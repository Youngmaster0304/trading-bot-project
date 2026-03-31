import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from datetime import datetime

from stream import BinanceStreamer
from model import AvellanedaStoikovModel, MLPredictor
from engine import MatchingEngine
from risk import RiskManager

st.set_page_config(page_title="Jane Street Style MM Simulator", layout="wide", page_icon="📈")

# CSS Hack to completely REMOVE Streamlit's "dimming/pulsing" effect during fast reruns
st.markdown("""
<style>
    [data-testid="stFragment"] {
        opacity: 1 !important;
        transition: none !important;
        animation: none !important;
    }
    [data-stale="true"] {
        opacity: 1 !important;
        transition: none !important;
        filter: none !important;
        animation: none !important;
    }
    .stElementContainer {
        opacity: 1 !important;
        transition: none !important;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_streamer_multi():
    streamer = BinanceStreamer(["btcusdt", "ethusdt"])
    streamer.start()
    return streamer

streamer = init_streamer_multi()

# Init Multi-Asset Session State
if "engines" not in st.session_state:
    st.session_state.engines = {
        "btc": MatchingEngine(order_size=0.1, fee_rate=0.0005),
        "eth": MatchingEngine(order_size=2.0, fee_rate=0.0005) # ETH size is larger due to price ratio
    }
if "risks" not in st.session_state:
    st.session_state.risks = {
        "btc": RiskManager(max_inventory=5.0, max_drawdown=-2000.0),
        "eth": RiskManager(max_inventory=100.0, max_drawdown=-2000.0)
    }
if "histories" not in st.session_state:
    def empty_hist():
        return {'time': [], 'mid_price': [], 'microprice': [], 'res_price': [], 'ask_price': [], 'bid_price': [], 'inventory': [], 'realized_pnl': [], 'unrealized_pnl': [], 'total_pnl': [], 'ofi': [], 'dynamic_vol': [], 'regime': [], 'ai_pred': [], 'ai_conf': []}
    st.session_state.histories = {"btc": empty_hist(), "eth": empty_hist()}

if "predictors" not in st.session_state:
    st.session_state.predictors = {
        "btc": MLPredictor(window_size=300),
        "eth": MLPredictor(window_size=300)
    }

if "auto_loop" not in st.session_state:
    st.session_state.auto_loop = False

# Sidebar Controls
st.sidebar.header("MM Parameters")
risk_aversion = st.sidebar.slider("Risk Aversion (Gamma)", 0.01, 1.0, 0.1, 0.01)
liquidity = st.sidebar.slider("Liquidity Density (k)", 0.1, 5.0, 1.5, 0.1)
ofi_weight = st.sidebar.slider("OFI Weight (Directional Bias)", 0.0, 50.0, 10.0, 1.0)

col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("Start MM"):
        st.session_state.auto_loop = True
with col2:
    if st.button("Stop MM"):
        st.session_state.auto_loop = False
        
st.sidebar.button("Reset State", on_click=lambda: st.session_state.clear())

if st.session_state.auto_loop and (streamer.best_bid.get("btcusdt") is None or streamer.best_bid.get("ethusdt") is None):
    st.warning("Connecting to Binance Multiplexed Streams... Please wait.")
    time.sleep(1)
    st.rerun()

# Layout
st.title("Live Market Simulator")

@st.fragment(run_every=1)
def update_dashboard():
    # Show active halts exactly ONCE per UI update to prevent spam
    for asset, sym in [("btc", "btcusdt"), ("eth", "ethusdt")]:
        engine = st.session_state.engines[asset]
        risk = st.session_state.risks[asset]
        microprice = streamer.microprice.get(sym)
        if microprice is None:
            microprice = streamer.best_bid.get(sym) or 0.0
        unrealized = engine.get_unrealized_pnl(microprice)
        halt, reason = risk.check_limits(engine.inventory, unrealized, engine.realized_pnl)
        if halt:
            st.error(f"[{asset.upper()}] Trading Halted: {reason}")

    # 1. Trading Loop Logic
    if st.session_state.auto_loop:
        for _ in range(5):
            if not st.session_state.auto_loop:
                break
                
            curr_time = datetime.now()
            
            # Extract correlation mapping between BTC and ETH (last 60 ticks)
            btc_hist = st.session_state.histories["btc"]
            eth_hist = st.session_state.histories["eth"]
            cross_correlation = 0.0
            
            if len(btc_hist['mid_price']) > 60 and len(eth_hist['mid_price']) > 60:
                btc_rets = pd.Series(btc_hist['mid_price'][-60:]).pct_change().dropna()
                eth_rets = pd.Series(eth_hist['mid_price'][-60:]).pct_change().dropna()
                if len(btc_rets) == len(eth_rets):
                    cross_correlation = btc_rets.corr(eth_rets)
                    if pd.isna(cross_correlation): cross_correlation = 0.0
            
            for asset, sym in [("btc", "btcusdt"), ("eth", "ethusdt")]:
                engine = st.session_state.engines[asset]
                risk = st.session_state.risks[asset]
                hist = st.session_state.histories[asset]
                predictor = st.session_state.predictors[asset]
                
                b_bid = streamer.best_bid.get(sym)
                b_ask = streamer.best_ask.get(sym)
                if b_bid is None or b_ask is None:
                    continue
                    
                mid = (b_bid + b_ask) / 2.0
                microprice = streamer.microprice.get(sym)
                if microprice is None:
                    microprice = mid
                ofi = streamer.ofi.get(sym, 0.0)
                
                # Dynamic Volatility Math (Rolling STDEV)
                if len(hist['mid_price']) > 5:
                    recent_prices = pd.Series(hist['mid_price'][-60:])
                    std_dev = recent_prices.pct_change().dropna().std()
                    dynamic_vol = max((std_dev * 100000.0) if pd.notna(std_dev) else 2.0, 0.1)
                else:
                    dynamic_vol = 2.0
                    
                # Machine Learning Training & Prediction Step
                predictor.add_tick(ofi, dynamic_vol, engine.inventory, microprice)
                ai_alpha, ai_conf = predictor.predict_alpha(ofi, dynamic_vol, engine.inventory)
                    
                # Regime Detection Math (Phase 4)
                regime = "🟢 Calm"
                if len(hist['dynamic_vol']) > 60:
                    long_vol_ma = pd.Series(hist['dynamic_vol'][-300:]).mean()
                    if dynamic_vol > long_vol_ma * 2.0:
                        regime = "🔴 Volatile"
                    elif abs(ofi) > 0.4:
                        regime = "🟡 Trending"
                else:
                    if dynamic_vol > 5.0:
                        regime = "🔴 Volatile"
                    elif abs(ofi) > 0.4:
                        regime = "🟡 Trending"
                        
                # MULTI-ASSET CORRELATION DEFENSE (Phase 7)
                correlation_discount = 1.0
                if asset == "eth" and cross_correlation > 0.7:
                    # If BTC is dumping hard, slash ETH confidence preemptively
                    btc_ofi = streamer.ofi.get("btcusdt", 0.0)
                    if btc_ofi < -0.4:
                        correlation_discount = 0.2
                        regime = "⚠️ BTC Contagion (Dump)"
                    elif btc_ofi > 0.4:
                        correlation_discount = 0.2
                        regime = "⚠️ BTC Contagion (Pump)"
                
                # Dynamic Quote Sizing Math
                confidence_multiplier = 1.0
                if regime == "🟢 Calm" and abs(ofi) > 0.2:
                    confidence_multiplier = 2.0
                elif regime == "🔴 Volatile" or "Contagion" in regime:
                    confidence_multiplier = 0.5
                    
                inventory_utilization = abs(engine.inventory) / risk.max_inventory
                risk_discount = max(0.1, 1.0 - inventory_utilization)
                
                base_size = 0.1 if asset == "btc" else 2.0
                dynamic_size = base_size * confidence_multiplier * risk_discount * correlation_discount
                dynamic_size = round(dynamic_size, 3)
                
                # Risk Check
                unrealized = engine.get_unrealized_pnl(microprice)
                halt, reason = risk.check_limits(engine.inventory, unrealized, engine.realized_pnl)
                
                if halt:
                    continue
                    
                # Strategy Math (Phase 8: Add AI Alpha)
                model = AvellanedaStoikovModel(risk_aversion=risk_aversion, liquidity_density=liquidity, volatility=5.0, terminal_time=1.0)
                
                effective_vol = dynamic_vol * 3.0 if "Contagion" in regime else dynamic_vol
                quotes = model.get_quotes(microprice, engine.inventory, dynamic_vol=effective_vol, ofi=ofi, ofi_weight=ofi_weight, ai_alpha_prediction=ai_alpha)
                
                # Engine Fill Simulation
                engine.check_fills(b_bid, b_ask, quotes['bid'], quotes['ask'], curr_time, dynamic_size=dynamic_size)
                
                # Update state
                hist['time'].append(curr_time)
                hist['mid_price'].append(mid)
                hist['microprice'].append(microprice)
                hist['res_price'].append(quotes['reservation_price'])
                hist['ask_price'].append(quotes['ask'])
                hist['bid_price'].append(quotes['bid'])
                hist['inventory'].append(engine.inventory)
                hist['realized_pnl'].append(engine.realized_pnl)
                hist['unrealized_pnl'].append(unrealized)
                hist['total_pnl'].append(engine.realized_pnl + unrealized)
                hist['ofi'].append(ofi)
                hist['dynamic_vol'].append(dynamic_vol)
                hist['regime'].append(regime)
                hist['ai_pred'].append(ai_alpha)
                hist['ai_conf'].append(ai_conf)
                
            time.sleep(0.1)

    # 2. Render Global HUD
    btc_un = st.session_state.engines["btc"].get_unrealized_pnl(streamer.microprice.get("btcusdt") or 0.0)
    eth_un = st.session_state.engines["eth"].get_unrealized_pnl(streamer.microprice.get("ethusdt") or 0.0)
    
    total_net_pnl = st.session_state.engines["btc"].realized_pnl + btc_un + \
                    st.session_state.engines["eth"].realized_pnl + eth_un
                    
    total_fees = st.session_state.engines["btc"].total_fees + st.session_state.engines["eth"].total_fees

    btc_hist = st.session_state.histories["btc"]
    eth_hist = st.session_state.histories["eth"]
    
    cross_corr = 0.0
    if len(btc_hist['mid_price']) > 60 and len(eth_hist['mid_price']) > 60:
        btc_rets = pd.Series(btc_hist['mid_price'][-60:]).pct_change().dropna()
        eth_rets = pd.Series(eth_hist['mid_price'][-60:]).pct_change().dropna()
        if len(btc_rets) == len(eth_rets):
            cross_corr = btc_rets.corr(eth_rets)
            if pd.isna(cross_corr): cross_corr = 0.0

    st.markdown("### Global Portfolio HUD")
    hud1, hud2, hud3, hud4 = st.columns(4)
    hud1.metric("Total Portfolio Net PnL", f"${total_net_pnl:.2f}")
    hud2.metric("Total Exchange Fees Paid", f"${total_fees:.2f}")
    hud3.metric("BTC/ETH Correlation (60t)", f"{cross_corr:.2f}")
    status = "Active" if st.session_state.auto_loop else "Halted"
    hud4.metric("System State", status)
    
    st.markdown("---")

    # 3. Render Tabs Environment
    tab1, tab2 = st.tabs(["BTC/USDT", "ETH/USDT"])
    
    for tab, asset, sym in zip([tab1, tab2], ["btc", "eth"], ["btcusdt", "ethusdt"]):
        with tab:
            engine = st.session_state.engines[asset]
            hist = st.session_state.histories[asset]
            
            if not hist['time']:
                st.info(f"Waiting for {asset.upper()} tick data...")
                continue
                
            top_cols = st.columns(6)
            micro = hist['microprice'][-1]
            latest_ofi = hist['ofi'][-1]
            lat_vol = hist['dynamic_vol'][-1]
            latest_regime = hist['regime'][-1]
            latest_ai_conf = hist['ai_conf'][-1]
            mid = hist['mid_price'][-1]
            unreal = engine.get_unrealized_pnl(mid)
            
            # Formatted AI Conf
            ai_status_color = "🟢" if latest_ai_conf > 50 else ("🟡" if latest_ai_conf > 20 else "⚪")
            ai_status = f"{ai_status_color} {latest_ai_conf:.1f}% Confidence"

            top_cols[0].metric("Microprice", f"${micro:.2f}", f"Mid: ${mid:.2f}")
            top_cols[1].metric("OFI", f"{latest_ofi:.2f}", f"Vol: {lat_vol:.2f}σ")
            top_cols[2].metric(f"Inventory ({asset.upper()})", f"{engine.inventory:.3f}")
            top_cols[3].metric("Total PnL", f"${(engine.realized_pnl + unreal):.2f}", f"Unreal: ${unreal:.2f}")
            top_cols[4].metric("Market Regime", latest_regime)
            top_cols[5].metric("AI Target Forward Return", f"{(hist['ai_pred'][-1]*1000):.3f}bps", ai_status)
            
            # Sub-Chart Generation
            df = pd.DataFrame(hist).tail(100)
            fig = make_subplots(rows=2, cols=2, 
                                subplot_titles=(f"{asset.upper()} Quotes vs Microprice", "Inventory Risk", "PnL Tracking", "Alpha Signals & AI Prediction"),
                                vertical_spacing=0.1, horizontal_spacing=0.05)
                                
            fig.add_trace(go.Scatter(x=df['time'], y=df['ask_price'], mode='lines', name='Ask', line=dict(color='red', dash='dash')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['time'], y=df['microprice'], mode='lines', name='Microprice', line=dict(color='yellow')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['time'], y=df['res_price'], mode='lines', name='Reservation', line=dict(color='white')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['time'], y=df['bid_price'], mode='lines', name='Bid', line=dict(color='green', dash='dash')), row=1, col=1)
            
            if engine.trades and not df.empty:
                start_time = df['time'].iloc[0]
                recent_trades = [t for t in engine.trades if t['timestamp'] >= start_time]
                buys = [t for t in recent_trades if t['side'] == 'BUY']
                sells = [t for t in recent_trades if t['side'] == 'SELL']
                
                if buys:
                    fig.add_trace(go.Scatter(x=[t['timestamp'] for t in buys], y=[t['price'] for t in buys], mode='markers', name='Buy', marker=dict(symbol='triangle-up', color='lime', size=14, line=dict(width=1, color='white'))), row=1, col=1)
                if sells:
                    fig.add_trace(go.Scatter(x=[t['timestamp'] for t in sells], y=[t['price'] for t in sells], mode='markers', name='Sell', marker=dict(symbol='triangle-down', color='red', size=14, line=dict(width=1, color='white'))), row=1, col=1)

            fig.add_trace(go.Bar(x=df['time'], y=df['inventory'], name='Inventory', marker_color='cyan'), row=1, col=2)
            fig.add_trace(go.Scatter(x=df['time'], y=df['realized_pnl'], mode='lines', fill='tozeroy', name='Realized PnL', line=dict(color='blue')), row=2, col=1)
            fig.add_trace(go.Scatter(x=df['time'], y=df['total_pnl'], mode='lines', name='Total PnL', line=dict(color='purple')), row=2, col=1)
            
            # Plot continuous prediction magnitude on the bottom right chart
            fig.add_trace(go.Scatter(x=df['time'], y=df['dynamic_vol'], mode='lines', name='Vol', line=dict(color='magenta')), row=2, col=2)
            fig.add_trace(go.Scatter(x=df['time'], y=(df['ai_pred'] * 100000.0), mode='lines', name='AI Return Pred * 10^5', line=dict(color='orange', dash='dot')), row=2, col=2)
            
            fig.update_layout(height=600, template="plotly_dark", margin=dict(l=20, r=20, t=40, b=20), uirevision="constant_"+asset)
            st.plotly_chart(fig, use_container_width=True, key=f"chart_{asset}")
            
            st.markdown(f"#### {asset.upper()} Live Trade Log")
            if engine.trades:
                trade_df = pd.DataFrame(engine.trades).iloc[::-1].head(10)
                st.dataframe(trade_df, use_container_width=True, key=f"table_{asset}")
            else:
                st.info("No fills executed yet.")

update_dashboard()

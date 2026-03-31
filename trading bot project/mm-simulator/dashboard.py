import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from datetime import datetime

from stream import BinanceStreamer
from model import AvellanedaStoikovModel
from engine import MatchingEngine
from risk import RiskManager

st.set_page_config(page_title="Jane Street Style MM Simulator", layout="wide", page_icon="📈")

st.title("Live Market Making Simulator")
st.markdown("Avellaneda-Stoikov model integrated with live Binance WebSocket data.")

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

# Cache the streamer so we don't reconnect on every Streamlit rerun
@st.cache_resource
def init_streamer():
    streamer = BinanceStreamer("btcusdt")
    streamer.start()
    return streamer

streamer = init_streamer()

# Init Session State
if "engine" not in st.session_state:
    st.session_state.engine = MatchingEngine(order_size=0.1)
    
if "risk_manager" not in st.session_state:
    st.session_state.risk_manager = RiskManager(max_inventory=5.0, max_drawdown=-1000.0)
    
if "history" not in st.session_state:
    st.session_state.history = {
        'time': [],
        'mid_price': [],
        'res_price': [],
        'ask_price': [],
        'bid_price': [],
        'inventory': [],
        'realized_pnl': [],
        'unrealized_pnl': [],
        'total_pnl': []
    }
    
if "auto_loop" not in st.session_state:
    st.session_state.auto_loop = False

# Sidebar Controls
st.sidebar.header("MM Parameters")
risk_aversion = st.sidebar.slider("Risk Aversion (Gamma)", 0.01, 1.0, 0.1, 0.01)
volatility = st.sidebar.slider("Volatility Base (Sigma)", 0.1, 10.0, 5.0, 0.1)
liquidity = st.sidebar.slider("Liquidity Density (k)", 0.1, 5.0, 1.5, 0.1)

col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("Start MM"):
        st.session_state.auto_loop = True
with col2:
    if st.button("Stop MM"):
        st.session_state.auto_loop = False
        
st.sidebar.button("Reset State", on_click=lambda: st.session_state.clear())

if st.session_state.auto_loop and streamer.best_bid is None:
    st.warning("Connecting to Binance... Please wait.")
    time.sleep(1)
    st.rerun()

# Layout
@st.fragment(run_every=1)
def update_dashboard():
    model = AvellanedaStoikovModel(risk_aversion=risk_aversion, liquidity_density=liquidity, volatility=volatility, terminal_time=1.0)
    engine = st.session_state.engine
    risk = st.session_state.risk_manager
    hist = st.session_state.history

    if st.session_state.auto_loop:
        for _ in range(10):
            if not st.session_state.auto_loop:
                break
                
            b_bid = streamer.best_bid
            b_ask = streamer.best_ask
            
            if b_bid is None or b_ask is None:
                time.sleep(0.1)
                continue
                
            mid = (b_bid + b_ask) / 2.0
            
            # Risk Check
            unrealized = engine.get_unrealized_pnl(mid)
            halt, reason = risk.check_limits(engine.inventory, unrealized, engine.realized_pnl)
            
            if halt:
                st.session_state.auto_loop = False
                st.error(f"Trading Halted: {reason}")
                break
                
            # Strategy
            quotes = model.get_quotes(mid, engine.inventory)
            
            # Engine Fill Simulation
            curr_time = datetime.now()
            engine.check_fills(b_bid, b_ask, quotes['bid'], quotes['ask'], curr_time)
            
            # Update state
            hist['time'].append(curr_time)
            hist['mid_price'].append(mid)
            hist['res_price'].append(quotes['reservation_price'])
            hist['ask_price'].append(quotes['ask'])
            hist['bid_price'].append(quotes['bid'])
            hist['inventory'].append(engine.inventory)
            
            hist['realized_pnl'].append(engine.realized_pnl)
            hist['unrealized_pnl'].append(unrealized)
            hist['total_pnl'].append(engine.realized_pnl + unrealized)
                    
            time.sleep(0.1)

    # Render Metrics
    top_cols = st.columns(4)
    if hist['time']:
        mid = hist['mid_price'][-1]
        b_bid = hist['bid_price'][-1] 
        b_ask = hist['ask_price'][-1]
        unrealized = engine.get_unrealized_pnl(mid)
    else:
        mid, b_bid, b_ask, unrealized = 0, 0, 0, 0

    if hist['time']:
        top_cols[0].metric("Mid Price", f"${mid:.2f}", f"Spread: ${(b_ask - b_bid):.2f}")
    else:
        top_cols[0].metric("Mid Price", "$0.00", "Spread: $0.00")
        
    top_cols[1].metric("Inventory (BTC)", f"{engine.inventory:.3f}")
    top_cols[2].metric("Total PnL", f"${(engine.realized_pnl + unrealized):.2f}", f"Unrealized: ${unrealized:.2f}")
    
    status_text = "Live Quoting" if st.session_state.auto_loop else "Halted"
    status_sub = "Active" if st.session_state.auto_loop else "Inactive"
    top_cols[3].metric("System Status", status_text, status_sub)
    
    if not hist['time']:
        return
        
    # Render Chart
    df = pd.DataFrame(hist).tail(100)
    
    fig = make_subplots(rows=2, cols=2, 
                        subplot_titles=("Live Quotes vs Mid", "Inventory Risk", "PnL Tracking", "Spread Distribution"),
                        vertical_spacing=0.1,
                        horizontal_spacing=0.05)
                        
    fig.add_trace(go.Scatter(x=df['time'], y=df['ask_price'], mode='lines', name='Our Ask', line=dict(color='red', dash='dash')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['time'], y=df['mid_price'], mode='lines', name='Market Mid', line=dict(color='yellow')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['time'], y=df['res_price'], mode='lines', name='Reservation', line=dict(color='white')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['time'], y=df['bid_price'], mode='lines', name='Our Bid', line=dict(color='green', dash='dash')), row=1, col=1)
    
    fig.add_trace(go.Bar(x=df['time'], y=df['inventory'], name='Inventory', marker_color='cyan'), row=1, col=2)
    
    fig.add_trace(go.Scatter(x=df['time'], y=df['realized_pnl'], mode='lines', fill='tozeroy', name='Realized PnL', line=dict(color='blue')), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['time'], y=df['total_pnl'], mode='lines', name='Total PnL', line=dict(color='purple')), row=2, col=1)
    
    our_spread = df['ask_price'] - df['bid_price']
    fig.add_trace(go.Scatter(x=df['time'], y=our_spread, mode='lines', name='Optimal Spread', line=dict(color='orange')), row=2, col=2)
    
    fig.update_layout(height=700, template="plotly_dark", margin=dict(l=20, r=20, t=40, b=20), uirevision="constant")
    st.plotly_chart(fig, use_container_width=True, key="live_chart")

update_dashboard()

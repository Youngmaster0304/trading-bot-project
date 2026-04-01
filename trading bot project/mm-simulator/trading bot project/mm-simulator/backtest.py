import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from model import AvellanedaStoikovModel
from engine import MatchingEngine
from risk import RiskManager
from volatility import VolatilityEstimator, RegimeDetector, MicropriceCalculator
from analytics import AdverseSelectionAnalyzer, PerformanceAnalytics

def run_backtest(df, gamma=0.1, k=1.5, ofi_weight=10.0):
    engine = MatchingEngine(initial_cash=100000.0, order_size=0.1, fee_rate=0.0005, max_inventory=5.0)
    risk = RiskManager(max_inventory=5.0, max_drawdown=-2000.0)
    model = AvellanedaStoikovModel(risk_aversion=gamma, liquidity_density=k, volatility=5.0, terminal_time=1.0)
    
    # Enhanced analytics
    vol_estimator = VolatilityEstimator(window_size=100)
    regime_detector = RegimeDetector(vol_window=200, ofi_window=100)
    microprice_calc = MicropriceCalculator(window_size=50)
    adverse_analyzer = AdverseSelectionAnalyzer(window_size=1000)
    
    history = []
    
    for row in df.itertuples():
        timestamp = pd.to_datetime(row.timestamp)
        b_bid = row.best_bid
        b_ask = row.best_ask
        mid = row.mid_price
        microprice = row.microprice
        ofi = row.ofi
        dynamic_vol = row.dynamic_vol
        long_vol_ma = row.long_vol_ma
        
        # Update volatility estimator
        realized_vol = vol_estimator.add_price(mid)
        
        # Update regime detector
        regime_detector.add_observation(realized_vol, ofi)
        regime = regime_detector.get_regime()
        regime_confidence = regime_detector.get_regime_confidence()
        spread_mult = regime_detector.get_spread_multiplier()
        
        # Calculate microprice and divergence
        bid_vol = getattr(row, 'bid_volume', 1.0)
        ask_vol = getattr(row, 'ask_volume', 1.0)
        microprice_calc.add_market_state(b_bid, b_ask, bid_vol, ask_vol)
        microprice_signal = microprice_calc.get_divergence_signal()
        
        # Confidence and sizing from original logic
        confidence = 2.0 if regime == "CALM" and abs(ofi) > 0.2 else (0.5 if regime == "VOLATILE" else 1.0)
        risk_discount = max(0.1, 1.0 - (abs(engine.inventory) / risk.max_inventory))
        dynamic_size = round(0.1 * confidence * risk_discount, 3)
        
        unrealized = engine.get_unrealized_pnl(microprice)
        halt, reason = risk.check_limits(engine.inventory, unrealized, engine.realized_pnl)
        
        if halt:
            break
            
        # Get quotes with regime adjustment and microprice signal
        quotes = model.get_quotes(
            microprice, 
            engine.inventory, 
            dynamic_vol=dynamic_vol, 
            ofi=ofi, 
            ofi_weight=ofi_weight,
            regime_multiplier=spread_mult,
            microprice_signal=microprice_signal
        )
        
        # Check fills and log
        engine.check_fills(b_bid, b_ask, quotes['bid'], quotes['ask'], timestamp, dynamic_size=dynamic_size)
        engine.log_spread(quotes['ask'] - quotes['bid'], timestamp)
        
        # Track adverse selection
        adverse_analyzer.add_market_tick(microprice)
        
        history.append({
            'timestamp': timestamp,
            'microprice': microprice,
            'bid': quotes['bid'],
            'ask': quotes['ask'],
            'inventory': engine.inventory,
            'realized_pnl': engine.realized_pnl,
            'unrealized_pnl': unrealized,
            'net_pnl': engine.realized_pnl + unrealized,
            'regime': regime,
            'regime_confidence': regime_confidence,
            'realized_vol': realized_vol,
            'spread': quotes['ask'] - quotes['bid']
        })
        
    return pd.DataFrame(history), engine.trades, adverse_analyzer, regime_detector

def calculate_adverse_selection(trades, adverse_analyzer):
    """Use the AdverseSelectionAnalyzer to compute metrics"""
    summary = adverse_analyzer.get_summary()
    return summary

def grid_search(df):
    gammas = [0.05, 0.1, 0.5]
    best_pnl = -999999
    best_gamma = 0.1
    best_hist = None
    best_trades = None
    best_analyzer = None
    
    print("\nStarting Grid Search...")
    for g in gammas:
        hist, trades, analyzer, detector = run_backtest(df, gamma=g)
        net_pnl = hist['net_pnl'].iloc[-1] if not hist.empty else 0
        print(f"Gamma = {g:.2f} | Net PnL = ${net_pnl:.2f} | Trades = {len(trades)}")
        if net_pnl > best_pnl:
            best_pnl = net_pnl
            best_gamma = g
            best_hist = hist
            best_trades = trades
            best_analyzer = analyzer
    
    print(f"\n* Optimal Gamma Found: {best_gamma} (Net PnL: ${best_pnl:.2f})")
    return best_hist, best_trades, best_gamma, best_analyzer

def generate_report(hist, trades, df, optimal_gamma):
    print("Generating Plotly HTML Report...")
    fig = make_subplots(rows=3, cols=1, 
                        subplot_titles=(f"Backtest Results (Gamma = {optimal_gamma})", "Inventory Tracker", "Net PnL Curve"),
                        vertical_spacing=0.1,
                        row_heights=[0.5, 0.25, 0.25])
                        
    fig.add_trace(go.Scatter(x=hist['timestamp'], y=hist['microprice'], mode='lines', name='Microprice', line=dict(color='yellow')), row=1, col=1)
    fig.add_trace(go.Scatter(x=hist['timestamp'], y=hist['ask'], mode='lines', name='Our Ask', line=dict(color='red', dash='dash')), row=1, col=1)
    fig.add_trace(go.Scatter(x=hist['timestamp'], y=hist['bid'], mode='lines', name='Our Bid', line=dict(color='green', dash='dash')), row=1, col=1)
    
    buys = [t for t in trades if t['side'] == 'BUY']
    sells = [t for t in trades if t['side'] == 'SELL']
    
    if buys:
        fig.add_trace(go.Scatter(x=[t['timestamp'] for t in buys], y=[t['price'] for t in buys], mode='markers', name='Buys', marker=dict(symbol='triangle-up', color='lime', size=8)), row=1, col=1)
    if sells:
        fig.add_trace(go.Scatter(x=[t['timestamp'] for t in sells], y=[t['price'] for t in sells], mode='markers', name='Sells', marker=dict(symbol='triangle-down', color='red', size=8)), row=1, col=1)
        
    fig.add_trace(go.Bar(x=hist['timestamp'], y=hist['inventory'], name='Inventory', marker_color='cyan'), row=2, col=1)
    fig.add_trace(go.Scatter(x=hist['timestamp'], y=hist['net_pnl'], mode='lines', fill='tozeroy', name='Net PnL', line=dict(color='lime')), row=3, col=1)
    
    fig.update_layout(height=1200, template="plotly_dark", title_text="High Frequency Backtest Report")
    fig.write_html("backtest_report.html")
    print("Successfully generated 'backtest_report.html'")

if __name__ == "__main__":
    df = pd.read_csv("history.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    best_hist, best_trades, best_gamma, best_analyzer = grid_search(df)
    
    # Get adverse selection metrics
    adverse_metrics = calculate_adverse_selection(best_trades, best_analyzer)
    print(f"\nAdverse Selection Report:")
    print(f"Total Executions: {adverse_metrics['total_trades']}")
    print(f"Toxic Fills Detected: {adverse_metrics['toxic_trades']} ({adverse_metrics['toxicity_rate']:.2f}%)")
    
    generate_report(best_hist, best_trades, df, best_gamma)

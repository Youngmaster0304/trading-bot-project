"""
Dashboard Analytics Utilities
Provides functions for computing session statistics, P&L metrics, and trade analysis
for real-time visualization
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta


class SessionAnalytics:
    """Real-time session performance analytics"""
    
    def __init__(self):
        self.pnl_history = []
        self.trade_count = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
    def update_from_engine(self, engine, current_midprice):
        """Update analytics from matching engine state"""
        realized = engine.realized_pnl
        unrealized = engine.get_unrealized_pnl(current_midprice)
        total_pnl = realized + unrealized
        
        self.pnl_history.append({
            "timestamp": datetime.now(),
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "total_pnl": total_pnl
        })
        
        # Track only recent history (last 10,000 ticks)
        if len(self.pnl_history) > 10000:
            self.pnl_history.pop(0)
    
    def calculate_sharpe_ratio(self, risk_free_rate=0.0):
        """Calculate Sharpe ratio from PnL history"""
        if len(self.pnl_history) < 2:
            return 0.0
        
        pnls = np.array([p["total_pnl"] for p in self.pnl_history])
        returns = np.diff(pnls)
        
        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0
        
        sharpe = (np.mean(returns) - risk_free_rate) / np.std(returns) * np.sqrt(252)
        return float(sharpe)
    
    def calculate_sortino_ratio(self, target_return=0.0):
        """Calculate Sortino ratio (downside risk only)"""
        if len(self.pnl_history) < 2:
            return 0.0
        
        pnls = np.array([p["total_pnl"] for p in self.pnl_history])
        returns = np.diff(pnls)
        
        downside_returns = [r for r in returns if r < target_return]
        
        if not downside_returns or np.std(downside_returns) == 0:
            return 0.0
        
        mean_return = np.mean(returns) if len(returns) > 0 else 0.0
        sortino = (mean_return - target_return) / np.std(downside_returns) * np.sqrt(252)
        return float(sortino)
    
    def calculate_max_drawdown(self):
        """Calculate maximum drawdown from equity curve"""
        if len(self.pnl_history) < 2:
            return 0.0
        
        pnls = np.array([p["total_pnl"] for p in self.pnl_history])
        cum_max = np.maximum.accumulate(pnls)
        drawdown = (pnls - cum_max) / np.maximum(np.abs(cum_max), 1.0)
        
        return float(np.min(drawdown)) if len(drawdown) > 0 else 0.0
    
    def calculate_win_rate(self, trades):
        """Calculate win rate from trades"""
        if not trades:
            return 0.0
        
        profitable = sum(1 for t in trades if t.get("realized_pnl_after", 0) > 0)
        return (profitable / len(trades)) * 100.0 if trades else 0.0
    
    def calculate_avg_trade_pnl(self, trades):
        """Calculate average P&L per trade"""
        if not trades:
            return 0.0
        
        trade_pnls = []
        for i, trade in enumerate(trades):
            if i > 0:
                pnl_delta = trade.get("realized_pnl_after", 0) - trades[i-1].get("realized_pnl_after", 0)
                trade_pnls.append(pnl_delta)
        
        return np.mean(trade_pnls) if trade_pnls else 0.0
    
    def get_summary(self, trades):
        """Get comprehensive session summary"""
        if not self.pnl_history:
            return {
                "total_pnl": 0.0,
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "total_trades": len(trades),
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "avg_trade_pnl": 0.0,
                "current_inventory": 0.0
            }
        
        latest = self.pnl_history[-1]
        
        return {
            "total_pnl": latest["total_pnl"],
            "realized_pnl": latest["realized_pnl"],
            "unrealized_pnl": latest["unrealized_pnl"],
            "total_trades": len(trades),
            "sharpe_ratio": self.calculate_sharpe_ratio(),
            "sortino_ratio": self.calculate_sortino_ratio(),
            "max_drawdown": self.calculate_max_drawdown(),
            "win_rate": self.calculate_win_rate(trades),
            "avg_trade_pnl": self.calculate_avg_trade_pnl(trades)
        }


def create_pnl_chart(history_df, asset_name="BTC"):
    """Create P&L chart with realized, unrealized, and combined curves"""
    if history_df.empty:
        return None
    
    fig = go.Figure()
    
    # Realized P&L (blue, filled)
    fig.add_trace(go.Scatter(
        x=history_df['time'],
        y=history_df['realized_pnl'],
        mode='lines',
        name='Realized P&L',
        line=dict(color='#00FF00', width=2),
        fill='tozeroy',
        fillcolor='rgba(0, 255, 0, 0.2)'
    ))
    
    # Unrealized P&L (orange dashed)
    fig.add_trace(go.Scatter(
        x=history_df['time'],
        y=history_df['unrealized_pnl'],
        mode='lines',
        name='Unrealized P&L',
        line=dict(color='#FFA500', width=2, dash='dash'),
        fill='tozeroy',
        fillcolor='rgba(255, 165, 0, 0.1)'
    ))
    
    # Total P&L (purple, thick)
    fig.add_trace(go.Scatter(
        x=history_df['time'],
        y=history_df['total_pnl'],
        mode='lines',
        name='Total P&L',
        line=dict(color='#9D4EDD', width=3),
        fill='tozeroy',
        fillcolor='rgba(157, 78, 221, 0.15)'
    ))
    
    # Add zero line for reference
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    fig.update_layout(
        title=f"{asset_name.upper()} Live P&L Curve",
        xaxis_title="Time",
        yaxis_title="P&L ($)",
        hovermode='x unified',
        template="plotly_dark",
        height=400,
        margin=dict(l=50, r=20, t=40, b=50)
    )
    
    return fig


def create_spread_chart(history_df, asset_name="BTC"):
    """Create candlestick chart with bid/ask quote bands overlay"""
    if history_df.empty:
        return None
    
    # Resample to 5-point candlesticks for clarity
    df_resampled = history_df.copy()
    
    fig = go.Figure()
    
    # Add candlesticks (mid price as OHLC)
    candlestick_data = []
    for i in range(0, len(df_resampled), max(1, len(df_resampled) // 50)):  # Max 50 candles
        chunk = df_resampled.iloc[i:min(i+10, len(df_resampled))]
        if chunk.empty:
            continue
        
        oprice = chunk['mid_price'].iloc[0]
        high = chunk['mid_price'].max()
        low = chunk['mid_price'].min()
        close = chunk['mid_price'].iloc[-1]
        time_label = chunk['time'].iloc[-1]
        
        candlestick_data.append({
            'x': time_label,
            'open': oprice,
            'high': high,
            'low': low,
            'close': close
        })
    
    if candlestick_data:
        candlestick_df = pd.DataFrame(candlestick_data)
        colors = ['green' if close >= open_ else 'red' 
                 for open_, close in zip(candlestick_df['open'], candlestick_df['close'])]
        
        fig.add_trace(go.Candlestick(
            x=candlestick_df['x'],
            open=candlestick_df['open'],
            high=candlestick_df['high'],
            low=candlestick_df['low'],
            close=candlestick_df['close'],
            name='Mid Price',
            increasing_line_color='green',
            decreasing_line_color='red'
        ))
    
    # Add bid/ask bands as shaded areas
    fig.add_trace(go.Scatter(
        x=history_df['time'],
        y=history_df['bid_price'],
        mode='lines',
        name='Bid Quote',
        line=dict(color='green', width=1, dash='dash'),
        opacity=0.7
    ))
    
    fig.add_trace(go.Scatter(
        x=history_df['time'],
        y=history_df['ask_price'],
        mode='lines',
        name='Ask Quote',
        line=dict(color='red', width=1, dash='dash'),
        fill='tonexty',
        fillcolor='rgba(255, 0, 0, 0.1)',
        opacity=0.7
    ))
    
    # Add microprice
    fig.add_trace(go.Scatter(
        x=history_df['time'],
        y=history_df['microprice'],
        mode='lines',
        name='Microprice',
        line=dict(color='yellow', width=2, dash='dot'),
        opacity=0.8
    ))
    
    fig.update_layout(
        title=f"{asset_name.upper()} Spread & Quote Positioning",
        xaxis_title="Time",
        yaxis_title="Price ($)",
        hovermode='x unified',
        template="plotly_dark",
        height=400,
        margin=dict(l=50, r=20, t=40, b=50),
        xaxis_rangeslider_visible=False
    )
    
    return fig


def create_inventory_heatmap(inventory_history):
    """Create inventory position timeline/heatmap"""
    if not inventory_history:
        return None
    
    df = pd.DataFrame(inventory_history)
    
    fig = go.Figure()
    
    # Inventory as colored area
    colors = ['green' if inv >= 0 else 'red' for inv in df['inventory']]
    
    fig.add_trace(go.Bar(
        x=df['time'],
        y=df['inventory'],
        marker=dict(
            color=df['inventory'],
            colorscale='RdYlGn',
            showscale=True,
            colorbar=dict(title="Inventory")
        ),
        name='Inventory Position',
        hovertemplate='<b>Time:</b> %{x}<br><b>Inventory:</b> %{y:.4f}<extra></extra>'
    ))
    
    fig.add_hline(y=0, line_dash="dash", line_color="yellow", opacity=0.5)
    
    fig.update_layout(
        title="Inventory Position Over Time",
        xaxis_title="Time",
        yaxis_title="Position Size",
        hovermode='x unified',
        template="plotly_dark",
        height=300,
        margin=dict(l=50, r=20, t=40, b=50)
    )
    
    return fig


def create_trade_log_table(trades, limit=15):
    """Create enhanced trade log DataFrame for display"""
    if not trades:
        return pd.DataFrame()
    
    # Take most recent trades
    recent_trades = trades[-limit:]
    
    table_data = []
    for i, trade in enumerate(recent_trades):
        # Calculate P&L for this trade
        if i > 0:
            trade_pnl = trade.get("realized_pnl_after", 0) - recent_trades[i-1].get("realized_pnl_after", 0)
        else:
            trade_pnl = trade.get("realized_pnl_after", 0)
        
        table_data.append({
            "Time": trade["timestamp"].strftime("%H:%M:%S.%f")[:-3],
            "Side": trade["side"],
            "Price": f"${trade['price']:.2f}",
            "Size": f"{trade['qty']:.4f}",
            "Fee": f"${trade['fee_usd']:.4f}",
            "Inventory": f"{trade['inventory_after']:.4f}",
            "P&L": f"${trade_pnl:.2f}",
            "Cum. PnL": f"${trade['realized_pnl_after']:.2f}"
        })
    
    return pd.DataFrame(table_data[::-1])  # Reverse to show most recent last


def create_statistics_panel(analytics, trades):
    """Create visual statistics panel data"""
    summary = analytics.get_summary(trades)
    
    stats = {
        "metric": [],
        "value": [],
        "indicator": []
    }
    
    # Total P&L
    total_pnl = summary["total_pnl"]
    stats["metric"].append("Total P&L")
    stats["value"].append(f"${total_pnl:,.2f}")
    stats["indicator"].append("🟢" if total_pnl > 0 else "🔴" if total_pnl < 0 else "⚪")
    
    # Realized P&L
    rpnl = summary["realized_pnl"]
    stats["metric"].append("Realized P&L")
    stats["value"].append(f"${rpnl:,.2f}")
    stats["indicator"].append("🟢" if rpnl > 0 else "🔴" if rpnl < 0 else "⚪")
    
    # Unrealized P&L
    upnl = summary["unrealized_pnl"]
    stats["metric"].append("Unrealized P&L")
    stats["value"].append(f"${upnl:,.2f}")
    stats["indicator"].append("🟢" if upnl > 0 else "🔴" if upnl < 0 else "⚪")
    
    # Total Trades
    trades_count = summary["total_trades"]
    stats["metric"].append("Total Trades")
    stats["value"].append(str(trades_count))
    stats["indicator"].append("🟢" if trades_count > 0 else "⚪")
    
    # Win Rate
    win_rate = summary["win_rate"]
    stats["metric"].append("Win Rate")
    stats["value"].append(f"{win_rate:.1f}%")
    stats["indicator"].append("🟢" if win_rate > 50 else ("🟡" if win_rate > 30 else "🔴"))
    
    # Sharpe Ratio
    sharpe = summary["sharpe_ratio"]
    stats["metric"].append("Sharpe Ratio")
    stats["value"].append(f"{sharpe:.2f}")
    stats["indicator"].append("🟢" if sharpe > 1.0 else ("🟡" if sharpe > 0 else "🔴"))
    
    # Sortino Ratio
    sortino = summary["sortino_ratio"]
    stats["metric"].append("Sortino Ratio")
    stats["value"].append(f"{sortino:.2f}")
    stats["indicator"].append("🟢" if sortino > 1.5 else ("🟡" if sortino > 0 else "🔴"))
    
    # Max Drawdown
    max_dd = summary["max_drawdown"]
    stats["metric"].append("Max Drawdown")
    stats["value"].append(f"{max_dd*100:.2f}%")
    stats["indicator"].append("🔴" if max_dd < -0.1 else ("🟡" if max_dd < 0 else "🟢"))
    
    # Avg Trade P&L
    avg_pnl = summary["avg_trade_pnl"]
    stats["metric"].append("Avg Trade P&L")
    stats["value"].append(f"${avg_pnl:.2f}")
    stats["indicator"].append("🟢" if avg_pnl > 0 else ("🟡" if avg_pnl > -50 else "🔴"))
    
    return pd.DataFrame(stats)


def create_ofi_regime_chart(history_df, asset_name="BTC"):
    """Create OFI and regime visualization"""
    if history_df.empty:
        return None
    
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        subplot_titles=(f"{asset_name} Order Flow & Volatility", "Market Regime"),
        vertical_spacing=0.1,
        row_heights=[0.6, 0.4]
    )
    
    # OFI (top)
    fig.add_trace(go.Bar(
        x=history_df['time'],
        y=history_df['ofi'],
        name='Order Flow Imbalance',
        marker=dict(
            color=history_df['ofi'],
            colorscale='RdYlGn',
            showscale=False
        ),
        hovertemplate='<b>OFI:</b> %{y:.2f}<extra></extra>'
    ), row=1, col=1)
    
    # Volatility (secondary axis on top)
    fig.add_trace(go.Scatter(
        x=history_df['time'],
        y=history_df['dynamic_vol'],
        name='Realized Volatility',
        line=dict(color='magenta', width=2, dash='dash'),
        yaxis='y2',
        hovertemplate='<b>Vol:</b> %{y:.2f}<extra></extra>'
    ), row=1, col=1)
    
    # Regime as categorical colors (bottom)
    regime_colors = {
        '🟢 Calm': 'green',
        '🟡 Trending': 'orange',
        '🔴 Volatile': 'red',
        '⚠️ BTC Contagion (Dump)': 'darkred',
        '⚠️ BTC Contagion (Pump)': 'darkgreen'
    }
    
    for regime, color in regime_colors.items():
        mask = history_df['regime'] == regime
        if mask.any():
            fig.add_trace(go.Scatter(
                x=history_df.loc[mask, 'time'],
                y=history_df.loc[mask, 'regime'],
                mode='markers',
                name=regime,
                marker=dict(size=10, color=color),
                hovertemplate=f'<b>{regime}</b><extra></extra>'
            ), row=2, col=1)
    
    fig.update_layout(
        height=500,
        template="plotly_dark",
        hovermode='x unified',
        margin=dict(l=50, r=20, t=50, b=50)
    )
    
    fig.update_yaxes(title_text="OFI", row=1, col=1)
    fig.update_yaxes(title_text="Regime", row=2, col=1)
    fig.update_xaxes(title_text="Time", row=2, col=1)
    
    return fig

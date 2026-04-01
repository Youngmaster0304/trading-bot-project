"""
Advanced Analytics & Research Layer
Step 19: Adverse Selection Metrics
Step 18: Parameter Sensitivity Analysis metrics
"""

import math
import numpy as np
from collections import defaultdict


class AdverseSelectionAnalyzer:
    """
    Measures toxicity of quotes by analyzing:
    - How often price moves against us after a fill
    - Time-to-adverse-move
    - Magnitude of adverse moves
    
    High adverse selection = our quotes are being picked off
    Low adverse selection = good market timing
    """
    
    def __init__(self, window_size=1000, lookback_ticks=20):
        """
        window_size: Number of trades to analyze
        lookback_ticks: How many ticks ahead to check for adverse moves
        """
        self.window_size = window_size
        self.lookback_ticks = lookback_ticks
        
        self.trades = []  # All executed trades
        self.future_prices = defaultdict(list)  # Map trade_id -> future prices
        self.toxic_count = 0
        self.total_trades = 0
    
    def log_trade(self, trade_id, side, fill_price, timestamp):
        """Log a trade execution"""
        self.trades.append({
            "id": trade_id,
            "side": side,  # "BUY" or "SELL"
            "price": fill_price,
            "timestamp": timestamp,
            "future_prices": deque(maxlen=self.lookback_ticks),
            "is_toxic": False,
            "adverse_move_pct": 0.0,
            "ticks_to_adverse": 0
        })
        
        if len(self.trades) > self.window_size:
            self.trades.pop(0)
        
        self.total_trades += 1
    
    def add_market_tick(self, mid_price, trade_id=None):
        """
        Add a new market price observation
        Checks all recent trades to see if they're becoming toxic
        """
        # Update all recent trades with this new price
        for trade in reversed(self.trades):
            if len(trade["future_prices"]) >= self.lookback_ticks:
                continue
                
            trade["future_prices"].append(mid_price)
            
            # Check if this trade has become toxic
            if not trade["is_toxic"] and len(trade["future_prices"]) > 1:
                self._check_toxicity(trade, mid_price)
    
    def _check_toxicity(self, trade, current_price):
        """
        Determine if a trade is toxic based on:
        BUY: Adverse if price drops significantly after our buy
        SELL: Adverse if price rises significantly after our sell
        """
        fill_price = trade["price"]
        
        if trade["side"] == "BUY":
            # After we buy, price falls = toxic
            move = (current_price - fill_price) / fill_price
            if move < -0.0001:  # More than 1 basis point drop
                trade["is_toxic"] = True
                trade["adverse_move_pct"] = abs(move) * 100.0
                trade["ticks_to_adverse"] = len(trade["future_prices"])
                self.toxic_count += 1
        
        elif trade["side"] == "SELL":
            # After we sell, price rises = toxic
            move = (current_price - fill_price) / fill_price
            if move > 0.0001:  # More than 1 basis point rise
                trade["is_toxic"] = True
                trade["adverse_move_pct"] = move * 100.0
                trade["ticks_to_adverse"] = len(trade["future_prices"])
                self.toxic_count += 1
    
    def get_adverse_selection_rate(self):
        """Returns percentage of trades that became toxic"""
        if self.total_trades == 0:
            return 0.0
        return (self.toxic_count / self.total_trades) * 100.0
    
    def get_toxic_trades(self):
        """Returns list of toxic trades for analysis"""
        return [t for t in self.trades if t["is_toxic"]]
    
    def get_avg_adverse_move(self):
        """Returns average magnitude of adverse moves (in bps)"""
        toxic = self.get_toxic_trades()
        if not toxic:
            return 0.0
        return np.mean([t["adverse_move_pct"] for t in toxic])
    
    def get_avg_ticks_to_adverse(self):
        """Returns average number of ticks before adverse move detected"""
        toxic = self.get_toxic_trades()
        if not toxic:
            return 0.0
        return np.mean([t["ticks_to_adverse"] for t in toxic])
    
    def get_summary(self):
        """Returns comprehensive adverse selection report"""
        return {
            "total_trades": self.total_trades,
            "toxic_trades": self.toxic_count,
            "toxicity_rate": self.get_adverse_selection_rate(),
            "avg_adverse_move_bps": self.get_avg_adverse_move() * 100.0,
            "avg_ticks_to_adverse": self.get_avg_ticks_to_adverse(),
            "interpretation": self._interpret_toxicity()
        }
    
    def _interpret_toxicity(self):
        """Provide interpretation of toxicity metrics"""
        rate = self.get_adverse_selection_rate()
        
        if rate < 10:
            return "Excellent - Very selective quoting"
        elif rate < 25:
            return "Good - Selective on both sides"
        elif rate < 40:
            return "Fair - Some adverse selection"
        elif rate < 60:
            return "Poor - High adverse selection, quotes being picked off"
        else:
            return "Very Poor - Quotes consistently disadvantaged"


class ParameterSensitivityAnalyzer:
    """
    Analyzes how strategy performance varies with parameter changes
    Used for Step 18: Parameter sensitivity analysis
    """
    
    def __init__(self):
        self.sweep_results = {}  # param_combo -> performance_metrics
        
    def run_sensitivity_sweep(self, params_to_sweep, backtest_func):
        """
        Run backtests across parameter combinations
        
        Args:
            params_to_sweep: dict of {param_name: [values]}
            backtest_func: function(params_dict) -> performance_metrics
        
        Returns:
            Dictionary of results
        """
        results = []
        
        # Generate all combinations (simple 1D sweep for now)
        for param_name, values in params_to_sweep.items():
            for value in values:
                params = {param_name: value}
                
                # Run backtest with these params
                metrics = backtest_func(params)
                
                result = {
                    "param": param_name,
                    "value": value,
                    **metrics
                }
                results.append(result)
                self.sweep_results[f"{param_name}={value}"] = metrics
        
        return results
    
    def find_optimal_parameters(self, objective="sharpe"):
        """Find parameter values that maximize objective"""
        if not self.sweep_results:
            return None
        
        best_combo = max(
            self.sweep_results.items(),
            key=lambda x: x[1].get(objective, 0.0)
        )
        
        return {
            "combo": best_combo[0],
            "metrics": best_combo[1],
            "objective_value": best_combo[1].get(objective, 0.0)
        }
    
    def get_sensitivity_table(self):
        """Returns nicely formatted sensitivity analysis table"""
        if not self.sweep_results:
            return []
        
        rows = []
        for combo, metrics in self.sweep_results.items():
            rows.append({
                "parameter_combo": combo,
                "net_pnl": metrics.get("net_pnl", 0.0),
                "sharpe": metrics.get("sharpe", 0.0),
                "max_drawdown": metrics.get("max_drawdown", 0.0),
                "win_rate": metrics.get("win_rate", 0.0),
                "trades": metrics.get("trades", 0)
            })
        
        return rows


class PerformanceAnalytics:
    """Comprehensive performance analytics computation"""
    
    @staticmethod
    def calculate_sharpe(returns, risk_free_rate=0.02):
        """Calculate Sharpe ratio from returns series"""
        if len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualize (assuming ~252 trading days for crypto-adjusted)
        sharpe = (mean_return - risk_free_rate) / std_return * np.sqrt(252)
        return sharpe
    
    @staticmethod
    def calculate_sortino(returns, target_return=0.0):
        """Calculate Sortino ratio (penalizes downside only)"""
        if len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        downside_returns = [r for r in returns if r < target_return]
        
        if not downside_returns:
            downside_std = 0.0
        else:
            downside_std = np.std(downside_returns)
        
        if downside_std == 0:
            return 0.0
        
        sortino = (mean_return - target_return) / downside_std * np.sqrt(252)
        return sortino
    
    @staticmethod
    def calculate_max_drawdown(equity_curve):
        """Calculate maximum drawdown from equity curve"""
        if not equity_curve:
            return 0.0
        
        cum_max = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - cum_max) / cum_max
        return np.min(drawdown)
    
    @staticmethod
    def calculate_recovery_factor(total_return, max_drawdown):
        """Recovery factor = Total Return / Max Drawdown"""
        if max_drawdown >= 0 or max_drawdown == 0:
            return 0.0
        return total_return / abs(max_drawdown)
    
    @staticmethod
    def calculate_win_rate(trades):
        """Win rate = profitable trades / total trades"""
        if not trades:
            return 0.0
        
        profitable = sum(1 for t in trades if t.get("pnl", 0) > 0)
        return (profitable / len(trades)) * 100.0
    
    @staticmethod
    def calculate_profit_factor(trades):
        """Profit factor = total_wins / total_losses"""
        if not trades:
            return 0.0
        
        wins = sum(max(0, t.get("pnl", 0)) for t in trades)
        losses = abs(sum(min(0, t.get("pnl", 0)) for t in trades))
        
        if losses == 0:
            return 10.0 if wins > 0 else 0.0
        
        return wins / losses


from collections import deque

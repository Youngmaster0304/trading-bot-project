import time
import random
import math
from collections import deque

class MatchingEngine:
    def __init__(self, initial_cash=100000.0, order_size=0.1, fee_rate=0.0005, max_inventory=5.0):
        self.cash = initial_cash
        self.inventory = 0.0 # representing position in BTC
        self.order_size = order_size # Qty per trade
        self.fee_rate = fee_rate
        self.max_inventory = max_inventory
        
        # Profit and Loss metrics
        self.realized_pnl = 0.0
        self.total_fees = 0.0
        self.avg_entry_price = 0.0
        
        self.trades = [] # Keep a log of trades
        
        # Enhanced tracking for analytics
        self.trade_fill_record = deque(maxlen=1000)  # Track fills for adverse selection
        self.spread_history = deque(maxlen=500)  # Track spreads over time
        self.inventory_history = deque(maxlen=500)  # Track inventory over time
        
    def check_fills(self, binance_bid, binance_ask, mm_bid, mm_ask, current_time, dynamic_size=None):
        """
        Matches our MM quotes against the live Top-of-Book.
        In reality, we would wait for market orders to cross our quotes.
        Here we use deterministic logic:
        If market asks <= our bid, we buy (our bid was hit).
        If market bids >= our ask, we sell (our ask was hit).
        """
        fill_occurred = False
        qty = dynamic_size if dynamic_size is not None else self.order_size
        
        # 1. Check if our Ask gets hit (Market buying from us)
        # In a real environment, people buy at the Ask. If the market's current bid equals or is higher than our Ask, it means a buyer would cross the spread. 
        # Since we use Binance data, if binance_bid >= mm_ask, we get filled.
        # Alternatively, we can use a distance probability to add random realistic fills.
        mid_price = (binance_bid + binance_ask) / 2.0
        
        prob_ask_hit = self._arrival_probability(mm_ask, mid_price, side='ask')
        prob_bid_hit = self._arrival_probability(mm_bid, mid_price, side='bid')
        
        if random.random() < prob_ask_hit or binance_bid >= mm_ask:
            self.execute_trade("SELL", mm_ask, qty, current_time, mid_price)
            fill_occurred = True
            
        if random.random() < prob_bid_hit or binance_ask <= mm_bid:
            self.execute_trade("BUY", mm_bid, qty, current_time, mid_price)
            fill_occurred = True
            
        return fill_occurred
        
    def _arrival_probability(self, quote_price, mid_price, side, k=1.5):
        """Simulates Poisson order arrival exponential decay based on distance from mid-price"""
        distance = quote_price - mid_price if side == 'ask' else mid_price - quote_price
        if distance < 0:
            return 1.0 # Crossing the book
        # Small probability to get filled quickly if near mid
        # k is liquidity parameter
        prob = math.exp(-k * distance)
        # Cap to a small reasonable per-tick percentage like 5% if at mid
        return min(0.05, prob * 0.05)
        
    def execute_trade(self, side, price, qty, timestamp, mid_price):
        trade_val = price * qty
        fee_usd = trade_val * self.fee_rate
        self.total_fees += fee_usd
        self.realized_pnl -= fee_usd
        
        if side == "BUY":
            # Update average entry price when buying
            if self.inventory >= 0:
                cost = self.avg_entry_price * self.inventory + trade_val
                self.inventory += qty
                self.avg_entry_price = cost / self.inventory
            else:
                # Covering short
                realized = (self.avg_entry_price - price) * qty
                self.realized_pnl += realized
                self.cash += trade_val
                self.inventory += qty
                if self.inventory == 0:
                    self.avg_entry_price = 0.0
            self.cash -= (trade_val + fee_usd)
        elif side == "SELL":
            if self.inventory <= 0:
                # Adding to short
                cost = self.avg_entry_price * abs(self.inventory) + trade_val
                self.inventory -= qty
                self.avg_entry_price = cost / abs(self.inventory)
                self.cash += (trade_val - fee_usd)
            else:
                # Selling long
                realized = (price - self.avg_entry_price) * qty
                self.realized_pnl += realized
                self.inventory -= qty
                if self.inventory == 0:
                    self.avg_entry_price = 0.0
            self.cash += (trade_val - fee_usd)
            
        trade_record = {
            "timestamp": timestamp,
            "side": side,
            "price": price,
            "qty": qty,
            "fee_usd": fee_usd,
            "inventory_after": self.inventory,
            "realized_pnl_after": self.realized_pnl,
            "mid_price": mid_price
        }
        
        self.trades.append(trade_record)
        self.trade_fill_record.append(trade_record)
        
    def get_unrealized_pnl(self, mid_price):
        if self.inventory == 0:
            return 0.0
        elif self.inventory > 0:
            return (mid_price - self.avg_entry_price) * self.inventory
        else:
            return (self.avg_entry_price - mid_price) * abs(self.inventory)
    
    def log_spread(self, bid_ask_spread, timestamp):
        """Track spread statistics for analysis"""
        self.spread_history.append({
            "timestamp": timestamp,
            "spread": bid_ask_spread
        })
    
    def log_inventory(self, timestamp):
        """Track inventory over time"""
        self.inventory_history.append({
            "timestamp": timestamp,
            "inventory": self.inventory,
            "position_value": self.inventory * self.avg_entry_price if self.avg_entry_price > 0 else 0.0
        })
    
    def get_avg_spread(self):
        """Get average spread over recent history"""
        if not self.spread_history:
            return 0.0
        spreads = [s["spread"] for s in self.spread_history]
        import numpy as np
        return np.mean(spreads) if spreads else 0.0
    
    def get_inventory_utilization(self):
        """Returns inventory as percentage of limit"""
        if self.max_inventory == 0:
            return 0.0
        return abs(self.inventory) / self.max_inventory

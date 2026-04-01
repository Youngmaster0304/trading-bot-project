"""
Volatility Estimator & Regime Detection
Step 8: Real-time volatility computation using rolling window
Step 10: Market regime classification (Calm, Trending, Volatile)
"""

import numpy as np
from collections import deque
import math


class VolatilityEstimator:
    """
    Computes realized volatility from rolling windows of returns.
    Updates every N ticks (default ~10 seconds in production).
    """
    
    def __init__(self, window_size=100, min_returns=20):
        """
        window_size: Number of returns to keep for volatility calculation
        min_returns: Minimum datapoints before computing volatility
        """
        self.window_size = window_size
        self.min_returns = min_returns
        self.returns = deque(maxlen=window_size)
        self.prices = deque(maxlen=window_size + 1)
        self.volatility = 0.0
        self.mean_return = 0.0
        
    def add_price(self, price):
        """Add a new price tick and update volatility estimates"""
        self.prices.append(price)
        
        # Calculate return only if we have at least 2 prices
        if len(self.prices) >= 2:
            prev_price = self.prices[-2]
            ret = math.log(price / prev_price) if prev_price > 0 else 0.0
            self.returns.append(ret)
            
            # Calculate realized volatility once we have enough data
            if len(self.returns) >= self.min_returns:
                self.volatility = np.std(self.returns)
                self.mean_return = np.mean(self.returns)
        
        return self.volatility
    
    def get_volatility(self):
        """Returns current realized volatility (annualized approximation)"""
        if len(self.returns) < self.min_returns:
            return 0.01  # Default low volatility while warming up
        return max(self.volatility, 0.001)  # Floor at 0.1%
    
    def get_vol_percentile(self, historical_vol_list):
        """
        Returns volatility as percentile among recent history
        Useful for regime detection ranking
        """
        if not historical_vol_list:
            return 50.0
        return np.percentile(historical_vol_list, np.searchsorted(sorted(historical_vol_list), self.volatility) * 100 / len(historical_vol_list))


class RegimeDetector:
    """
    Classifies market regime into 3 states:
    🟢 CALM: Low volatility, tight spreads, normal sizing
    🟡 TRENDING: Medium volatility + strong directional bias (OFI), wider spreads
    🔴 VOLATILE: High volatility or extreme OFI, defensive positioning
    """
    
    def __init__(self, vol_window=200, ofi_window=100, calm_threshold=0.5, 
                 trending_threshold=1.5, volatile_threshold=2.5):
        """
        vol_window: Historical volatility samples to track
        ofi_window: Historical OFI samples to track
        Thresholds define regime boundaries (relative to rolling mean)
        """
        self.vol_window = deque(maxlen=vol_window)
        self.ofi_window = deque(maxlen=ofi_window)
        
        self.calm_threshold = calm_threshold
        self.trending_threshold = trending_threshold
        self.volatile_threshold = volatile_threshold
        
        self.regime = "CALM"  # Default state
        self.regime_confidence = 0.0
        
    def add_observation(self, volatility, ofi):
        """
        Add new market observation
        volatility: Current realized volatility
        ofi: Order flow imbalance (-1.0 to 1.0)
        """
        self.vol_window.append(volatility)
        self.ofi_window.append(abs(ofi))  # Use absolute OFI for momentum strength
        
        # Update regime if we have enough history
        if len(self.vol_window) >= 10:
            self._classify_regime()
    
    def _classify_regime(self):
        """Classify regime based on volatility & OFI patterns"""
        if len(self.vol_window) < 10:
            self.regime = "CALM"
            self.regime_confidence = 0.0
            return
        
        # Calculate rolling statistics
        vols = np.array(list(self.vol_window))
        ofis = np.array(list(self.ofi_window))
        
        current_vol = vols[-1]
        mean_vol = np.mean(vols)
        std_vol = np.std(vols)
        vol_zscore = (current_vol - mean_vol) / max(std_vol, 0.0001)
        
        current_ofi = ofis[-1]
        mean_ofi = np.mean(ofis)
        std_ofi = np.std(ofis)
        ofi_zscore = (current_ofi - mean_ofi) / max(std_ofi, 0.0001)
        
        # Regime decision logic
        if vol_zscore > self.volatile_threshold or ofi_zscore > self.volatile_threshold:
            self.regime = "VOLATILE"
            self.regime_confidence = min(100.0, (vol_zscore + ofi_zscore) / 2.0 * 50.0)
        elif vol_zscore > self.trending_threshold or ofi_zscore > self.trending_threshold:
            self.regime = "TRENDING"
            self.regime_confidence = min(100.0, (vol_zscore + ofi_zscore) / 2.0 * 50.0)
        else:
            self.regime = "CALM"
            self.regime_confidence = max(0.0, 100.0 - vol_zscore * 30.0)
    
    def get_regime(self):
        """Returns current regime: 'CALM', 'TRENDING', 'VOLATILE'"""
        return self.regime
    
    def get_regime_confidence(self):
        """Returns confidence in regime classification (0-100)"""
        return max(0.0, min(100.0, self.regime_confidence))
    
    def get_spread_multiplier(self):
        """
        Returns spread multiplier based on regime:
        CALM: 1.0x (tight spreads)
        TRENDING: 1.5x (widened spreads)
        VOLATILE: 2.5x (very wide spreads for protection)
        """
        regime_map = {
            "CALM": 1.0,
            "TRENDING": 1.5,
            "VOLATILE": 2.5
        }
        return regime_map.get(self.regime, 1.0)
    
    def get_inventory_limit_multiplier(self):
        """
        Returns inventory limit multiplier based on regime:
        CALM: 1.0x (normal risk)
        TRENDING: 0.7x (reduced due to directional risk)
        VOLATILE: 0.3x (minimal inventory during high volatility)
        """
        regime_map = {
            "CALM": 1.0,
            "TRENDING": 0.7,
            "VOLATILE": 0.3
        }
        return regime_map.get(self.regime, 1.0)
    
    def get_quote_size_multiplier(self):
        """
        Returns quote size multiplier based on regime:
        CALM: 1.5x (aggressive quoting)
        TRENDING: 1.0x (normal sizing)
        VOLATILE: 0.5x (conservative sizing)
        """
        regime_map = {
            "CALM": 1.5,
            "TRENDING": 1.0,
            "VOLATILE": 0.5
        }
        return regime_map.get(self.regime, 1.0)
    
    def get_regime_color(self):
        """Returns color indicator for visualization"""
        color_map = {
            "CALM": "🟢",
            "TRENDING": "🟡",
            "VOLATILE": "🔴"
        }
        return color_map.get(self.regime, "⚪")


class MicropriceCalculator:
    """
    Step 9: Compute microprice and detect divergence from mid-price
    microprice = (ask_vol × bid + bid_vol × ask) / (bid_vol + ask_vol)
    """
    
    def __init__(self, window_size=50):
        self.window_size = window_size
        self.microprice_history = deque(maxlen=window_size)
        self.midprice_history = deque(maxlen=window_size)
        self.divergence_history = deque(maxlen=window_size)
        self.current_microprice = 0.0
        self.current_divergence = 0.0
        
    def add_market_state(self, bid, ask, bid_volume, ask_volume):
        """
        Calculate microprice from order book state
        """
        mid_price = (bid + ask) / 2.0
        
        # Microprice formula: weighted average by volume
        total_vol = bid_volume + ask_volume
        if total_vol > 0:
            self.current_microprice = (ask_volume * bid + bid_volume * ask) / total_vol
        else:
            self.current_microprice = mid_price
        
        self.microprice_history.append(self.current_microprice)
        self.midprice_history.append(mid_price)
        
        # Calculate divergence as percentage
        divergence = (self.current_microprice - mid_price) / mid_price * 100.0 if mid_price > 0 else 0.0
        self.current_divergence = divergence
        self.divergence_history.append(divergence)
    
    def get_microprice(self):
        """Returns current microprice"""
        return self.current_microprice
    
    def get_divergence(self):
        """Returns microprice divergence from mid (in basis points)"""
        return self.current_divergence
    
    def get_divergence_signal(self):
        """
        Returns adjustment signal for reservation price:
        Positive signal = microprice above mid (buyers more aggressive)
        Negative signal = microprice below mid (sellers more aggressive)
        Used to reduce adverse selection
        """
        if len(self.divergence_history) < 5:
            return 0.0
        
        # Use recent divergence as signal
        recent_div = np.mean(list(self.divergence_history)[-5:])
        # Normalize to small adjustment factor
        return recent_div / 100.0  # Convert bps to decimal adjustment

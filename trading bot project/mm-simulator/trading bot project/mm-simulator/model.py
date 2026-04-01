import math
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

class MLPredictor:
    def __init__(self, window_size=300):
        self.window_size = window_size
        self.model = Ridge(alpha=1.0)
        self.features = [] # [ofi, dynamic_vol, inventory]
        self.targets = []  # forward 10-tick microprice return
        self.recent_data = [] # Buffer for forward lookahead
        self.is_trained = False
        
    def add_tick(self, ofi, dynamic_vol, inventory, microprice):
        self.recent_data.append({
            'ofi': ofi,
            'dynamic_vol': dynamic_vol,
            'inventory': inventory,
            'microprice': microprice
        })
        
        if len(self.recent_data) > 10:
            past_tick = self.recent_data[-11]
            past_micro = past_tick['microprice']
            ret = (microprice - past_micro) / past_micro if past_micro > 0 else 0.0
            
            x_vec = [past_tick['ofi'], past_tick['dynamic_vol'], past_tick['inventory']]
            
            self.features.append(x_vec)
            self.targets.append(ret)
            
            if len(self.features) > self.window_size:
                self.features.pop(0)
                self.targets.pop(0)
                
            # Train model continuously if we have enough data (50 ticks)
            if len(self.features) > 50:
                self.model.fit(self.features, self.targets)
                self.is_trained = True

        if len(self.recent_data) > 20:
            self.recent_data.pop(0)
            
    def predict_alpha(self, current_ofi, current_vol, current_inventory):
        """
        Predict alpha with dynamic confidence scoring.
        Confidence is based on: data maturity + model R² score + prediction stability
        """
        try:
            # Phase 1: Warm-up phase (< 50 data points) - gradually increase confidence
            data_progress = min(len(self.features) / 50.0, 1.0)  # 0 to 1 as we approach 50 points
            
            if not self.is_trained:
                # During warm-up: return 0 prediction with growing confidence
                warmup_confidence = data_progress * 40.0  # Reaches 40% at 50 points
                return 0.0, warmup_confidence
            
            x_pred = np.array([[current_ofi, current_vol, current_inventory]])
            pred_return = self.model.predict(x_pred)[0]
            
            # Phase 2: Model trained - calculate R² score as confidence base
            try:
                y_pred = self.model.predict(np.array(self.features))
                # Calculate R² score (coefficient of determination)
                ss_res = np.sum((np.array(self.targets) - y_pred) ** 2)
                ss_tot = np.sum((np.array(self.targets) - np.mean(self.targets)) ** 2)
                r2_score = max(0.0, 1.0 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0
            except:
                r2_score = 0.0
            
            # Phase 3: Combine R² with prediction signal strength
            # Stronger signals (larger |pred_return|) indicate clearer market patterns
            signal_strength = min(abs(pred_return) * 10000.0, 1.0)  # Cap at 1.0 (100%)
            
            # Confidence = 50% base (model trained) + 30% from R² + 20% from signal
            base_confidence = 50.0
            r2_contribution = r2_score * 30.0  # Up to 30%
            signal_contribution = signal_strength * 20.0  # Up to 20%
            
            confidence = min(base_confidence + r2_contribution + signal_contribution, 100.0)
            
            # Boost confidence as more data accumulates (even with low R²)
            data_maturity_boost = data_progress * 10.0  # Up to 10% boost
            confidence = min(confidence + data_maturity_boost, 100.0)
            
            return pred_return, confidence
            
        except Exception as e:
            return 0.0, 0.0

class AvellanedaStoikovModel:
    def __init__(self, risk_aversion=0.1, liquidity_density=1.5, volatility=0.5, terminal_time=1.0):
        # gamma
        self.risk_aversion = risk_aversion
        # k
        self.liquidity_density = liquidity_density
        # sigma
        self.volatility = volatility
        # T (using 1.0 for continuous operation approximation)
        self.terminal_time = terminal_time
        
    def get_quotes(self, mid_price, inventory, dynamic_vol=None, ofi=0.0, ofi_weight=0.0, ai_alpha_prediction=0.0, regime_multiplier=1.0, microprice_signal=0.0):
        """
        Calculates the Reservation Price and Optimal Spread based on Avellaneda-Stoikov math,
        with added AI prediction signals, regime adjustments, and microprice divergence handling.
        
        Args:
            regime_multiplier: Spread multiplier based on market regime (1.0x for calm, 1.5x for trending, 2.5x for volatile)
            microprice_signal: Adjustment signal from microprice divergence to reduce adverse selection
        """
        vol = dynamic_vol if dynamic_vol is not None else self.volatility
        
        # 1. Reservation Price
        # r = s - q * gamma * sigma^2 * T + OFI_offset + AI_prediction + microprice_signal
        reservation_price = mid_price - (inventory * self.risk_aversion * (vol ** 2) * self.terminal_time)
        reservation_price += (ofi * ofi_weight)
        
        # Inject the absolute scalar magnitude of the forward return into the quote offset
        reservation_price += (ai_alpha_prediction * mid_price)
        
        # Add microprice divergence signal to reduce adverse selection
        reservation_price += (microprice_signal * mid_price)
        
        # 2. Optimal Spread with regime adjustment
        # delta = gamma * sigma^2 * T + (2/gamma) * ln(1 + gamma/k)
        vol_term = self.risk_aversion * (vol ** 2) * self.terminal_time
        log_term = (2 / self.risk_aversion) * math.log(1 + (self.risk_aversion / self.liquidity_density))
        optimal_spread = vol_term + log_term
        
        # Apply regime multiplier (wider spreads during volatile regimes)
        optimal_spread *= regime_multiplier
        
        # We also want to calculate our Bid and Ask
        bid_price = reservation_price - (optimal_spread / 2)
        ask_price = reservation_price + (optimal_spread / 2)
        
        return {
            "reservation_price": reservation_price,
            "optimal_spread": optimal_spread,
            "bid": bid_price,
            "ask": ask_price
        }

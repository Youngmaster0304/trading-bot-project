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
        if not self.is_trained:
            return 0.0, 0.0
        
        try:
            x_pred = np.array([[current_ofi, current_vol, current_inventory]])
            pred_return = self.model.predict(x_pred)[0]
            # Convert decimal return to 0-100% confidence scale
            confidence = min(max(abs(pred_return) * 100000.0, 0.0), 100.0) 
            return pred_return, confidence
        except Exception:
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
        
    def get_quotes(self, mid_price, inventory, dynamic_vol=None, ofi=0.0, ofi_weight=0.0, ai_alpha_prediction=0.0):
        """
        Calculates the Reservation Price and Optimal Spread based on Avellaneda-Stoikov math,
        with added AI prediction signals.
        """
        vol = dynamic_vol if dynamic_vol is not None else self.volatility
        
        # 1. Reservation Price
        # r = s - q * gamma * sigma^2 * T + OFI_offset + AI_prediction
        reservation_price = mid_price - (inventory * self.risk_aversion * (vol ** 2) * self.terminal_time)
        reservation_price += (ofi * ofi_weight)
        
        # Inject the absolute scalar magnitude of the forward return into the quote offset
        # e.g., if pred_return = 0.001 (0.1%), and mid is 68000 -> shifted up $68
        reservation_price += (ai_alpha_prediction * mid_price)
        
        # 2. Optimal Spread
        # delta = gamma * sigma^2 * T + (2/gamma) * ln(1 + gamma/k)
        vol_term = self.risk_aversion * (vol ** 2) * self.terminal_time
        log_term = (2 / self.risk_aversion) * math.log(1 + (self.risk_aversion / self.liquidity_density))
        optimal_spread = vol_term + log_term
        
        # We also want to calculate our Bid and Ask
        bid_price = reservation_price - (optimal_spread / 2)
        ask_price = reservation_price + (optimal_spread / 2)
        
        return {
            "reservation_price": reservation_price,
            "optimal_spread": optimal_spread,
            "bid": bid_price,
            "ask": ask_price
        }

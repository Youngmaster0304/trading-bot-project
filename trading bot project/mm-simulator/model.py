import math

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
        
    def get_quotes(self, mid_price, inventory, dynamic_vol=None, ofi=0.0, ofi_weight=0.0):
        """
        Calculates the Reservation Price and Optimal Spread based on Avellaneda-Stoikov math,
        with added Alpha signals (OFI & Dynamic Volatility).
        """
        vol = dynamic_vol if dynamic_vol is not None else self.volatility
        
        # 1. Reservation Price
        # r = s - q * gamma * sigma^2 * T + OFI_offset
        reservation_price = mid_price - (inventory * self.risk_aversion * (vol ** 2) * self.terminal_time)
        reservation_price += (ofi * ofi_weight)
        
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

"""
Dynamic Quote Sizing (Step 12)
Size quotes based on confidence, volatility, and inventory constraints
Uses Kelly criterion-inspired approach for position sizing
"""

import math


class DynamicSizer:
    """
    Calculates optimal quote size dynamically based on:
    - Confidence level (OFI + volatility)
    - Inventory position
    - Risk limits
    - Market regime
    """
    
    def __init__(self, base_size=0.1, max_size=1.0):
        """
        base_size: Default quote size
        max_size: Maximum allowed size per quote
        """
        self.base_size = base_size
        self.max_size = max_size
    
    def calculate_size(self, confidence, volatility, inventory, inventory_limit,
                      ofi, regime_multiplier=1.0, regime="CALM"):
        """
        Calculate optimal quote size using multiple factors
        
        Args:
            confidence: Prediction confidence (0-100)
            volatility: Current realized volatility
            inventory: Current inventory position
            inventory_limit: Maximum allowed inventory
            ofi: Order flow imbalance (-1.0 to 1.0)
            regime_multiplier: Size adjustment based on regime
            regime: Current market regime
        
        Returns:
            Dictionary with:
            - size: Recommended quote size
            - reasoning: Explanation of sizing decision
            - kelly_fraction: Kelly-inspired fraction
            - inventory_discount: Inventory adjustment factor
        """
        
        # 1. Confidence component (0 to 1)
        confidence_factor = min(confidence / 100.0, 1.0) if confidence > 0 else 0.3
        
        # 2. Volatility component (inverse - higher vol = smaller size)
        # Normalize volatility: assume 1% is "normal"
        vol_discount = 1.0 / (1.0 + volatility * 10.0)
        
        # 3. Kelly Criterion-inspired sizing
        # Simplified Kelly: f* = (p - q) / odds = confidence / volatility
        # Where p = win probability, q = loss probability
        kelly_fraction = 0.0
        if volatility > 0.0001:
            kelly_fraction = min(confidence_factor, volatility)  # Cap at volatility estimate
            # Be conservative - use 25% of full Kelly
            kelly_fraction *= 0.25
        
        # 4. Inventory utilization factor
        # penalize sizing if we're already loaded (long or short)
        inventory_utilization = abs(inventory) / max(inventory_limit, 0.01)
        
        # If we're at 80%+ inventory, heavily discount
        if inventory_utilization > 0.8:
            inventory_discount = 0.2
        elif inventory_utilization > 0.5:
            inventory_discount = 0.5 + (0.5 * (1.0 - inventory_utilization))
        else:
            inventory_discount = 1.0
        
        # Inventory direction bias: reduce size if inventory is skewed same direction as OFI
        # If we're long (inventory > 0) and OFI is positive, reduce size (risky)
        if inventory > 0 and ofi > 0.3:
            inventory_discount *= 0.7
        elif inventory < 0 and ofi < -0.3:
            inventory_discount *= 0.7
        
        # 5. Regime impact (already multiplied in downstream logic)
        
        # Combine all factors
        size = self.base_size * confidence_factor * vol_discount * kelly_fraction * inventory_discount * regime_multiplier
        size = min(size, self.max_size)
        size = max(size, self.base_size * 0.25)  # Floor at 25% of base
        
        # Build reasoning string
        reasoning_parts = []
        if confidence_factor < 0.5:
            reasoning_parts.append(f"Low confidence ({confidence:.1f}%)")
        if vol_discount < 0.7:
            reasoning_parts.append(f"High volatility ({volatility:.4f})")
        if inventory_discount < 0.8:
            reasoning_parts.append(f"High inventory util. ({inventory_utilization:.1%})")
        if regime == "VOLATILE":
            reasoning_parts.append("Volatile regime")
        
        reasoning = " | ".join(reasoning_parts) if reasoning_parts else "Optimal conditions"
        
        return {
            "size": round(size, 4),
            "reasoning": reasoning,
            "kelly_fraction": kelly_fraction,
            "inventory_discount": inventory_discount,
            "confidence_factor": confidence_factor,
            "vol_discount": vol_discount,
            "components": {
                "confidence": confidence,
                "volatility": volatility,
                "inventory": inventory,
                "inventory_limit": inventory_limit,
                "ofi": ofi
            }
        }
    
    def get_asymmetric_size(self, base_size, side, inventory, ofi):
        """
        Returns asymmetric sizing: favor buying when we're short, selling when we're long
        
        This improves market-making by pushing us back to neutral faster
        """
        inventory_skew = inventory / 10.0  # Normalize
        
        if side == "BUY":
            # When buying, reduce size if already long
            if inventory > 0:
                size = base_size * max(0.5, 1.0 - (inventory_skew * 0.5))
            else:
                size = base_size * min(1.5, 1.0 + abs(inventory_skew))
        else:  # SELL
            # When selling, reduce size if already short
            if inventory < 0:
                size = base_size * max(0.5, 1.0 - (abs(inventory_skew) * 0.5))
            else:
                size = base_size * min(1.5, 1.0 + inventory_skew)
        
        return max(base_size * 0.25, min(base_size * 2.0, size))
    
    @staticmethod
    def optimal_bid_ask_size(total_liquidity_budget, confidence, volatility):
        """
        Given a total liquidity budget, split it between bid and ask
        Higher confidence = more aggressive sizing
        """
        if volatility < 0.001:
            volatility = 0.001
        
        confidence_multiplier = 1.0 + (confidence / 100.0) * 0.5
        aggressive_factor = confidence_multiplier / (1.0 + volatility * 5.0)
        
        # Allocate more to the confident side
        size = total_liquidity_budget * aggressive_factor
        return min(size, total_liquidity_budget)


class QuoteSizingMetrics:
    """Track and analyze quote sizing decisions over time"""
    
    def __init__(self, window_size=1000):
        self.window_size = window_size
        self.sizing_history = []
        self.fill_rates = []  # Track if quotes with certain sizes got filled
        
    def log_size_decision(self, size, reason, confidence, vol, inventory_util):
        """Log a sizing decision"""
        self.sizing_history.append({
            "size": size,
            "reason": reason,
            "confidence": confidence,
            "vol": vol,
            "inventory_util": inventory_util
        })
        
        if len(self.sizing_history) > self.window_size:
            self.sizing_history.pop(0)
    
    def log_fill(self, size, filled):
        """Log whether a quote with given size got filled"""
        self.fill_rates.append({
            "size": size,
            "filled": filled
        })
        
        if len(self.fill_rates) > self.window_size:
            self.fill_rates.pop(0)
    
    def get_sizing_summary(self):
        """Return statistics about sizing decisions"""
        if not self.sizing_history:
            return {}
        
        sizes = [h["size"] for h in self.sizing_history]
        confidences = [h["confidence"] for h in self.sizing_history]
        
        return {
            "avg_size": sum(sizes) / len(sizes),
            "max_size": max(sizes),
            "min_size": min(sizes),
            "avg_confidence": sum(confidences) / len(confidences),
            "total_decisions": len(self.sizing_history)
        }
    
    def get_fill_rate_by_size(self, size_bucket=0.05):
        """Analyze fill rates by size buckets"""
        if not self.fill_rates:
            return {}
        
        buckets = {}
        for record in self.fill_rates:
            size = record["size"]
            bucket_key = round(size / size_bucket) * size_bucket
            
            if bucket_key not in buckets:
                buckets[bucket_key] = {"total": 0, "filled": 0}
            
            buckets[bucket_key]["total"] += 1
            if record["filled"]:
                buckets[bucket_key]["filled"] += 1
        
        # Calculate fill rates
        fill_rates = {
            k: v["filled"] / v["total"] for k, v in buckets.items()
        }
        
        return fill_rates

class RiskManager:
    def __init__(self, max_inventory=5.0, max_drawdown=-1000.0):
        self.max_inventory = max_inventory
        self.max_drawdown = max_drawdown
        self.limit_hit = False
        self.limit_reason = ""
        
    def check_limits(self, inventory, unrealized_pnl, realized_pnl):
        """
        Evaluates risk parameters. If limits exceeded, halts the quoting engine.
        Returns (True/False to halt, Reason for halt)
        """
        if self.limit_hit:
            return True, self.limit_reason
            
        # Inventory limit (absolute value)
        if abs(inventory) >= self.max_inventory:
            self.limit_hit = True
            self.limit_reason = f"Inventory Limit Exceeded: {inventory:.2f} > {self.max_inventory:.2f}"
            return True, self.limit_reason
            
        # Drawdown limit
        total_pnl = realized_pnl + unrealized_pnl
        if total_pnl <= self.max_drawdown:
            self.limit_hit = True
            self.limit_reason = f"Max Drawdown Exceeded: PnL {total_pnl:.2f} <= {self.max_drawdown:.2f}"
            return True, self.limit_reason
            
        return False, ""

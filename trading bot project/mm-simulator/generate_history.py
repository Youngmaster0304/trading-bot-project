import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_synthetic_data(num_ticks=10000, start_price=68000.0, output_file="history.csv"):
    np.random.seed(42)
    
    timestamps = [datetime.now() + timedelta(milliseconds=100 * i) for i in range(num_ticks)]
    
    # 1. Simulate Price Random Walk with local momentum
    returns = np.random.normal(loc=0.0, scale=0.00001, size=num_ticks)
    
    # Add a sudden volatility regime shift halfway through
    midpoint = num_ticks // 2
    returns[midpoint:midpoint+1000] = np.random.normal(loc=0.0, scale=0.00005, size=1000)
    
    price_path = start_price * np.exp(np.cumsum(returns))
    
    # 2. Simulate Spread
    # Normal spread is 0.1, during vol it blows out to 1.0 - 5.0
    spread = np.clip(np.random.normal(loc=0.5, scale=0.2, size=num_ticks), 0.1, 10.0)
    spread[midpoint:midpoint+1000] = np.clip(np.random.normal(loc=2.0, scale=1.0, size=1000), 0.5, 20.0)
    
    best_bids = price_path - (spread / 2)
    best_asks = price_path + (spread / 2)
    
    # 3. Simulate OFI (Auto-regressive process to simulate sticky momentum)
    # OFI sits between -1.0 and 1.0
    ofi = np.zeros(num_ticks)
    for i in range(1, num_ticks):
        ofi[i] = 0.85 * ofi[i-1] + np.random.normal(0, 0.2)
    ofi = np.clip(ofi, -1.0, 1.0)
    
    # Push price returns slightly towards OFI direction (to give strategy an edge)
    price_adjust = np.zeros(num_ticks)
    for i in range(1, num_ticks):
        price_adjust[i] = price_adjust[i-1] + (ofi[i] * 0.05)
        
    price_path = price_path + price_adjust
    best_bids = price_path - (spread / 2)
    best_asks = price_path + (spread / 2)
    
    # 4. Microprice diverges from mid depending on OFI
    microprice = price_path + (ofi * spread * 0.4)
    
    # 5. Dynamic Volatility (Rolling standard deviation of returns)
    df = pd.DataFrame({
        'timestamp': timestamps,
        'best_bid': best_bids,
        'best_ask': best_asks,
        'mid_price': price_path,
        'microprice': microprice,
        'ofi': ofi
    })
    
    # Calculate rolling dynamic vol exactly like the dashboard
    df['dynamic_vol'] = df['mid_price'].pct_change().rolling(60).std() * 100000.0
    df['dynamic_vol'].fillna(5.0, inplace=True)
    df['dynamic_vol'] = df['dynamic_vol'].clip(lower=0.1)
    
    # Add the long ma
    df['long_vol_ma'] = df['dynamic_vol'].rolling(300).mean().fillna(5.0)
    
    df.to_csv(output_file, index=False)
    print(f"✅ Generated {num_ticks} synthetic tick rows perfectly mapping to Phase 4 physics in {output_file}")

if __name__ == "__main__":
    generate_synthetic_data()

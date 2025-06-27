#!/usr/bin/env python3
"""
Check data ranges for BTC/USDT and ETH/USDT to see what needs to be updated.
"""

import pandas as pd
from pathlib import Path

def check_data_range(pair, timeframe):
    """Check the data range for a specific pair and timeframe."""
    data_dir = Path("user_data/data/binance")
    filename = f"{pair.replace('/', '_')}-{timeframe}.feather"
    filepath = data_dir / filename
    
    if not filepath.exists():
        print(f"No data found for {pair} {timeframe}")
        return None
    
    try:
        df = pd.read_feather(filepath)
        df['date'] = pd.to_datetime(df['date'])
        start_date = df['date'].min()
        end_date = df['date'].max()
        total_rows = len(df)
        
        print(f"{pair} {timeframe}:")
        print(f"  Start: {start_date}")
        print(f"  End: {end_date}")
        print(f"  Rows: {total_rows:,}")
        print(f"  Duration: {(end_date - start_date).days} days")
        print()
        
        return {
            'pair': pair,
            'timeframe': timeframe,
            'start': start_date,
            'end': end_date,
            'rows': total_rows,
            'duration_days': (end_date - start_date).days
        }
    except Exception as e:
        print(f"Error reading {pair} {timeframe}: {e}")
        return None

def main():
    """Check data ranges for both BTC/USDT and ETH/USDT across all timeframes."""
    pairs = ['BTC/USDT', 'ETH/USDT']
    timeframes = ['5m', '15m', '1h', '4h', '1d']
    
    results = {}
    
    for pair in pairs:
        results[pair] = {}
        print(f"=== {pair} ===")
        for timeframe in timeframes:
            result = check_data_range(pair, timeframe)
            if result:
                results[pair][timeframe] = result
        print()
    
    # Compare 5m data specifically
    if 'BTC/USDT' in results and 'ETH/USDT' in results:
        if '5m' in results['BTC/USDT'] and '5m' in results['ETH/USDT']:
            btc_5m = results['BTC/USDT']['5m']
            eth_5m = results['ETH/USDT']['5m']
            
            print("=== 5m Data Comparison ===")
            print(f"BTC/USDT starts: {btc_5m['start']}")
            print(f"ETH/USDT starts: {eth_5m['start']}")
            
            if btc_5m['start'] < eth_5m['start']:
                gap_days = (eth_5m['start'] - btc_5m['start']).days
                print(f"ETH/USDT is missing {gap_days} days of earlier data")
                print(f"Need to download from {btc_5m['start']} to {eth_5m['start']}")
            elif eth_5m['start'] < btc_5m['start']:
                gap_days = (btc_5m['start'] - eth_5m['start']).days
                print(f"BTC/USDT is missing {gap_days} days of earlier data")
            else:
                print("Both pairs start at the same time")
                
            print(f"BTC/USDT rows: {btc_5m['rows']:,}")
            print(f"ETH/USDT rows: {eth_5m['rows']:,}")
            row_diff = abs(btc_5m['rows'] - eth_5m['rows'])
            print(f"Row difference: {row_diff:,}")

if __name__ == "__main__":
    main()

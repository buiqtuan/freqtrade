import pandas as pd
import numpy as np
from pathlib import Path

def analyze_trend_conditions():
    """
    Analyze the trend conditions to understand why no trades were generated
    """
    # Load the data files
    data_dir = Path("d:/workspace/bots/freqtrade/user_data/data/binance")
    
    pairs = ['BTC_USDT', 'ETH_USDT']
    timeframes = ['5m', '1d', '4h']
    
    print("=== TREND CONDITION ANALYSIS ===")
    print("Checking why the multi-timeframe strategy generated no trades")
    print()
    
    for pair in pairs:
        print(f"📊 Analyzing {pair.replace('_', '/')}")
        print("-" * 40)
        
        # Load data for different timeframes
        data = {}
        for tf in timeframes:
            file_path = data_dir / f"{pair}-{tf}.feather"
            if file_path.exists():
                df = pd.read_feather(file_path)
                df['date'] = pd.to_datetime(df['date'])
                data[tf] = df
                print(f"✓ Loaded {tf} data: {len(df)} candles")
            else:
                print(f"✗ Missing {tf} data")
        
        if not data:
            continue
        
        # Analyze December 2024 period
        start_date = '2024-12-01'
        end_date = '2024-12-27'
        
        print(f"\nAnalyzing period: {start_date} to {end_date}")
        
        # Check 1D trend
        if '1d' in data:
            df_1d = data['1d']
            df_1d = df_1d[(df_1d['date'] >= start_date) & (df_1d['date'] <= end_date)]
            
            # Calculate EMAs
            df_1d['ema_20'] = df_1d['close'].ewm(span=20).mean()
            df_1d['ema_50'] = df_1d['close'].ewm(span=50).mean()
            df_1d['trend_up'] = df_1d['ema_20'] > df_1d['ema_50']
            
            uptrend_days = df_1d['trend_up'].sum()
            total_days = len(df_1d)
            
            print(f"1D Timeframe:")
            print(f"  - Uptrend days: {uptrend_days}/{total_days} ({uptrend_days/total_days*100:.1f}%)")
            print(f"  - Last 5 days trend: {df_1d['trend_up'].tail().tolist()}")
        
        # Check 4H trend
        if '4h' in data:
            df_4h = data['4h']
            df_4h = df_4h[(df_4h['date'] >= start_date) & (df_4h['date'] <= end_date)]
            
            # Calculate EMAs
            df_4h['ema_20'] = df_4h['close'].ewm(span=20).mean()
            df_4h['ema_50'] = df_4h['close'].ewm(span=50).mean()
            df_4h['trend_up'] = (df_4h['ema_20'] > df_4h['ema_50']) & (df_4h['close'] > df_4h['ema_20'])
            
            uptrend_periods = df_4h['trend_up'].sum()
            total_periods = len(df_4h)
            
            print(f"4H Timeframe:")
            print(f"  - Uptrend periods: {uptrend_periods}/{total_periods} ({uptrend_periods/total_periods*100:.1f}%)")
            print(f"  - Last 10 periods trend: {df_4h['trend_up'].tail(10).tolist()}")
        
        # Check alignment
        if '1d' in data and '4h' in data:
            # Find periods where both timeframes align
            # Resample 4h to daily to compare
            df_4h_daily = df_4h.set_index('date').resample('D')['trend_up'].last()
            df_1d_indexed = df_1d.set_index('date')['trend_up']
            
            # Find common dates
            common_dates = df_4h_daily.index.intersection(df_1d_indexed.index)
            if len(common_dates) > 0:
                aligned_uptrend = (df_1d_indexed[common_dates] & df_4h_daily[common_dates]).sum()
                print(f"Trend Alignment:")
                print(f"  - Both 1D and 4H uptrend: {aligned_uptrend}/{len(common_dates)} days ({aligned_uptrend/len(common_dates)*100:.1f}%)")
            
        print()
    
    print("🔍 ANALYSIS SUMMARY:")
    print("If both timeframes show low uptrend percentages, this explains")
    print("why the multi-timeframe strategy generated no trades.")
    print()
    print("💡 RECOMMENDATIONS:")
    print("1. Use a longer time period that includes more trending markets")
    print("2. Relax the trend alignment requirements")
    print("3. Add neutral/ranging market conditions")
    print("4. Test with different trend strength thresholds")

if __name__ == "__main__":
    analyze_trend_conditions()

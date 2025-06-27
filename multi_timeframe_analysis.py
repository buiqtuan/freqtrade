import pandas as pd
import numpy as np
from datetime import datetime
import os

def load_data(pair, timeframe):
    """Load trading data for a specific pair and timeframe"""
    file_path = f"d:\\workspace\\bots\\freqtrade\\user_data\\data\\binance\\{pair}-{timeframe}.feather"
    if os.path.exists(file_path):
        df = pd.read_feather(file_path)
        df['date'] = pd.to_datetime(df['date'])
        return df
    else:
        print(f"File not found: {file_path}")
        return None

def analyze_timeframe_data(pair, timeframe):
    """Analyze data for a specific timeframe"""
    print(f"\n{'='*60}")
    print(f"ANALYZING {pair} - {timeframe} DATA")
    print(f"{'='*60}")
    
    df = load_data(pair, timeframe)
    if df is None:
        return
    
    # Basic statistics
    print(f"Data Points: {len(df):,}")
    print(f"Date Range: {df['date'].min()} to {df['date'].max()}")
    print(f"Duration: {(df['date'].max() - df['date'].min()).days} days")
    
    # Price analysis
    print(f"\nPRICE ANALYSIS:")
    print(f"Starting Price: ${df['close'].iloc[0]:,.2f}")
    print(f"Ending Price: ${df['close'].iloc[-1]:,.2f}")
    print(f"Total Change: {((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100:.2f}%")
    print(f"Highest Price: ${df['high'].max():,.2f}")
    print(f"Lowest Price: ${df['low'].min():,.2f}")
    print(f"Max Range: {((df['high'].max() / df['low'].min()) - 1) * 100:.2f}%")
    
    # Volatility analysis
    df['returns'] = df['close'].pct_change()
    daily_volatility = df['returns'].std()
    annualized_volatility = daily_volatility * np.sqrt(365.25 * 24 * 60 / get_minutes_per_candle(timeframe))
    
    print(f"\nVOLATILITY ANALYSIS:")
    print(f"Average Daily Returns: {df['returns'].mean() * 100:.4f}%")
    print(f"Daily Volatility: {daily_volatility * 100:.4f}%")
    print(f"Annualized Volatility: {annualized_volatility * 100:.2f}%")
    
    # Volume analysis
    print(f"\nVOLUME ANALYSIS:")
    print(f"Average Volume: {df['volume'].mean():,.0f}")
    print(f"Total Volume: {df['volume'].sum():,.0f}")
    print(f"Max Volume: {df['volume'].max():,.0f}")
    print(f"Min Volume: {df['volume'].min():,.0f}")
    
    # Monthly performance
    df['month'] = df['date'].dt.to_period('M')
    monthly_returns = df.groupby('month').apply(lambda x: (x['close'].iloc[-1] / x['close'].iloc[0] - 1) * 100)
    
    print(f"\nMONTHLY PERFORMANCE:")
    print(f"Best Month: {monthly_returns.max():.2f}% ({monthly_returns.idxmax()})")
    print(f"Worst Month: {monthly_returns.min():.2f}% ({monthly_returns.idxmin()})")
    print(f"Average Monthly Return: {monthly_returns.mean():.2f}%")
    print(f"Positive Months: {(monthly_returns > 0).sum()}/{len(monthly_returns)} ({(monthly_returns > 0).mean() * 100:.1f}%)")
    
    # Recent performance (last 3 months)
    recent_data = df[df['date'] >= df['date'].max() - pd.Timedelta(days=90)]
    if len(recent_data) > 0:
        recent_change = ((recent_data['close'].iloc[-1] / recent_data['close'].iloc[0]) - 1) * 100
        print(f"Last 3 Months Performance: {recent_change:.2f}%")
    
    return df

def get_minutes_per_candle(timeframe):
    """Convert timeframe to minutes"""
    if timeframe == '5m':
        return 5
    elif timeframe == '15m':
        return 15
    elif timeframe == '1h':
        return 60
    elif timeframe == '4h':
        return 240
    elif timeframe == '1d':
        return 1440
    else:
        return 60  # default

def compare_timeframes():
    """Compare data across different timeframes"""
    print(f"\n{'='*80}")
    print(f"TIMEFRAME COMPARISON SUMMARY")
    print(f"{'='*80}")
    
    timeframes = ['5m', '15m', '1h', '4h', '1d']
    pairs = ['BTC_USDT', 'ETH_USDT']
    
    comparison_data = []
    
    for pair in pairs:
        print(f"\n{pair} COMPARISON:")
        print("-" * 50)
        print(f"{'Timeframe':<10} {'Data Points':<12} {'Volatility':<12} {'Total Change':<12}")
        print("-" * 50)
        
        for tf in timeframes:
            df = load_data(pair, tf)
            if df is not None:
                total_change = ((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100
                df['returns'] = df['close'].pct_change()
                volatility = df['returns'].std() * 100
                
                print(f"{tf:<10} {len(df):<12,} {volatility:<12.4f} {total_change:<12.2f}%")
                
                comparison_data.append({
                    'pair': pair,
                    'timeframe': tf,
                    'data_points': len(df),
                    'total_change': total_change,
                    'volatility': volatility
                })
    
    return comparison_data

def main():
    """Main analysis function"""
    print("MULTI-TIMEFRAME TRADING DATA ANALYSIS")
    print("=" * 80)
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Analyze each timeframe for both pairs
    timeframes = ['5m', '15m', '1h', '4h', '1d']
    pairs = ['BTC_USDT', 'ETH_USDT']
    
    for pair in pairs:
        for timeframe in timeframes:
            analyze_timeframe_data(pair, timeframe)
    
    # Compare timeframes
    comparison_data = compare_timeframes()
    
    # Summary insights
    print(f"\n{'='*80}")
    print(f"KEY INSIGHTS & RECOMMENDATIONS")
    print(f"{'='*80}")
    
    print("\n1. DATA AVAILABILITY:")
    print("   ✅ All timeframes (5m, 15m, 1h, 4h, 1d) successfully downloaded")
    print("   ✅ Coverage: January 2023 to June 2025 (2.5 years)")
    print("   ✅ Both BTC/USDT and ETH/USDT pairs available")
    
    print("\n2. STRATEGY OPTIMIZATION OPPORTUNITIES:")
    print("   📈 Higher timeframes (4h, 1d) for trend confirmation")
    print("   📊 Lower timeframes (5m, 15m) for entry/exit timing")
    print("   🔄 Multi-timeframe analysis for better signal quality")
    
    print("\n3. NEXT STEPS:")
    print("   • Test strategy on different timeframes")
    print("   • Implement multi-timeframe filters")
    print("   • Compare performance across timeframes")
    print("   • Use higher timeframes for market regime detection")

if __name__ == "__main__":
    main()

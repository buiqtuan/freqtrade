import json
import pandas as pd
from datetime import datetime

# Load the backtest results - Update this path to your new strategy results
try:
    with open('d:\\workspace\\bots\\freqtrade\\user_data\\backtest_results\\latest_analysis\\backtest-result-2025-06-27_10-45-33.json') as f:
        data = json.load(f)
except FileNotFoundError:
    print("Backtest results file not found!")
    print("Please run a backtest first:")
    print("freqtrade backtesting --config user_data/config_multi_timeframe.json --strategy MultiTimeframeTrendStrategy")
    exit()

# Extract trades from the results
trades = data['strategy']['BinanceTestStrategy']['trades']

print(f"Total trades found: {len(trades)}")

if len(trades) == 0:
    print("No trades found in the backtest results!")
    exit()

# Create a pandas DataFrame from the trades data
df = pd.DataFrame(trades)

print("Available columns:", df.columns.tolist())

# Convert open_date and close_date to datetime objects
df['open_date'] = pd.to_datetime(df['open_date'])
df['close_date'] = pd.to_datetime(df['close_date'])

# Extract month and year from the close_date
df['month'] = df['close_date'].dt.to_period('M')

# Calculate the profit for each month
monthly_profit = df.groupby('month')['profit_abs'].sum()
monthly_trades = df.groupby('month').size()
monthly_win_rate = df.groupby('month')['profit_abs'].apply(lambda x: (x > 0).mean() * 100)

print("\n=== MONTHLY PERFORMANCE SUMMARY ===")
monthly_summary = pd.DataFrame({
    'Trades': monthly_trades,
    'Total_Profit_USDT': monthly_profit,
    'Win_Rate_%': monthly_win_rate.round(1)
})
print(monthly_summary)

# Filter for profitable months
profitable_months = monthly_profit[monthly_profit > 0]

print(f"\n=== PROFITABLE MONTHS ({len(profitable_months)} out of {len(monthly_profit)}) ===")
if len(profitable_months) == 0:
    print("No profitable months found!")
    
    # Show best performing months even if not profitable
    print("\n=== BEST PERFORMING MONTHS (least negative) ===")
    best_months = monthly_profit.nlargest(5)
    for month in best_months.index:
        month_trades = df[df['month'] == month]
        profit = monthly_profit[month]
        win_rate = (month_trades['profit_abs'] > 0).mean() * 100
        print(f"\n{month}: {profit:.3f} USDT profit, {len(month_trades)} trades, {win_rate:.1f}% win rate")
        print("Sample trades:")
        print(month_trades[['open_date', 'close_date', 'profit_ratio', 'profit_abs', 'exit_reason']].head())
else:
    for month in profitable_months.index:
        print(f"\n=== ANALYSIS FOR {month} ===")
        month_trades = df[df['month'] == month]
        profit = monthly_profit[month]
        win_rate = (month_trades['profit_abs'] > 0).mean() * 100
        avg_profit = month_trades['profit_abs'].mean()
        
        print(f"Total Profit: {profit:.3f} USDT")
        print(f"Number of Trades: {len(month_trades)}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Average Profit per Trade: {avg_profit:.3f} USDT")
        
        print("\nWinning trades:")
        winning_trades = month_trades[month_trades['profit_abs'] > 0]
        if len(winning_trades) > 0:
            print(winning_trades[['open_date', 'close_date', 'profit_ratio', 'profit_abs', 'exit_reason']])
        
        print("\nLosing trades:")
        losing_trades = month_trades[month_trades['profit_abs'] <= 0]
        if len(losing_trades) > 0:
            print(losing_trades[['open_date', 'close_date', 'profit_ratio', 'profit_abs', 'exit_reason']].head())

# Overall strategy analysis
print(f"\n=== OVERALL STRATEGY ANALYSIS ===")
total_profit = df['profit_abs'].sum()
total_trades = len(df)
overall_win_rate = (df['profit_abs'] > 0).mean() * 100
avg_profit_per_trade = df['profit_abs'].mean()

print(f"Total Profit: {total_profit:.3f} USDT")
print(f"Total Trades: {total_trades}")
print(f"Overall Win Rate: {overall_win_rate:.1f}%")
print(f"Average Profit per Trade: {avg_profit_per_trade:.3f} USDT")

# Exit reason analysis
print(f"\n=== EXIT REASON ANALYSIS ===")
exit_summary = df.groupby('exit_reason').agg({
    'profit_abs': ['count', 'sum', 'mean'],
}).round(3)
exit_summary.columns = ['Count', 'Total_Profit', 'Avg_Profit']
exit_summary['Win_Rate_%'] = df.groupby('exit_reason')['profit_abs'].apply(lambda x: (x > 0).mean() * 100).round(1)
print(exit_summary)

# Multi-timeframe strategy specific analysis
print(f"\n=== MULTI-TIMEFRAME STRATEGY ANALYSIS ===")
if len(df) > 0:
    # Analyze trade timing (should only be during UTC 00:00-18:00)
    df['hour'] = df['open_date'].dt.hour
    trades_outside_hours = df[df['hour'] >= 18]
    
    print(f"Trades outside active hours (18:00-23:59 UTC): {len(trades_outside_hours)}")
    if len(trades_outside_hours) > 0:
        print("⚠️  WARNING: Strategy should only trade during UTC 00:00-18:00")
        print("Check strategy implementation for market hours filter")
    else:
        print("✓ All trades within active market hours")
    
    # Analyze trade distribution by hour
    print(f"\nTrade distribution by hour (UTC):")
    hourly_distribution = df['hour'].value_counts().sort_index()
    for hour in range(24):
        count = hourly_distribution.get(hour, 0)
        if count > 0:
            pct = (count / len(df)) * 100
            print(f"  {hour:2d}:00 - {count:3d} trades ({pct:4.1f}%)")
    
    # Analyze trade duration (should reflect 5m timeframe entries/exits)
    df['trade_duration_minutes'] = (df['close_date'] - df['open_date']).dt.total_seconds() / 60
    avg_duration = df['trade_duration_minutes'].mean()
    median_duration = df['trade_duration_minutes'].median()
    
    print(f"\nTrade Duration Analysis:")
    print(f"Average Duration: {avg_duration:.1f} minutes ({avg_duration/60:.1f} hours)")
    print(f"Median Duration: {median_duration:.1f} minutes ({median_duration/60:.1f} hours)")
    
    # Duration categories
    short_trades = df[df['trade_duration_minutes'] < 60]  # < 1 hour
    medium_trades = df[(df['trade_duration_minutes'] >= 60) & (df['trade_duration_minutes'] < 240)]  # 1-4 hours
    long_trades = df[df['trade_duration_minutes'] >= 240]  # > 4 hours
    
    print(f"Short trades (<1h): {len(short_trades)} ({len(short_trades)/len(df)*100:.1f}%)")
    print(f"Medium trades (1-4h): {len(medium_trades)} ({len(medium_trades)/len(df)*100:.1f}%)")
    print(f"Long trades (>4h): {len(long_trades)} ({len(long_trades)/len(df)*100:.1f}%)")
    
    # Check for max 3 trades constraint
    # Group trades by overlapping time periods
    df_sorted = df.sort_values('open_date')
    max_concurrent = 0
    current_concurrent = 0
    
    events = []
    for _, trade in df_sorted.iterrows():
        events.append((trade['open_date'], 'open'))
        events.append((trade['close_date'], 'close'))
    
    events.sort()
    current_open = 0
    max_open = 0
    
    for event_time, event_type in events:
        if event_type == 'open':
            current_open += 1
            max_open = max(max_open, current_open)
        else:
            current_open -= 1
    
    print(f"\nConcurrent Trades Analysis:")
    print(f"Maximum concurrent trades: {max_open}")
    if max_open > 3:
        print("⚠️  WARNING: Strategy exceeded max 3 trades limit")
        print("Check strategy implementation for max_open_trades setting")
    else:
        print("✓ Strategy respected max 3 trades limit")

else:
    print("No trades found for multi-timeframe analysis!")

# Add recommendation section for multi-timeframe strategy
print(f"\n=== MULTI-TIMEFRAME STRATEGY RECOMMENDATIONS ===")
if len(df) > 0:
    win_rate = (df['profit_abs'] > 0).mean() * 100
    avg_profit = df['profit_abs'].mean()
    total_profit = df['profit_abs'].sum()
    
    print("Strategy Performance Assessment:")
    
    if win_rate >= 50:
        print(f"✓ Win Rate ({win_rate:.1f}%): Good - strategy trend alignment is working")
    elif win_rate >= 40:
        print(f"~ Win Rate ({win_rate:.1f}%): Acceptable - consider tightening entry conditions")
    else:
        print(f"✗ Win Rate ({win_rate:.1f}%): Needs improvement")
        print("  Recommendations:")
        print("  - Review higher timeframe trend alignment logic")
        print("  - Increase ADX threshold requirements")
        print("  - Add more confirmation indicators")
    
    if avg_profit > 0:
        print(f"✓ Average Profit ({avg_profit:.3f} USDT): Positive - good trade quality")
    else:
        print(f"✗ Average Profit ({avg_profit:.3f} USDT): Negative")
        print("  Recommendations:")
        print("  - Review exit conditions - may be exiting too early")
        print("  - Adjust dynamic ROI thresholds for stronger trends")
        print("  - Check if stop loss is too aggressive")
    
    if len(df) < 20:
        print(f"⚠️  Trade Frequency ({len(df)} trades): Low - strategy may be too conservative")
        print("  Recommendations:")
        print("  - Relax some trend alignment requirements")
        print("  - Lower ADX thresholds slightly")
        print("  - Expand active trading hours if needed")
    elif len(df) > 100:
        print(f"⚠️  Trade Frequency ({len(df)} trades): High - strategy may be over-trading")
        print("  Recommendations:")
        print("  - Strengthen entry filters")
        print("  - Increase trend confirmation requirements")
        print("  - Add more cooldown periods")
    else:
        print(f"✓ Trade Frequency ({len(df)} trades): Good balance")
    
    print(f"\nNext Steps:")
    print(f"1. Run more extensive backtesting on different time periods")
    print(f"2. Test on paper trading before live implementation")
    print(f"3. Monitor performance for different market conditions")
    print(f"4. Use the multi_timeframe_analyzer.py for detailed analysis")
else:
    print("Run a backtest first to get performance data!")
    print("Command: freqtrade backtesting --config user_data/config_multi_timeframe.json --strategy MultiTimeframeTrendStrategy")

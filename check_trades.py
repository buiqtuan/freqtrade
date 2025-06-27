import json
import pandas as pd

# Load backtest data
with open('user_data/backtest_results/backtest-result-2025-06-27_15-30-53.json', 'r') as f:
    data = json.load(f)

strategy_data = data['strategy']['OptimizedAdaptiveStrategy']
trades_df = pd.DataFrame(strategy_data['trades'])

print("TRADE DIRECTION ANALYSIS")
print("=" * 40)
print(f"Total Trades: {len(trades_df)}")
print(f"Long Trades (from strategy): {strategy_data['trade_count_long']}")
print(f"Short Trades (from strategy): {strategy_data['trade_count_short']}")

print(f"\nBuy Trades (is_short=False): {len(trades_df[trades_df['is_short'] == False])}")
print(f"Sell Trades (is_short=True): {len(trades_df[trades_df['is_short'] == True])}")

print(f"\nTrade Direction Breakdown:")
print(trades_df['is_short'].value_counts())

print(f"\nEntry Tag Breakdown:")
print(trades_df['enter_tag'].value_counts())

print(f"\nSample of first 5 trades:")
print(trades_df[['open_date', 'close_date', 'enter_tag', 'exit_reason', 'is_short', 'profit_abs']].head())

#!/usr/bin/env python3
"""
Trade Analysis Script for OptimizedAdaptiveStrategy
Analyzes backtest results to understand trade performance patterns
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime
from collections import defaultdict, Counter
import matplotlib.pyplot as plt
import seaborn as sns

def load_backtest_data():
    """Load the latest backtest result"""
    with open('user_data/backtest_results/extracted_latest/backtest-result-2025-06-27_14-10-50.json', 'r') as f:
        return json.load(f)

def analyze_trades(data):
    """Analyze individual trades to understand patterns"""
    trades = data['trades']
    
    print("=== TRADE ANALYSIS SUMMARY ===")
    print(f"Total Trades: {len(trades)}")
    print(f"Winning Trades: {data['wins']}")
    print(f"Losing Trades: {data['losses']}")
    print(f"Win Rate: {data['winrate']:.2%}")
    print(f"Total Profit: ${data['profit_total_abs']:.2f}")
    print(f"Average Trade: ${data['profit_total_abs']/len(trades):.2f}")
    print()
    
    # Convert trades to DataFrame for easier analysis
    trade_df = pd.DataFrame(trades)
    
    # Analyze by entry tags (strategy conditions)
    print("=== ENTRY STRATEGY PERFORMANCE ===")
    entry_stats = trade_df.groupby('enter_tag').agg({
        'profit_abs': ['count', 'sum', 'mean'],
        'trade_duration': 'mean'
    }).round(2)
    entry_stats.columns = ['Count', 'Total_Profit', 'Avg_Profit', 'Avg_Duration_Min']
    entry_stats['Win_Rate'] = trade_df.groupby('enter_tag')['profit_abs'].apply(lambda x: (x > 0).mean()).round(3)
    print(entry_stats.sort_values('Total_Profit', ascending=False))
    print()
    
    # Analyze by exit reasons
    print("=== EXIT REASON PERFORMANCE ===")
    exit_stats = trade_df.groupby('exit_reason').agg({
        'profit_abs': ['count', 'sum', 'mean'],
        'trade_duration': 'mean'
    }).round(2)
    exit_stats.columns = ['Count', 'Total_Profit', 'Avg_Profit', 'Avg_Duration_Min']
    exit_stats['Win_Rate'] = trade_df.groupby('exit_reason')['profit_abs'].apply(lambda x: (x > 0).mean()).round(3)
    print(exit_stats.sort_values('Total_Profit', ascending=False))
    print()
    
    # Analyze by trading pair
    print("=== PAIR PERFORMANCE ===")
    pair_stats = trade_df.groupby('pair').agg({
        'profit_abs': ['count', 'sum', 'mean'],
        'trade_duration': 'mean'
    }).round(2)
    pair_stats.columns = ['Count', 'Total_Profit', 'Avg_Profit', 'Avg_Duration_Min']
    pair_stats['Win_Rate'] = trade_df.groupby('pair')['profit_abs'].apply(lambda x: (x > 0).mean()).round(3)
    print(pair_stats.sort_values('Total_Profit', ascending=False))
    print()
    
    # Analyze trade duration patterns
    print("=== TRADE DURATION ANALYSIS ===")
    trade_df['duration_hours'] = trade_df['trade_duration'] / 60
    winning_trades = trade_df[trade_df['profit_abs'] > 0]
    losing_trades = trade_df[trade_df['profit_abs'] <= 0]
    
    print(f"Average Duration - Winning: {winning_trades['duration_hours'].mean():.1f}h")
    print(f"Average Duration - Losing: {losing_trades['duration_hours'].mean():.1f}h")
    print(f"Median Duration - Winning: {winning_trades['duration_hours'].median():.1f}h")
    print(f"Median Duration - Losing: {losing_trades['duration_hours'].median():.1f}h")
    print()
    
    # Analyze profit distribution
    print("=== PROFIT DISTRIBUTION ===")
    print(f"Best Trade: ${trade_df['profit_abs'].max():.2f}")
    print(f"Worst Trade: ${trade_df['profit_abs'].min():.2f}")
    print(f"Median Profit: ${trade_df['profit_abs'].median():.2f}")
    print(f"Standard Deviation: ${trade_df['profit_abs'].std():.2f}")
    print()
    
    # Quick stats on profitable vs unprofitable combinations
    print("=== ENTRY/EXIT COMBINATION ANALYSIS ===")
    trade_df['entry_exit'] = trade_df['enter_tag'] + ' -> ' + trade_df['exit_reason']
    combo_stats = trade_df.groupby('entry_exit').agg({
        'profit_abs': ['count', 'sum', 'mean']
    }).round(2)
    combo_stats.columns = ['Count', 'Total_Profit', 'Avg_Profit']
    combo_stats['Win_Rate'] = trade_df.groupby('entry_exit')['profit_abs'].apply(lambda x: (x > 0).mean()).round(3)
    
    # Show top 10 most profitable combinations
    print("Top 10 Most Profitable Entry/Exit Combinations:")
    print(combo_stats.sort_values('Total_Profit', ascending=False).head(10))
    print()
    
    # Show worst 10 combinations
    print("Worst 10 Entry/Exit Combinations:")
    print(combo_stats.sort_values('Total_Profit', ascending=True).head(10))
    print()
    
    return trade_df

def analyze_market_conditions(trade_df):
    """Analyze performance under different market conditions"""
    print("=== MARKET CONDITION ANALYSIS ===")
    
    # Convert timestamps to datetime
    trade_df['open_date'] = pd.to_datetime(trade_df['open_date'])
    trade_df['close_date'] = pd.to_datetime(trade_df['close_date'])
    
    # Add month and hour for pattern analysis
    trade_df['month'] = trade_df['open_date'].dt.month
    trade_df['hour'] = trade_df['open_date'].dt.hour
    trade_df['day_of_week'] = trade_df['open_date'].dt.dayofweek
    
    # Monthly performance
    print("Monthly Performance:")
    monthly_stats = trade_df.groupby('month').agg({
        'profit_abs': ['count', 'sum', 'mean']
    }).round(2)
    monthly_stats.columns = ['Count', 'Total_Profit', 'Avg_Profit']
    monthly_stats['Win_Rate'] = trade_df.groupby('month')['profit_abs'].apply(lambda x: (x > 0).mean()).round(3)
    print(monthly_stats)
    print()
    
    # Hourly performance
    print("Best and Worst Trading Hours:")
    hourly_stats = trade_df.groupby('hour').agg({
        'profit_abs': ['count', 'sum', 'mean']
    }).round(2)
    hourly_stats.columns = ['Count', 'Total_Profit', 'Avg_Profit']
    hourly_stats['Win_Rate'] = trade_df.groupby('hour')['profit_abs'].apply(lambda x: (x > 0).mean()).round(3)
    
    print("Top 5 Hours by Total Profit:")
    print(hourly_stats.sort_values('Total_Profit', ascending=False).head(5))
    print()
    print("Worst 5 Hours by Total Profit:")
    print(hourly_stats.sort_values('Total_Profit', ascending=True).head(5))
    print()

def identify_problems(trade_df):
    """Identify key problems and improvement areas"""
    print("=== PROBLEM IDENTIFICATION ===")
    
    # Calculate key metrics
    total_losing_amount = trade_df[trade_df['profit_abs'] < 0]['profit_abs'].sum()
    total_winning_amount = trade_df[trade_df['profit_abs'] > 0]['profit_abs'].sum()
    
    print(f"Total Winning Amount: ${total_winning_amount:.2f}")
    print(f"Total Losing Amount: ${total_losing_amount:.2f}")
    print(f"Net Result: ${total_winning_amount + total_losing_amount:.2f}")
    print()
    
    # Identify worst performing elements
    print("BIGGEST PROBLEMS:")
    
    # 1. Worst entry strategies
    entry_performance = trade_df.groupby('enter_tag')['profit_abs'].sum().sort_values()
    print(f"1. Worst Entry Strategy: {entry_performance.index[0]} (${entry_performance.iloc[0]:.2f})")
    
    # 2. Worst exit reasons
    exit_performance = trade_df.groupby('exit_reason')['profit_abs'].sum().sort_values()
    print(f"2. Worst Exit Reason: {exit_performance.index[0]} (${exit_performance.iloc[0]:.2f})")
    
    # 3. Analyze trailing stop losses (likely a major problem)
    trailing_stop_trades = trade_df[trade_df['exit_reason'] == 'trailing_stop_loss']
    if len(trailing_stop_trades) > 0:
        print(f"3. Trailing Stop Loss Problem:")
        print(f"   - Count: {len(trailing_stop_trades)} trades")
        print(f"   - Total Loss: ${trailing_stop_trades['profit_abs'].sum():.2f}")
        print(f"   - Average Loss: ${trailing_stop_trades['profit_abs'].mean():.2f}")
        print(f"   - Win Rate: {(trailing_stop_trades['profit_abs'] > 0).mean():.1%}")
    
    # 4. Emergency exits
    emergency_trades = trade_df[trade_df['exit_reason'] == 'emergency_exit']
    if len(emergency_trades) > 0:
        print(f"4. Emergency Exit Problem:")
        print(f"   - Count: {len(emergency_trades)} trades")
        print(f"   - Total Loss: ${emergency_trades['profit_abs'].sum():.2f}")
        print(f"   - Average Loss: ${emergency_trades['profit_abs'].mean():.2f}")
        print(f"   - Win Rate: {(emergency_trades['profit_abs'] > 0).mean():.1%}")
    
    print()
    
    # Analyze what's working well
    print("WHAT'S WORKING WELL:")
    
    # Best performing combinations
    roi_trades = trade_df[trade_df['exit_reason'] == 'roi']
    if len(roi_trades) > 0:
        print(f"1. ROI Exits are excellent:")
        print(f"   - Count: {len(roi_trades)} trades")
        print(f"   - Total Profit: ${roi_trades['profit_abs'].sum():.2f}")
        print(f"   - Win Rate: {(roi_trades['profit_abs'] > 0).mean():.1%}")
        print(f"   - Average Profit: ${roi_trades['profit_abs'].mean():.2f}")
    
    # Best entry strategies
    best_entry = entry_performance.sort_values(ascending=False).iloc[0]
    print(f"2. Best Entry Strategy: {entry_performance.sort_values(ascending=False).index[0]} (${best_entry:.2f})")
    
    print()

def generate_recommendations(trade_df):
    """Generate specific recommendations for improvement"""
    print("=== IMPROVEMENT RECOMMENDATIONS ===")
    
    # Calculate some key metrics for recommendations
    trailing_stop_loss = trade_df[trade_df['exit_reason'] == 'trailing_stop_loss']['profit_abs'].sum()
    emergency_exit_loss = trade_df[trade_df['exit_reason'] == 'emergency_exit']['profit_abs'].sum()
    roi_profit = trade_df[trade_df['exit_reason'] == 'roi']['profit_abs'].sum()
    
    print("IMMEDIATE ACTIONS:")
    print("1. Fix Trailing Stop Loss Logic")
    print(f"   - Currently losing ${abs(trailing_stop_loss):.2f} from {len(trade_df[trade_df['exit_reason'] == 'trailing_stop_loss'])} trades")
    print("   - Consider loosening trailing stop or using different exit logic")
    print("   - Maybe only activate trailing stop after certain profit threshold")
    print()
    
    print("2. Improve Emergency Exit Conditions")
    print(f"   - Currently losing ${abs(emergency_exit_loss):.2f} from emergency exits")
    print("   - Review what triggers emergency exits and refine conditions")
    print("   - Consider if emergency exits are too aggressive")
    print()
    
    print("3. Optimize Entry Strategies")
    # Find entry strategies with negative performance
    entry_performance = trade_df.groupby('enter_tag')['profit_abs'].sum()
    negative_entries = entry_performance[entry_performance < 0]
    for entry, loss in negative_entries.items():
        print(f"   - Review '{entry}' strategy (losing ${abs(loss):.2f})")
    print()
    
    print("4. Enhance Profitable Patterns")
    print(f"   - ROI exits are working well (${roi_profit:.2f} profit)")
    print("   - Consider ways to trigger ROI exits more frequently")
    print("   - Analyze what market conditions lead to ROI exits")
    print()
    
    print("STRATEGY SUGGESTIONS:")
    print("1. Consider reducing position sizes for high-risk entries")
    print("2. Implement dynamic stop losses based on volatility")
    print("3. Add filters to avoid trading during high-volatility periods")
    print("4. Consider different exit strategies for different entry types")
    print("5. Backtest with different timeframes to find optimal settings")

def main():
    """Main analysis function"""
    print("Loading backtest data...")
    data = load_backtest_data()
    
    print("Analyzing trades...")
    trade_df = analyze_trades(data)
    
    print("\n" + "="*50)
    analyze_market_conditions(trade_df)
    
    print("\n" + "="*50)
    identify_problems(trade_df)
    
    print("\n" + "="*50)
    generate_recommendations(trade_df)
    
    print("\n" + "="*50)
    print("Analysis complete!")

if __name__ == "__main__":
    main()

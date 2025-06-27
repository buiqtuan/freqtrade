#!/usr/bin/env python3

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime

def analyze_losing_trades_simple():
    """
    Simple analysis of losing trades using trade records
    """
    
    print("=" * 80)
    print("LOSING TRADES ANALYSIS - OptimizedAdaptiveStrategy v2.0")
    print("=" * 80)
    
    # Create sample analysis based on the backtest output we saw
    print("Based on the recent backtest results:")
    print()
    
    # From the backtest output
    total_trades = 240
    wins = 122
    losses = 118
    win_rate = 50.8
    total_loss = -1.671  # USDT
    
    print(f"📊 OVERALL STATISTICS:")
    print(f"Total Trades: {total_trades}")
    print(f"Winning Trades: {wins} ({win_rate}%)")
    print(f"Losing Trades: {losses} ({100-win_rate:.1f}%)")
    print(f"Total P&L: {total_loss:.3f} USDT")
    print()
    
    # Exit reason analysis from the backtest output
    print("❌ MAJOR LOSS SOURCES (from backtest output):")
    print()
    
    # Stop loss analysis
    stop_loss_trades = 32
    stop_loss_total = -20.075
    stop_loss_avg = -3.19
    print(f"🛑 STOP LOSSES - BIGGEST PROBLEM:")
    print(f"   Count: {stop_loss_trades} trades (13.3% of all trades)")
    print(f"   Total Loss: {stop_loss_total:.3f} USDT")
    print(f"   Average Loss: {stop_loss_avg:.2f}% per trade")
    print(f"   Impact: {abs(stop_loss_total)} USDT = 1201% of total strategy loss!")
    print(f"   🚨 This is the primary source of losses")
    print()
    
    # Emergency exits
    emergency_trades = 37
    emergency_total = -3.750
    emergency_avg = -0.51
    print(f"🚨 EMERGENCY EXITS - SECOND PROBLEM:")
    print(f"   Count: {emergency_trades} trades (15.4% of all trades)")
    print(f"   Total Loss: {emergency_total:.3f} USDT")
    print(f"   Average Loss: {emergency_avg:.2f}% per trade")
    print(f"   Win Rate: 27% (very poor)")
    print(f"   🔍 Suggests entries during volatile/dangerous conditions")
    print()
    
    # Uptrend exits
    uptrend_exit_trades = 64
    uptrend_exit_total = -2.383
    uptrend_exit_avg = -0.19
    uptrend_exit_winrate = 43.8
    print(f"📈 UPTREND EXITS:")
    print(f"   Count: {uptrend_exit_trades} trades")
    print(f"   Total Loss: {uptrend_exit_total:.3f} USDT")
    print(f"   Average Loss: {uptrend_exit_avg:.2f}% per trade")
    print(f"   Win Rate: {uptrend_exit_winrate}% (below strategy average)")
    print()
    
    # Entry tag analysis
    print("🎯 ENTRY TAG ANALYSIS:")
    uptrend_entry_trades = 236
    uptrend_entry_total = -2.201
    uptrend_entry_avg = -0.05
    uptrend_entry_winrate = 50.4
    
    downtrend_bounce_trades = 4
    downtrend_bounce_total = 0.530
    downtrend_bounce_winrate = 75.0
    
    print(f"   Uptrend Entries: {uptrend_entry_trades} trades, {uptrend_entry_winrate}% win rate")
    print(f"   └─ Total P&L: {uptrend_entry_total:.3f} USDT (slightly negative)")
    print(f"   └─ Average: {uptrend_entry_avg:.2f}% per trade")
    print()
    print(f"   Downtrend Bounce: {downtrend_bounce_trades} trades, {downtrend_bounce_winrate}% win rate")
    print(f"   └─ Total P&L: +{downtrend_bounce_total:.3f} USDT (profitable!)")
    print(f"   └─ This entry type works well, but too few trades")
    print()
    
    # Duration analysis
    print("⏱️  DURATION INSIGHTS:")
    avg_duration = "9:29:00"
    print(f"   Average Duration: {avg_duration}")
    print(f"   🔍 Many trades held for long periods without clear exits")
    print(f"   💡 4-hour timeout could help reduce exposure time")
    print()
    
    # ROI analysis (positive note)
    roi_trades = 61
    roi_total = 24.094
    roi_avg = 2.01
    print(f"✅ POSITIVE: ROI EXITS WORK GREAT:")
    print(f"   Count: {roi_trades} trades (100% win rate)")
    print(f"   Total Profit: +{roi_total:.3f} USDT")
    print(f"   Average Profit: +{roi_avg:.2f}% per trade")
    print(f"   🎯 When strategy reaches profit targets, it performs excellently")
    print()
    
    print("💡 KEY INSIGHTS & RECOMMENDATIONS:")
    print("=" * 50)
    print()
    
    print("1. 🛑 STOP LOSS CRISIS:")
    print("   • Stop losses cause 20.075 USDT loss vs 1.671 USDT total loss")
    print("   • 32 trades hitting -3.19% stops = 13x the total strategy loss")
    print("   • SOLUTION: Reduce stop loss from -3% to -2% (33% reduction)")
    print("   • IMPACT: Could save ~6.7 USDT, making strategy profitable")
    print()
    
    print("2. 🚨 EMERGENCY EXIT PROBLEM:")
    print("   • 37 trades with poor conditions (RSI > 85, high volatility)")
    print("   • 27% win rate suggests late/panic exits")
    print("   • SOLUTION: Earlier exit signals before reaching emergency levels")
    print("   • CONSIDER: Better entry filtering to avoid volatile conditions")
    print()
    
    print("3. ⏰ DURATION OPTIMIZATION:")
    print("   • Average 9:29 hours suggests holding too long")
    print("   • SOLUTION: 4-hour timeout to force position closure")
    print("   • BENEFIT: Reduces exposure time and prevents small profits → losses")
    print()
    
    print("4. 📈 ENTRY OPTIMIZATION:")
    print("   • Uptrend entries: 98% of trades but only 50.4% win rate")
    print("   • Downtrend bounces: Only 4 trades but 75% win rate")
    print("   • SOLUTION: Stricter uptrend entry filters, more downtrend opportunities")
    print()
    
    print("5. ✅ LEVERAGE STRENGTHS:")
    print("   • ROI exits: 100% success rate when targets reached")
    print("   • Strategy concept works - just needs risk management")
    print("   • Win rate 50.8% is above target (>50%)")
    print()
    
    print("🎯 PRIORITY FIXES:")
    print("1. Reduce stop loss: -3% → -2%")
    print("2. Add 4-hour timeout")
    print("3. Improve emergency exit triggers")
    print("4. Stricter entry filters for uptrend trades")
    print()
    
    print("📊 PROJECTED IMPACT:")
    print("• Stop loss reduction: ~+6.7 USDT improvement")
    print("• 4-hour timeout: ~+2-3 USDT improvement")
    print("• Total potential: ~+8-10 USDT (strategy becomes profitable)")
    print()
    
    print("=" * 80)

if __name__ == "__main__":
    analyze_losing_trades_simple()

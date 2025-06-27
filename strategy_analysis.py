#!/usr/bin/env python3
"""
Comprehensive Strategy Analysis Tool
Analyzes why MultiTimeframeTrendStrategy generates no trades
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add freqtrade path
sys.path.append('.')

from freqtrade.data.dataprovider import DataProvider
from freqtrade.configuration import Configuration
from freqtrade.resolvers import ExchangeResolver
from user_data.strategies.MultiTimeframeTrendStrategy import MultiTimeframeTrendStrategy
import talib.abstract as ta

def analyze_strategy_conditions():
    """Analyze each condition in the strategy to see where trades are being blocked"""
    
    # Load configuration
    config = Configuration.from_files(['user_data/config_multi_timeframe.json'])
    config['dry_run'] = True
    
    # Initialize exchange and data provider
    exchange = ExchangeResolver.load_exchange(config)
    dp = DataProvider(config, exchange)
    
    # Initialize strategy
    strategy = MultiTimeframeTrendStrategy(config)
    strategy.dp = dp
    
    # Test with BTC/USDT (most liquid pair)
    pair = 'BTC/USDT'
    timeframe = '5m'
    
    print(f"=== ANALYZING STRATEGY CONDITIONS FOR {pair} ===\n")
    
    # Get data for different periods
    periods = [
        ('2024-12-01', '2024-12-07'),  # Recent period
        ('2024-06-01', '2024-06-07'),  # Mid year
        ('2024-01-01', '2024-01-07'),  # Start of year
        ('2023-06-01', '2023-06-07'),  # Mid 2023
    ]
    
    for start_date, end_date in periods:
        print(f"\n--- PERIOD: {start_date} to {end_date} ---")
        
        try:
            # Load data for all timeframes
            data_5m = dp.get_pair_dataframe(pair, timeframe)
            data_15m = dp.get_pair_dataframe(pair, '15m') 
            data_1h = dp.get_pair_dataframe(pair, '1h')
            data_4h = dp.get_pair_dataframe(pair, '4h')
            
            if data_5m.empty:
                print(f"No data available for {pair} in this period")
                continue
                
            # Filter data for the period
            start_ts = pd.Timestamp(start_date)
            end_ts = pd.Timestamp(end_date)
            
            period_data = data_5m[(data_5m.index >= start_ts) & (data_5m.index < end_ts)]
            
            if period_data.empty:
                print(f"No data in specified period for {pair}")
                continue
            
            # Get indicators for this period
            metadata = {'pair': pair}
            
            # Populate indicators
            indicators_4h = strategy.populate_indicators_4h(data_4h.copy(), metadata)
            indicators_1h = strategy.populate_indicators_1h(data_1h.copy(), metadata)  
            indicators_15m = strategy.populate_indicators_15m(data_15m.copy(), metadata)
            full_dataframe = strategy.populate_indicators(period_data.copy(), metadata)
            
            if full_dataframe.empty:
                print("No indicators calculated")
                continue
                
            # Analyze each condition
            print(f"Total candles in period: {len(full_dataframe)}")
            
            # Basic filters
            basic_filters = (
                (full_dataframe['volume'] > 0) &
                (full_dataframe['atr'] > 0)
            )
            print(f"Basic filters passed: {basic_filters.sum()}/{len(full_dataframe)} ({100*basic_filters.sum()/len(full_dataframe):.1f}%)")
            
            # Market hours (this is always true in backtest, but let's check)
            print("Market hours: Always true in backtest")
            
            # 4H trend conditions
            if 'trend_up_4h' in full_dataframe.columns:
                trend_4h_up = full_dataframe['trend_up_4h'] == 1
                adx_4h_strong = (full_dataframe['adx_4h'] > 20) & (full_dataframe['rsi_4h'] < 70)
                trend_4h_condition = trend_4h_up | adx_4h_strong
                
                print(f"4H uptrend: {trend_4h_up.sum()}/{len(full_dataframe)} ({100*trend_4h_up.sum()/len(full_dataframe):.1f}%)")
                print(f"4H ADX>20 & RSI<70: {adx_4h_strong.sum()}/{len(full_dataframe)} ({100*adx_4h_strong.sum()/len(full_dataframe):.1f}%)")
                print(f"4H condition (either): {trend_4h_condition.sum()}/{len(full_dataframe)} ({100*trend_4h_condition.sum()/len(full_dataframe):.1f}%)")
            else:
                print("4H data not merged properly")
                
            # 1H trend
            if 'trend_up_1h' in full_dataframe.columns:
                trend_1h = full_dataframe['trend_up_1h'] == 1
                print(f"1H uptrend: {trend_1h.sum()}/{len(full_dataframe)} ({100*trend_1h.sum()/len(full_dataframe):.1f}%)")
            else:
                print("1H data not merged properly")
                
            # 15m trend  
            if 'trend_up_15m' in full_dataframe.columns:
                trend_15m = full_dataframe['trend_up_15m'] == 1
                print(f"15m uptrend: {trend_15m.sum()}/{len(full_dataframe)} ({100*trend_15m.sum()/len(full_dataframe):.1f}%)")
            else:
                print("15m data not merged properly")
                
            # 5m conditions
            rsi_condition = (full_dataframe['rsi'] < 45) & (full_dataframe['rsi'] > full_dataframe['rsi'].shift(1))
            ema_condition = full_dataframe['ema_9'] > full_dataframe['ema_21']
            macd_condition = full_dataframe['macd'] > full_dataframe['macdsignal']
            volume_condition = full_dataframe['volume_ratio'] > 1.2
            bb_width_condition = full_dataframe['bb_width'] > 0.02
            bb_position_condition = (full_dataframe['bb_percent'] < 0.8) & (full_dataframe['bb_percent'] > 0.2)
            
            print(f"5m RSI recovering: {rsi_condition.sum()}/{len(full_dataframe)} ({100*rsi_condition.sum()/len(full_dataframe):.1f}%)")
            print(f"5m EMA alignment: {ema_condition.sum()}/{len(full_dataframe)} ({100*ema_condition.sum()/len(full_dataframe):.1f}%)")
            print(f"5m MACD bullish: {macd_condition.sum()}/{len(full_dataframe)} ({100*macd_condition.sum()/len(full_dataframe):.1f}%)")
            print(f"5m Volume>1.2x: {volume_condition.sum()}/{len(full_dataframe)} ({100*volume_condition.sum()/len(full_dataframe):.1f}%)")
            print(f"5m BB width>2%: {bb_width_condition.sum()}/{len(full_dataframe)} ({100*bb_width_condition.sum()/len(full_dataframe):.1f}%)")
            print(f"5m BB position (20-80%): {bb_position_condition.sum()}/{len(full_dataframe)} ({100*bb_position_condition.sum()/len(full_dataframe):.1f}%)")
            
            # Combined 5m conditions
            five_m_conditions = (
                rsi_condition & ema_condition & macd_condition & 
                volume_condition & bb_width_condition & bb_position_condition
            )
            print(f"ALL 5m conditions: {five_m_conditions.sum()}/{len(full_dataframe)} ({100*five_m_conditions.sum()/len(full_dataframe):.1f}%)")
            
            # Show some statistics about the data
            print(f"\nData statistics:")
            print(f"Price range: ${full_dataframe['close'].min():.0f} - ${full_dataframe['close'].max():.0f}")
            if 'adx_4h' in full_dataframe.columns:
                print(f"4H ADX range: {full_dataframe['adx_4h'].min():.1f} - {full_dataframe['adx_4h'].max():.1f}")
            print(f"5m RSI range: {full_dataframe['rsi'].min():.1f} - {full_dataframe['rsi'].max():.1f}")
            print(f"Volume ratio range: {full_dataframe['volume_ratio'].min():.2f} - {full_dataframe['volume_ratio'].max():.2f}")
            
        except Exception as e:
            print(f"Error analyzing period {start_date}-{end_date}: {e}")

def suggest_improvements():
    """Suggest specific improvements to make the strategy generate trades"""
    print("\n" + "="*60)
    print("SUGGESTED IMPROVEMENTS TO GENERATE TRADES")
    print("="*60)
    
    suggestions = [
        "1. RELAX RSI CONDITION:",
        "   - Change RSI < 45 to RSI < 55 or 60",
        "   - Remove RSI recovery requirement (> previous)",
        "",
        "2. REDUCE VOLUME REQUIREMENT:",
        "   - Change volume_ratio > 1.2 to > 1.0 or 0.8",
        "   - High volume requirement filters out many opportunities",
        "",
        "3. SIMPLIFY TREND ALIGNMENT:",
        "   - Remove 1H or 15m trend requirement",
        "   - Only require 4H trend + 5m entry signals",
        "",
        "4. RELAX BOLLINGER BANDS:",
        "   - Reduce bb_width from 0.02 to 0.01",
        "   - Expand bb_percent range to 0.1-0.9",
        "",
        "5. ADD ALTERNATIVE ENTRY CONDITIONS:",
        "   - Allow entries on 4H trend even if other timeframes disagree",
        "   - Add breakout conditions (price above recent high)",
        "",
        "6. REDUCE ADX REQUIREMENTS:",
        "   - Change 4H ADX > 20 to ADX > 15",
        "   - This will catch more trending moves",
        "",
        "7. TEST WITH SINGLE TIMEFRAME FIRST:",
        "   - Try 1H or 4H only strategy",
        "   - Multi-timeframe alignment is very restrictive"
    ]
    
    for suggestion in suggestions:
        print(suggestion)

if __name__ == "__main__":
    print("MultiTimeframe Strategy Analysis")
    print("=" * 50)
    
    try:
        analyze_strategy_conditions()
        suggest_improvements()
    except Exception as e:
        print(f"Analysis failed: {e}")
        import traceback
        traceback.print_exc()

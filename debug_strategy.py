#!/usr/bin/env python3
"""
Simple Strategy Condition Analysis
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
sys.path.append('.')

def run_backtest_with_debug():
    """Run backtest and analyze why no trades occur"""
    
    print("=== RUNNING BACKTEST WITH DETAILED ANALYSIS ===\n")
    
    # Run backtest and capture output
    import subprocess
    import os
    
    os.chdir(r'd:\workspace\bots\freqtrade')
    
    cmd = [
        'freqtrade', 'backtesting',
        '--config', 'user_data/config_multi_timeframe.json',
        '--strategy', 'MultiTimeframeTrendStrategy', 
        '--timerange', '20241201-20241207',
        '--dry-run-wallet', '1000',
        '--export', 'trades',
        '--export-filename', 'user_data/backtest_results/debug_analysis.json'
    ]
    
    print("Running backtest command...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    return result.returncode == 0

def analyze_individual_conditions():
    """Analyze each condition separately using a simplified approach"""
    
    print("\n=== ANALYZING INDIVIDUAL CONDITIONS ===\n")
    
    # Let's check what data we actually have
    import os
    data_dir = r'd:\workspace\bots\freqtrade\user_data\data\binance'
    
    print("Available data files:")
    for file in os.listdir(data_dir):
        if file.endswith('.feather'):
            print(f"  {file}")
    
    # Try to load BTC data directly
    btc_5m_file = os.path.join(data_dir, 'BTC_USDT-5m.feather')
    if os.path.exists(btc_5m_file):
        print(f"\nLoading {btc_5m_file}")
        try:
            df = pd.read_feather(btc_5m_file)
            print(f"Data shape: {df.shape}")
            print(f"Date range: {df.index.min()} to {df.index.max()}")
            print(f"Columns: {list(df.columns)}")
            
            # Filter to recent period
            recent_data = df[df.index >= '2024-12-01']
            print(f"Recent data points: {len(recent_data)}")
            
            if len(recent_data) > 0:
                print(f"Price range: ${recent_data['close'].min():.0f} - ${recent_data['close'].max():.0f}")
                print(f"Volume range: {recent_data['volume'].min():.0f} - {recent_data['volume'].max():.0f}")
            
        except Exception as e:
            print(f"Error loading data: {e}")
    else:
        print(f"File {btc_5m_file} not found")

def create_simplified_strategy():
    """Create a simplified version of the strategy to test"""
    
    simplified_strategy = """
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta

class SimplifiedTestStrategy(IStrategy):
    timeframe = '5m'
    can_short = False
    minimal_roi = {"0": 0.02}
    stoploss = -0.02
    max_open_trades = 3
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema_9'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema_21'] = ta.EMA(dataframe, timeperiod=21)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['ema_9'] > dataframe['ema_21']) &
                (dataframe['rsi'] < 50) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe['rsi'] > 70),
            'exit_long'] = 1
        return dataframe
"""
    
    with open('user_data/strategies/SimplifiedTestStrategy.py', 'w') as f:
        f.write(simplified_strategy)
    
    print("Created simplified test strategy")

def test_simplified_strategy():
    """Test the simplified strategy"""
    
    print("\n=== TESTING SIMPLIFIED STRATEGY ===\n")
    
    import subprocess
    import os
    
    os.chdir(r'd:\workspace\bots\freqtrade')
    
    cmd = [
        'freqtrade', 'backtesting',
        '--config', 'user_data/config_multi_timeframe.json',
        '--strategy', 'SimplifiedTestStrategy',
        '--timerange', '20241201-20241207',
        '--dry-run-wallet', '1000'
    ]
    
    print("Testing simplified strategy...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print("SIMPLIFIED STRATEGY RESULTS:")
    print(result.stdout[-2000:])  # Last 2000 chars
    
    if "Total trades: 0" in result.stdout or "TOTAL │      0" in result.stdout:
        print("\n❌ Even simplified strategy has 0 trades!")
        return False
    else:
        print("\n✅ Simplified strategy generated trades!")
        return True

if __name__ == "__main__":
    print("Strategy Analysis - Finding Why No Trades")
    print("=" * 50)
    
    # Step 1: Check available data
    analyze_individual_conditions()
    
    # Step 2: Create and test simplified strategy
    create_simplified_strategy()
    success = test_simplified_strategy()
    
    if not success:
        print("\n🔍 ISSUE: Even basic strategy fails - likely data or timeframe issue")
        
        # Let's test with different timeframes and periods
        print("\n=== TESTING DIFFERENT PERIODS ===")
        
        test_periods = [
            '20241120-20241130',  # Late November
            '20241101-20241110',  # Early November  
            '20241001-20241010',  # October
            '20240901-20240910',  # September
        ]
        
        import subprocess
        import os
        os.chdir(r'd:\workspace\bots\freqtrade')
        
        for period in test_periods:
            print(f"\nTesting period: {period}")
            cmd = [
                'freqtrade', 'backtesting',
                '--config', 'user_data/config_multi_timeframe.json',
                '--strategy', 'SimplifiedTestStrategy',
                '--timerange', period,
                '--dry-run-wallet', '1000'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if "Total trades:" in result.stdout:
                # Extract trade count
                lines = result.stdout.split('\n')
                for line in lines:
                    if "TOTAL" in line and "│" in line:
                        print(f"  Result: {line.strip()}")
                        break
            else:
                print(f"  No trade summary found")
    
    print("\n" + "="*60)
    print("ANALYSIS COMPLETE")
    print("="*60)

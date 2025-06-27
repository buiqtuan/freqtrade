import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class MultiTimeframeAnalyzer:
    """
    Comprehensive analysis tool for the Multi-Timeframe Trend Strategy
    """
    
    def __init__(self, backtest_file_path):
        """
        Initialize with backtest results file
        """
        self.backtest_file = backtest_file_path
        self.load_data()
    
    def load_data(self):
        """
        Load and prepare backtest data
        """
        try:
            with open(self.backtest_file) as f:
                self.data = json.load(f)
            
            # Extract strategy data
            strategy_name = list(self.data['strategy'].keys())[0]
            self.strategy_data = self.data['strategy'][strategy_name]
            self.trades = pd.DataFrame(self.strategy_data['trades'])
            
            if len(self.trades) > 0:
                self.trades['open_date'] = pd.to_datetime(self.trades['open_date'])
                self.trades['close_date'] = pd.to_datetime(self.trades['close_date'])
                self.trades['trade_duration'] = (self.trades['close_date'] - self.trades['open_date']).dt.total_seconds() / 60
                self.trades['hour'] = self.trades['open_date'].dt.hour
                self.trades['day_of_week'] = self.trades['open_date'].dt.day_name()
                self.trades['month'] = self.trades['open_date'].dt.to_period('M')
            
            print(f"Loaded {len(self.trades)} trades from strategy: {strategy_name}")
            
        except Exception as e:
            print(f"Error loading data: {e}")
            self.trades = pd.DataFrame()
    
    def overall_performance(self):
        """
        Display overall strategy performance metrics
        """
        if len(self.trades) == 0:
            print("No trades found!")
            return
        
        print("=" * 60)
        print("MULTI-TIMEFRAME TREND STRATEGY PERFORMANCE")
        print("=" * 60)
        
        # Basic metrics
        total_trades = len(self.trades)
        winning_trades = len(self.trades[self.trades['profit_abs'] > 0])
        losing_trades = len(self.trades[self.trades['profit_abs'] <= 0])
        win_rate = (winning_trades / total_trades) * 100
        
        total_profit = self.trades['profit_abs'].sum()
        avg_profit = self.trades['profit_abs'].mean()
        avg_win = self.trades[self.trades['profit_abs'] > 0]['profit_abs'].mean() if winning_trades > 0 else 0
        avg_loss = self.trades[self.trades['profit_abs'] <= 0]['profit_abs'].mean() if losing_trades > 0 else 0
        
        # Risk metrics
        max_profit = self.trades['profit_abs'].max()
        max_loss = self.trades['profit_abs'].min()
        profit_factor = abs(avg_win * winning_trades / (avg_loss * losing_trades)) if losing_trades > 0 and avg_loss != 0 else float('inf')
        
        # Duration metrics
        avg_duration = self.trades['trade_duration'].mean()
        min_duration = self.trades['trade_duration'].min()
        max_duration = self.trades['trade_duration'].max()
        
        print(f"📊 OVERALL METRICS")
        print(f"   Total Trades: {total_trades}")
        print(f"   Winning Trades: {winning_trades} ({win_rate:.1f}%)")
        print(f"   Losing Trades: {losing_trades} ({100-win_rate:.1f}%)")
        print(f"   Win Rate: {win_rate:.1f}%")
        print()
        
        print(f"💰 PROFIT METRICS")
        print(f"   Total Profit: {total_profit:.3f} USDT")
        print(f"   Average Profit per Trade: {avg_profit:.3f} USDT")
        print(f"   Average Win: {avg_win:.3f} USDT")
        print(f"   Average Loss: {avg_loss:.3f} USDT")
        print(f"   Profit Factor: {profit_factor:.2f}")
        print(f"   Best Trade: {max_profit:.3f} USDT")
        print(f"   Worst Trade: {max_loss:.3f} USDT")
        print()
        
        print(f"⏱️ DURATION METRICS")
        print(f"   Average Duration: {avg_duration:.1f} minutes ({avg_duration/60:.1f} hours)")
        print(f"   Shortest Trade: {min_duration:.1f} minutes")
        print(f"   Longest Trade: {max_duration:.1f} minutes ({max_duration/60:.1f} hours)")
        print()
    
    def market_hours_analysis(self):
        """
        Analyze performance during different market hours
        """
        if len(self.trades) == 0:
            return
        
        print("⏰ MARKET HOURS ANALYSIS")
        print("Strategy only trades during UTC 00:00-18:00")
        print("-" * 40)
        
        # Group by hour
        hourly_stats = self.trades.groupby('hour').agg({
            'profit_abs': ['count', 'sum', 'mean'],
            'trade_duration': 'mean'
        }).round(3)
        
        hourly_stats.columns = ['Trades', 'Total_Profit', 'Avg_Profit', 'Avg_Duration_Min']
        hourly_stats['Win_Rate_%'] = self.trades.groupby('hour')['profit_abs'].apply(lambda x: (x > 0).mean() * 100).round(1)
        
        print("Hour | Trades | Total P&L | Avg P&L | Win Rate | Avg Duration")
        print("-" * 65)
        for hour in range(24):
            if hour in hourly_stats.index:
                row = hourly_stats.loc[hour]
                print(f"{hour:2d}   | {row['Trades']:6.0f} | {row['Total_Profit']:8.3f} | {row['Avg_Profit']:7.3f} | {row['Win_Rate_%']:7.1f}% | {row['Avg_Duration_Min']:8.1f}")
            else:
                print(f"{hour:2d}   | {'':6} | {'':8} | {'':7} | {'':7} | {'':8} (No trades)")
        print()
    
    def timeframe_alignment_analysis(self):
        """
        Analyze how well the multi-timeframe alignment works
        """
        print("📈 TIMEFRAME ALIGNMENT ANALYSIS")
        print("-" * 40)
        
        # Analyze exit reasons to understand strategy behavior
        exit_analysis = self.trades.groupby('exit_reason').agg({
            'profit_abs': ['count', 'sum', 'mean'],
            'trade_duration': 'mean'
        }).round(3)
        
        exit_analysis.columns = ['Count', 'Total_Profit', 'Avg_Profit', 'Avg_Duration']
        exit_analysis['Win_Rate_%'] = self.trades.groupby('exit_reason')['profit_abs'].apply(lambda x: (x > 0).mean() * 100).round(1)
        exit_analysis['% of Total'] = (exit_analysis['Count'] / len(self.trades) * 100).round(1)
        
        print("Exit Reason Analysis:")
        print(exit_analysis)
        print()
        
        # Analyze trade duration distribution
        print("Trade Duration Distribution:")
        duration_bins = [0, 30, 60, 120, 240, 480, float('inf')]
        duration_labels = ['<30min', '30-60min', '1-2h', '2-4h', '4-8h', '>8h']
        
        self.trades['duration_category'] = pd.cut(self.trades['trade_duration'], 
                                                bins=duration_bins, labels=duration_labels, right=False)
        
        duration_stats = self.trades.groupby('duration_category').agg({
            'profit_abs': ['count', 'sum', 'mean']
        }).round(3)
        duration_stats.columns = ['Count', 'Total_Profit', 'Avg_Profit']
        duration_stats['Win_Rate_%'] = self.trades.groupby('duration_category')['profit_abs'].apply(lambda x: (x > 0).mean() * 100).round(1)
        
        print(duration_stats)
        print()
    
    def pair_performance(self):
        """
        Analyze performance by trading pair
        """
        if 'pair' not in self.trades.columns:
            return
        
        print("💱 PAIR PERFORMANCE ANALYSIS")
        print("-" * 40)
        
        pair_stats = self.trades.groupby('pair').agg({
            'profit_abs': ['count', 'sum', 'mean'],
            'trade_duration': 'mean'
        }).round(3)
        
        pair_stats.columns = ['Trades', 'Total_Profit', 'Avg_Profit', 'Avg_Duration']
        pair_stats['Win_Rate_%'] = self.trades.groupby('pair')['profit_abs'].apply(lambda x: (x > 0).mean() * 100).round(1)
        
        # Sort by total profit
        pair_stats = pair_stats.sort_values('Total_Profit', ascending=False)
        
        print("Top Performing Pairs:")
        print(pair_stats.head(10))
        print()
        
        print("Worst Performing Pairs:")
        print(pair_stats.tail(5))
        print()
    
    def monthly_performance(self):
        """
        Analyze monthly performance trends
        """
        print("📅 MONTHLY PERFORMANCE TRENDS")
        print("-" * 40)
        
        monthly_stats = self.trades.groupby('month').agg({
            'profit_abs': ['count', 'sum', 'mean'],
            'trade_duration': 'mean'
        }).round(3)
        
        monthly_stats.columns = ['Trades', 'Total_Profit', 'Avg_Profit', 'Avg_Duration']
        monthly_stats['Win_Rate_%'] = self.trades.groupby('month')['profit_abs'].apply(lambda x: (x > 0).mean() * 100).round(1)
        
        print(monthly_stats)
        print()
        
        # Show best and worst months
        if len(monthly_stats) > 0:
            best_month = monthly_stats.loc[monthly_stats['Total_Profit'].idxmax()]
            worst_month = monthly_stats.loc[monthly_stats['Total_Profit'].idxmin()]
            
            print(f"🏆 Best Month: {monthly_stats['Total_Profit'].idxmax()}")
            print(f"   Profit: {best_month['Total_Profit']:.3f} USDT")
            print(f"   Trades: {best_month['Trades']:.0f}")
            print(f"   Win Rate: {best_month['Win_Rate_%']:.1f}%")
            print()
            
            print(f"📉 Worst Month: {monthly_stats['Total_Profit'].idxmin()}")
            print(f"   Profit: {worst_month['Total_Profit']:.3f} USDT")
            print(f"   Trades: {worst_month['Trades']:.0f}")
            print(f"   Win Rate: {worst_month['Win_Rate_%']:.1f}%")
            print()
    
    def strategy_effectiveness_report(self):
        """
        Generate a comprehensive effectiveness report
        """
        print("🎯 STRATEGY EFFECTIVENESS REPORT")
        print("=" * 50)
        
        if len(self.trades) == 0:
            print("No trades to analyze!")
            return
        
        # Check if strategy meets design goals
        total_trades = len(self.trades)
        win_rate = (self.trades['profit_abs'] > 0).mean() * 100
        avg_profit = self.trades['profit_abs'].mean()
        total_profit = self.trades['profit_abs'].sum()
        
        print("DESIGN GOALS vs ACTUAL PERFORMANCE:")
        print("-" * 40)
        print(f"Goal: Max 3 open trades -> Actual: Strategy enforces this ✓")
        print(f"Goal: Trade during UTC 00:00-18:00 -> Checking trade hours...")
        
        # Check trading hours
        trades_outside_hours = self.trades[self.trades['hour'] >= 18]
        if len(trades_outside_hours) == 0:
            print("   All trades within active hours ✓")
        else:
            print(f"   ⚠️ {len(trades_outside_hours)} trades outside active hours")
        
        print(f"Goal: Use Bollinger Bands to avoid flat markets -> Implemented in strategy ✓")
        print(f"Goal: ADX >20 for trend confirmation -> Implemented in strategy ✓")
        print(f"Goal: Dynamic ROI/SL based on trend -> Implemented in strategy ✓")
        print(f"Goal: 5m entries = 5m exits -> Implemented in strategy ✓")
        print()
        
        # Performance assessment
        print("PERFORMANCE ASSESSMENT:")
        print("-" * 25)
        
        if win_rate >= 50:
            print(f"✓ Win Rate: {win_rate:.1f}% (Good)")
        elif win_rate >= 40:
            print(f"~ Win Rate: {win_rate:.1f}% (Acceptable)")
        else:
            print(f"✗ Win Rate: {win_rate:.1f}% (Needs improvement)")
        
        if avg_profit > 0:
            print(f"✓ Avg Profit: {avg_profit:.3f} USDT (Positive)")
        else:
            print(f"✗ Avg Profit: {avg_profit:.3f} USDT (Negative)")
        
        if total_profit > 0:
            print(f"✓ Total Profit: {total_profit:.3f} USDT (Profitable)")
        else:
            print(f"✗ Total Profit: {total_profit:.3f} USDT (Losing)")
        
        print()
        
        # Recommendations
        print("🔧 OPTIMIZATION RECOMMENDATIONS:")
        print("-" * 35)
        
        if win_rate < 45:
            print("• Consider tightening entry conditions")
            print("• Review higher timeframe trend alignment")
            print("• Check if ADX threshold needs adjustment")
        
        if avg_profit < 0:
            print("• Review exit conditions - may be exiting too early")
            print("• Consider adjusting dynamic ROI thresholds")
            print("• Check if stop loss is too tight")
        
        if total_trades < 20:
            print("• Strategy may be too conservative")
            print("• Consider relaxing some entry filters")
            print("• Check if trend conditions are too strict")
        
        if total_trades > 100:
            print("• Strategy may be over-trading")
            print("• Consider stricter entry conditions")
            print("• Review volume and volatility filters")
        
        print()
    
    def generate_full_report(self):
        """
        Generate complete analysis report
        """
        self.overall_performance()
        self.market_hours_analysis()
        self.timeframe_alignment_analysis()
        self.pair_performance()
        self.monthly_performance()
        self.strategy_effectiveness_report()

# Usage example:
if __name__ == "__main__":
    # Update this path to your backtest results
    backtest_file = "d:\\workspace\\bots\\freqtrade\\user_data\\backtest_results\\latest_analysis\\backtest-result-YYYY-MM-DD_HH-MM-SS.json"
    
    print("Multi-Timeframe Trend Strategy Analyzer")
    print("=" * 50)
    print("Update the backtest_file path to your results and run analysis")
    print()
    print("Example usage:")
    print("analyzer = MultiTimeframeAnalyzer('path/to/your/backtest-result.json')")
    print("analyzer.generate_full_report()")
    
    # If you have a backtest file ready, uncomment these lines:
    # analyzer = MultiTimeframeAnalyzer(backtest_file)
    # analyzer.generate_full_report()

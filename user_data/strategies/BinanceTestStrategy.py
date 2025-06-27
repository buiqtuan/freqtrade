from freqtrade.strategy.interface import IStrategy
from freqtrade.persistence import Trade
from pandas import DataFrame
import talib.abstract as ta
import pandas as pd
from datetime import datetime


class BinanceTestStrategy(IStrategy):
    """
    BTC/USDT Optimized Mean Reversion Strategy - Version 2.0
    
    IMPROVEMENT TARGETS:
    - Trade Frequency: 50+ trades (vs 8 previously)
    - Win Rate: 40-60% (vs 25% previously) 
    - Avg Profit: 0.5-1.5% per trade (vs -0.24% previously)
    - Total ROI: 20-50% annually (vs -0.04% previously)
    - Max Drawdown: 5-8% (vs 4% previously)
    
    STRATEGY IMPROVEMENTS:
    - Multiple RSI conditions for better entry timing
    - Bollinger Bands for oversold/overbought detection
    - Enhanced trend confirmation with multiple EMAs
    - Reduced profit target (2%) for higher hit rate
    - Tighter stop losses with dynamic ATR-based management
    - Less aggressive exits to let profits run
    - Increased position sizing and trade frequency
    """
    
    # Strategy interface version - allow new iterations of the strategy interface.
    INTERFACE_VERSION = 3

    # Optimal timeframe for the strategy (5m for scalping)
    timeframe = '5m'

    # Can this strategy go short?
    can_short = False

    # Take profit at 1.2% for better hit rate and realistic target
    minimal_roi = {
        "0": 0.012  # 1.2% profit target for higher win rate
    }

    # Adjusted stop loss for better risk/reward
    stoploss = -0.02  # -2% stop loss (better risk/reward ratio)

    # Enable trailing stop with optimized settings
    trailing_stop = True
    trailing_stop_positive = 0.003  # Start trailing at 0.3% profit (earlier)
    trailing_stop_positive_offset = 0.008  # Trail by 0.8% (tighter)

    # Protection settings - relaxed for more trading opportunities
    protections = [
        {
            "method": "CooldownPeriod",
            "stop_duration_candles": 1  # 5min cooldown (1 * 5min candles) - reduced
        },
        {
            "method": "MaxDrawdown",
            "lookback_period_candles": 200,  # Increased lookback
            "trade_limit": 4,  # Allow more trades before protection
            "stop_duration_candles": 4,  # 20min (reduced from 30min)
            "max_allowed_drawdown": 0.10  # 10% max drawdown (increased tolerance)
        }
    ]

    # Max concurrent trades - reduced for better quality trades
    max_open_trades = 2

    # Use market orders for faster execution
    order_types = {
        'entry': 'market',
        'exit': 'market',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame
        """
        # RSI(14) for entry and exit conditions
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Additional RSI for more granular signals
        dataframe['rsi_fast'] = ta.RSI(dataframe, timeperiod=7)

        # EMAs for trend confirmation
        dataframe['ema_9'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema_21'] = ta.EMA(dataframe, timeperiod=21)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)  # Additional EMA for trend
        
        # MACD for bullish divergence
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        # ATR for dynamic stop loss and volatility
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        # Volume indicators for surge detection
        dataframe['volume_sma'] = ta.SMA(dataframe, timeperiod=20, price='volume')
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # Bollinger Bands for additional signals
        bollinger = ta.BBANDS(dataframe, timeperiod=20)
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_percent'] = (dataframe['close'] - dataframe['bb_lower']) / (dataframe['bb_upper'] - dataframe['bb_lower'])

        # EMA crossover signals
        dataframe['ema_cross_above'] = (
            (dataframe['ema_9'] > dataframe['ema_21']) &
            (dataframe['ema_9'].shift(1) <= dataframe['ema_21'].shift(1))
        )
        
        dataframe['ema_cross_below'] = (
            (dataframe['ema_9'] < dataframe['ema_21']) &
            (dataframe['ema_9'].shift(1) >= dataframe['ema_21'].shift(1))
        )
        
        # Additional trend confirmation
        dataframe['trend_up'] = (
            (dataframe['ema_9'] > dataframe['ema_21']) &
            (dataframe['ema_21'] > dataframe['ema_50'])
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        Entry Conditions (Optimized for 50+ trades with 40-60% win rate):
        - Relaxed RSI conditions for more opportunities
        - Basic trend confirmation
        - Volume surge detection
        """
        dataframe.loc[
            (
                # Balanced RSI conditions for moderate trade frequency  
                (
                    (dataframe['rsi'] < 42) &  # Moderately oversold RSI (relaxed)
                    (dataframe['rsi_fast'] < 38)  # Oversold on fast RSI (relaxed)
                ) &
                
                # Trend confirmation for quality trades
                (
                    (dataframe['trend_up']) |  # Strong uptrend OR
                    (
                        (dataframe['ema_9'] > dataframe['ema_21']) &  # Short-term uptrend
                        (dataframe['ema_cross_above'])  # Recent bullish crossover
                    ) |
                    (dataframe['ema_cross_above'].shift(1))  # Crossover 1 candle ago
                ) &
                
                # Volume and momentum filters (balanced)
                (
                    (dataframe['volume_ratio'] > 1.15) &  # Good volume surge (relaxed)
                    (dataframe['macd'] > dataframe['macdsignal'])   # MACD bullish
                ) &
                
                # Bollinger Band confirmation for mean reversion
                (dataframe['bb_percent'] < 0.35) &  # Near lower BB for better entries (relaxed)
                
                # Basic filters
                (dataframe['volume'] > 0) &  # Volume exists
                (dataframe['atr'] > 0)  # ATR exists (volatility filter)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        Exit Conditions (Optimized for better win rate):
        - Less aggressive exits to let profits run
        - Multiple exit signals for flexibility
        """
        dataframe.loc[
            (
                # More conservative exit conditions to let profits run longer
                (dataframe['rsi'] > 80) |  # Very overbought (increased from 75)
                
                # Strong trend reversal signals
                (
                    (dataframe['ema_cross_below']) &  # EMA bearish crossover
                    (dataframe['rsi'] > 60)  # Only exit on crossover if RSI high
                ) |
                
                # MACD strong deterioration
                (
                    (dataframe['macd'] < dataframe['macdsignal']) &
                    (dataframe['macdhist'] < dataframe['macdhist'].shift(1)) &
                    (dataframe['macdhist'] < 0) &  # MACD histogram negative
                    (dataframe['rsi'] > 65)  # Only if RSI elevated
                ) |
                
                # Bollinger Band exit with confirmation
                (
                    (dataframe['bb_percent'] > 0.95) &  # Very near upper BB
                    (dataframe['rsi'] > 70) &  # RSI very high
                    (dataframe['close'] > dataframe['open'])  # Green candle (resistance)
                )
            ),
            'exit_long'] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Dynamic stop loss based on ATR and trade performance
        Optimized for better risk/reward ratio
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        if 'atr' not in last_candle or pd.isna(last_candle['atr']):
            return self.stoploss  # Fallback to fixed stoploss
        
        # Calculate ATR-based stop loss (optimized for better risk/reward)
        atr_multiplier = 1.8  # Reduced from 2.0 for tighter stops
        atr_stop_distance = (last_candle['atr'] * atr_multiplier) / current_rate
        
        # Dynamic stoploss between -1.2% and -2% (tighter range)
        dynamic_stoploss = max(-0.02, min(-0.012, -atr_stop_distance))
        
        # Trailing stop logic - tighten stop as profit increases
        if current_profit > 0.008:  # If profit > 0.8%
            # Reduce stop loss to lock in profits
            dynamic_stoploss = max(dynamic_stoploss, -0.008)
        
        return dynamic_stoploss

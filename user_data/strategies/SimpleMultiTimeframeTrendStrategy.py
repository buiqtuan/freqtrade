from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import informative, merge_informative_pair
from freqtrade.persistence import Trade
from pandas import DataFrame
import talib.abstract as ta
import pandas as pd
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)


class SimpleMultiTimeframeTrendStrategy(IStrategy):
    """
    Simplified Multi-Timeframe Trend Strategy for Testing
    
    This is a less restrictive version to test the multi-timeframe concept
    """
    
    # Strategy interface version
    INTERFACE_VERSION = 3

    # Primary timeframe for entries/exits
    timeframe = '5m'

    # Cannot short
    can_short = False

    # Simple ROI
    minimal_roi = {
        "0": 0.02,    # 2% profit target
        "60": 0.015,  # 1.5% after 1 hour
        "180": 0.01   # 1% after 3 hours
    }

    # Stop loss
    stoploss = -0.03  # -3% stop loss

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.005  # Start trailing at 0.5%
    trailing_stop_positive_offset = 0.01  # Trail by 1%

    # Maximum 3 open trades
    max_open_trades = 3

    # Protection settings
    protections = [
        {
            "method": "CooldownPeriod",
            "stop_duration_candles": 5  # 25min cooldown
        }
    ]

    # Order types
    order_types = {
        'entry': 'market',
        'exit': 'market',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    def is_market_active(self, current_time: datetime) -> bool:
        """
        Check if current time is within active market hours (UTC 00:00-18:00)
        """
        current_hour = current_time.hour
        return 0 <= current_hour < 18

    @informative('1d')
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Daily timeframe indicators for major trend direction
        """
        # Simple EMA trend
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        
        # Simple trend direction
        dataframe['trend_up'] = dataframe['ema_20'] > dataframe['ema_50']
        
        return dataframe

    @informative('4h')
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        4H timeframe indicators for trend confirmation
        """
        # Simple EMA trend
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        
        # RSI for momentum
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Simple trend direction
        dataframe['trend_up'] = (
            (dataframe['ema_20'] > dataframe['ema_50']) &
            (dataframe['close'] > dataframe['ema_20'])
        )
        
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        5m timeframe indicators for precise entry/exit
        """
        # Simple EMAs
        dataframe['ema_9'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema_21'] = ta.EMA(dataframe, timeperiod=21)
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Bollinger Bands (simplified)
        bollinger = ta.BBANDS(dataframe, timeperiod=20)
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['close']
        
        # Volume
        dataframe['volume_sma'] = ta.SMA(dataframe, timeperiod=10, price='volume')
        
        # Merge higher timeframe data
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '1d'), self.timeframe, '1d', ffill=True)
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '4h'), self.timeframe, '4h', ffill=True)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Simplified multi-timeframe entry logic
        """
        dataframe.loc[
            (
                # Market hours filter (commented out for testing)
                # is_active_hours &
                
                # Higher timeframe trend alignment (simplified)
                (dataframe['trend_up_1d'] == True) &  # Daily uptrend
                (dataframe['trend_up_4h'] == True) &  # 4H uptrend
                
                # 5m entry signals (simplified)
                (dataframe['ema_9'] > dataframe['ema_21']) &  # 5m uptrend
                (dataframe['rsi'] < 60) &  # Not overbought
                (dataframe['rsi'] > 30) &  # Not oversold
                (dataframe['close'] > dataframe['bb_lower']) &  # Above BB lower
                (dataframe['bb_width'] > 0.015) &  # Minimum volatility
                (dataframe['volume'] > dataframe['volume_sma']) &  # Volume confirmation
                
                # Basic filters
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Simplified exit logic
        """
        dataframe.loc[
            (
                # Simple exit conditions
                (dataframe['rsi'] > 70) |  # Overbought
                (dataframe['ema_9'] < dataframe['ema_21']) |  # Trend reversal
                (dataframe['close'] > dataframe['bb_upper'])  # Above BB upper
            ),
            'exit_long'] = 1

        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                          rate: float, time_in_force: str, current_time: datetime,
                          entry_tag: str, side: str, **kwargs) -> bool:
        """
        Market hours check (for testing, allowing all hours initially)
        """
        # For testing, we'll allow all hours first
        # return self.is_market_active(current_time)
        return True

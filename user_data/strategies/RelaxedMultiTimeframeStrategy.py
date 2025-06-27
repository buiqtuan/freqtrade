from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import informative, merge_informative_pair
from freqtrade.persistence import Trade
from pandas import DataFrame
import talib.abstract as ta
import pandas as pd
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)


class RelaxedMultiTimeframeStrategy(IStrategy):
    """
    RELAXED Multi-Timeframe Strategy - Fixed to Generate Trades
    
    KEY CHANGES FROM ORIGINAL:
    - Relaxed RSI from < 45 to < 60 
    - Removed RSI recovery requirement
    - Reduced volume requirement from 1.2x to 1.0x
    - Relaxed Bollinger Band conditions
    - Made trend alignment less strict (OR conditions instead of AND)
    - Reduced ADX requirements
    """
    
    # Strategy interface version
    INTERFACE_VERSION = 3

    # Primary timeframe for entries/exits
    timeframe = '5m'

    # Cannot short
    can_short = False

    # Relaxed ROI 
    minimal_roi = {
        "0": 0.02,    # 2% target
        "60": 0.015,  # 1.5% after 1 hour
        "180": 0.01,  # 1% after 3 hours
        "360": 0.005  # 0.5% after 6 hours
    }

    # Relaxed stop loss
    stoploss = -0.02  # -2% stop loss

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.005  # Start trailing at 0.5%
    trailing_stop_positive_offset = 0.008  # Trail by 0.8%

    # Maximum 3 open trades
    max_open_trades = 3

    # Reduced protection
    protections = [
        {
            "method": "CooldownPeriod", 
            "stop_duration_candles": 1  # 5min cooldown (reduced)
        }
    ]

    # Order types
    order_types = {
        'entry': 'market',
        'exit': 'market',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    @informative('4h')
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ADX for trend strength
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        
        # EMAs for trend direction
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        
        # RSI for momentum
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # RELAXED trend direction (reduced ADX requirement)
        dataframe['trend_up'] = (
            (dataframe['ema_20'] > dataframe['ema_50']) &
            (dataframe['close'] > dataframe['ema_20']) &
            (dataframe['adx'] > 15)  # Reduced from 20 to 15
        )
        
        return dataframe

    @informative('1h')
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMAs
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        
        # RELAXED trend direction
        dataframe['trend_up'] = (
            (dataframe['ema_20'] > dataframe['ema_50']) &
            (dataframe['close'] > dataframe['ema_20'])
            # Removed MACD requirement
        )
        
        return dataframe

    @informative('15m')
    def populate_indicators_15m(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMAs
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        
        # Simple trend direction
        dataframe['trend_up'] = dataframe['ema_20'] > dataframe['ema_50']
        
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMAs for trend
        dataframe['ema_9'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema_21'] = ta.EMA(dataframe, timeperiod=21)
        
        # RSI for momentum
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Bollinger Bands
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_percent'] = (dataframe['close'] - dataframe['bb_lower']) / (dataframe['bb_upper'] - dataframe['bb_lower'])
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['close']
        
        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        
        # Volume indicators
        dataframe['volume_sma'] = ta.SMA(dataframe, timeperiod=20, price='volume')
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # Merge higher timeframe data
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '4h'), self.timeframe, '4h', ffill=True)
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '1h'), self.timeframe, '1h', ffill=True)
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '15m'), self.timeframe, '15m', ffill=True)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        RELAXED Multi-timeframe entry logic
        """
        
        dataframe.loc[
            (
                # RELAXED Higher timeframe trend (OR instead of strict AND)
                (
                    (dataframe['trend_up_4h'] == 1) |  # 4H uptrend OR
                    (dataframe['trend_up_1h'] == 1) |  # 1H uptrend OR  
                    (dataframe['trend_up_15m'] == 1)   # 15m uptrend
                ) &
                
                # RELAXED 5m entry signals
                (
                    # RELAXED RSI condition
                    (dataframe['rsi'] < 60) &  # Increased from 45 to 60
                    # Removed RSI recovery requirement
                    
                    # EMA alignment
                    (dataframe['ema_9'] > dataframe['ema_21']) &
                    
                    # MACD bullish
                    (dataframe['macd'] > dataframe['macdsignal']) &
                    
                    # RELAXED Volume confirmation
                    (dataframe['volume_ratio'] > 1.0) &  # Reduced from 1.2 to 1.0
                    
                    # RELAXED Bollinger Band position
                    (dataframe['bb_width'] > 0.01) &  # Reduced from 0.02 to 0.01
                    (dataframe['bb_percent'] < 0.9) &  # Relaxed from 0.8 to 0.9
                    (dataframe['bb_percent'] > 0.1)    # Relaxed from 0.2 to 0.1
                ) &
                
                # Basic filters
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        5m exit signals
        """
        dataframe.loc[
            (
                # RSI overbought 
                (dataframe['rsi'] > 70) |  # Reduced from 75 to 70
                
                # EMA reversal
                (dataframe['ema_9'] < dataframe['ema_21']) |
                
                # MACD deterioration
                (
                    (dataframe['macd'] < dataframe['macdsignal']) &
                    (dataframe['rsi'] > 55)  # Reduced from 60 to 55
                ) |
                
                # Bollinger Band exit
                (dataframe['bb_percent'] > 0.85)  # Reduced from 0.9 to 0.85
            ),
            'exit_long'] = 1

        return dataframe

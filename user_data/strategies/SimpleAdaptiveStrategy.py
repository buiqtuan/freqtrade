from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import informative, merge_informative_pair
from freqtrade.persistence import Trade
from pandas import DataFrame
import talib.abstract as ta
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SimpleAdaptiveStrategy(IStrategy):
    """
    Simplified Adaptive Strategy that WILL Generate Trades
    
    MARKET DETECTION:
    - EMA200 for long-term trend
    - EMA50 for mid-term momentum  
    - ADX for trend strength
    
    SIMPLIFIED CONDITIONS:
    - UPTREND: Price > EMA50 and EMA50 > EMA200 and ADX > 15 (reduced from 20)
    - DOWNTREND: Price < EMA50 and EMA50 < EMA200 and ADX > 15
    - SIDEWAYS: ADX < 15 or EMAs close together
    
    RELAXED TRADING LOGIC:
    - UPTREND: Buy on any pullback 
    - DOWNTREND: Buy on strong oversold bounces
    - SIDEWAYS: Simple mean reversion
    """
    
    # Strategy interface version
    INTERFACE_VERSION = 3

    # Primary timeframe for entries/exits
    timeframe = '5m'

    # Cannot short
    can_short = False

    # Simple ROI
    minimal_roi = {
        "0": 0.025,   # 2.5% target
        "60": 0.02,   # 2% after 1 hour
        "180": 0.015, # 1.5% after 3 hours
        "360": 0.01   # 1% after 6 hours
    }

    # Simple stop loss
    stoploss = -0.025  # -2.5% stop loss

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.008  # Start trailing at 0.8%
    trailing_stop_positive_offset = 0.012  # Trail by 1.2%

    # Maximum 3 open trades
    max_open_trades = 3

    # Minimal protection
    protections = [
        {
            "method": "CooldownPeriod",
            "stop_duration_candles": 1  # 5min cooldown
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
        """
        4H timeframe for market condition detection
        """
        # EMAs for trend detection
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        
        # ADX for trend strength (RELAXED threshold)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        
        # RSI for momentum
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Market condition detection (SIMPLIFIED)
        ema_diff_pct = abs(dataframe['ema_50'] - dataframe['ema_200']) / dataframe['ema_200'] * 100
        
        # UPTREND: Relaxed conditions
        dataframe['uptrend'] = (
            (dataframe['close'] > dataframe['ema_50']) &
            (dataframe['ema_50'] > dataframe['ema_200']) &
            (dataframe['adx'] > 15)  # Reduced from 20
        )
        
        # DOWNTREND: Relaxed conditions
        dataframe['downtrend'] = (
            (dataframe['close'] < dataframe['ema_50']) &
            (dataframe['ema_50'] < dataframe['ema_200']) &
            (dataframe['adx'] > 15)  # Reduced from 20
        )
        
        # SIDEWAYS: Very relaxed conditions
        dataframe['sideways'] = (
            (dataframe['adx'] < 15) |  # Reduced from 20
            (ema_diff_pct < 2.0)  # EMAs within 2% of each other
        )
        
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        5m timeframe indicators - SIMPLIFIED
        """
        # Basic EMAs
        dataframe['ema_9'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema_21'] = ta.EMA(dataframe, timeperiod=21)
        
        # RSI for momentum
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Simple Bollinger Bands
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_percent'] = (dataframe['close'] - dataframe['bb_lower']) / (dataframe['bb_upper'] - dataframe['bb_lower'])
        
        # Simple MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        
        # Volume (simple)
        dataframe['volume_sma'] = ta.SMA(dataframe, timeperiod=10, price='volume')  # Shorter period
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # Merge 4H data
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '4h'), self.timeframe, '4h', ffill=True)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        VERY SIMPLIFIED entry logic that WILL generate trades
        """
        
        # UPTREND STRATEGY: Buy on any dip
        uptrend_entries = (
            (dataframe['uptrend_4h'] == 1) &
            (
                # ANY of these conditions (very relaxed)
                (dataframe['rsi'] < 60) |  # Most of the time
                (dataframe['close'] < dataframe['ema_21']) |  # Price below short EMA
                (dataframe['bb_percent'] < 0.7)  # Not at upper BB
            ) &
            # Simple momentum check
            (dataframe['ema_9'] > dataframe['ema_21'].shift(2)) &  # EMA trending up (looser)
            (dataframe['volume_ratio'] > 0.8)  # Some volume
        )
        
        # DOWNTREND STRATEGY: Only very oversold bounces
        downtrend_entries = (
            (dataframe['downtrend_4h'] == 1) &
            (
                # Strong oversold conditions
                (dataframe['rsi'] < 30) &
                (dataframe['bb_percent'] < 0.2) &  # Near lower BB
                (dataframe['close'] > dataframe['close'].shift(1)) &  # Price bouncing
                (dataframe['volume_ratio'] > 1.2)  # Volume spike
            )
        )
        
        # SIDEWAYS STRATEGY: Simple mean reversion
        sideways_entries = (
            (dataframe['sideways_4h'] == 1) &
            (
                # Oversold conditions
                (dataframe['rsi'] < 45) &  # Relaxed oversold
                (dataframe['bb_percent'] < 0.4) &  # Lower half of BB
                (dataframe['macd'] > dataframe['macdsignal']) &  # MACD positive
                (dataframe['volume_ratio'] > 0.9)  # Reasonable volume
            )
        )
        
        # Combine all conditions with basic filters
        dataframe.loc[
            (
                (uptrend_entries | downtrend_entries | sideways_entries) &
                (dataframe['volume'] > 0)  # Only basic filter
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        SIMPLIFIED exit logic
        """
        
        # Universal exit conditions (apply to all market types)
        dataframe.loc[
            (
                # RSI overbought
                (dataframe['rsi'] > 75) |
                
                # EMA bearish cross
                (
                    (dataframe['ema_9'] < dataframe['ema_21']) &
                    (dataframe['ema_9'].shift(1) >= dataframe['ema_21'].shift(1))
                ) |
                
                # Near upper Bollinger Band with high RSI
                (
                    (dataframe['bb_percent'] > 0.85) &
                    (dataframe['rsi'] > 65)
                ) |
                
                # MACD bearish with momentum loss
                (
                    (dataframe['macd'] < dataframe['macdsignal']) &
                    (dataframe['rsi'] > 60)
                )
            ),
            'exit_long'] = 1

        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                          rate: float, time_in_force: str, current_time: datetime,
                          entry_tag: str, side: str, **kwargs) -> bool:
        """
        Simple trade confirmation
        """
        # Check max open trades
        if len(Trade.get_open_trades()) >= self.max_open_trades:
            return False
        
        # Get market condition for logging
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) > 0:
            last_candle = dataframe.iloc[-1].squeeze()
            
            market_condition = "unknown"
            if last_candle.get('uptrend_4h', False):
                market_condition = "uptrend"
            elif last_candle.get('downtrend_4h', False):
                market_condition = "downtrend"
            elif last_candle.get('sideways_4h', False):
                market_condition = "sideways"
            
            logger.info(f"Entering {pair} in {market_condition} market")
        
        return True

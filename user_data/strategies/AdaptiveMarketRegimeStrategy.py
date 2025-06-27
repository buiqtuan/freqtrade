from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import informative, merge_informative_pair
from freqtrade.persistence import Trade
from pandas import DataFrame
import talib.abstract as ta
import pandas as pd
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)


class AdaptiveMarketRegimeStrategy(IStrategy):
    """
    Adaptive Market Regime Strategy
    
    Uses EMA200, EMA50, price action, and ADX to detect market conditions:
    - UPTREND: Price > EMA50 > EMA200 & ADX > 20 → Prioritize buys
    - DOWNTREND: Price < EMA50 < EMA200 & ADX > 20 → Limited buys (strong bounces only)
    - SIDEWAYS: ADX < 20 or EMA50 ≈ EMA200 → Mean reversion trades with BB
    
    Each regime has specific entry/exit logic adapted to market conditions.
    """
    
    # Strategy interface version
    INTERFACE_VERSION = 3

    # Primary timeframe for entries/exits
    timeframe = '5m'

    # Cannot short
    can_short = False

    # Adaptive ROI based on market regime
    minimal_roi = {
        "0": 0.025,   # 2.5% target
        "30": 0.02,   # 2% after 30 min
        "120": 0.015, # 1.5% after 2 hours
        "300": 0.01   # 1% after 5 hours
    }

    # Stop loss
    stoploss = -0.025  # -2.5% stop loss

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.008  # Start trailing at 0.8%
    trailing_stop_positive_offset = 0.012  # Trail by 1.2%

    # Maximum open trades
    max_open_trades = 3

    # Protection
    protections = [
        {
            "method": "CooldownPeriod", 
            "stop_duration_candles": 2
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
        """4H timeframe for long-term trend context"""
        # EMAs for trend detection
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        
        # ADX for trend strength
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        
        # Market regime detection
        dataframe['ema_diff_pct'] = ((dataframe['ema_50'] - dataframe['ema_200']) / dataframe['ema_200']) * 100
        
        # Regime classification
        dataframe['uptrend'] = (
            (dataframe['close'] > dataframe['ema_50']) &
            (dataframe['ema_50'] > dataframe['ema_200']) &
            (dataframe['adx'] > 20)
        )
        
        dataframe['downtrend'] = (
            (dataframe['close'] < dataframe['ema_50']) &
            (dataframe['ema_50'] < dataframe['ema_200']) &
            (dataframe['adx'] > 20)
        )
        
        dataframe['sideways'] = (
            (dataframe['adx'] < 20) |
            (abs(dataframe['ema_diff_pct']) < 1.0)  # EMA50 ≈ EMA200 within 1%
        )
        
        return dataframe

    @informative('1h')
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """1H timeframe for medium-term context"""
        # EMAs
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        
        # ADX
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        
        # RSI for momentum
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Similar regime detection for 1H confirmation
        dataframe['ema_diff_pct'] = ((dataframe['ema_50'] - dataframe['ema_200']) / dataframe['ema_200']) * 100
        
        dataframe['uptrend'] = (
            (dataframe['close'] > dataframe['ema_50']) &
            (dataframe['ema_50'] > dataframe['ema_200']) &
            (dataframe['adx'] > 18)  # Slightly more relaxed for 1H
        )
        
        dataframe['downtrend'] = (
            (dataframe['close'] < dataframe['ema_50']) &
            (dataframe['ema_50'] < dataframe['ema_200']) &
            (dataframe['adx'] > 18)
        )
        
        dataframe['sideways'] = (
            (dataframe['adx'] < 18) |
            (abs(dataframe['ema_diff_pct']) < 1.2)
        )
        
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """5m timeframe indicators for entry/exit signals"""
        
        # EMAs for trend and signals
        dataframe['ema_9'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema_21'] = ta.EMA(dataframe, timeperiod=21)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        
        # ADX for trend strength
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        
        # RSI for momentum and overbought/oversold
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Bollinger Bands for mean reversion
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_percent'] = (dataframe['close'] - dataframe['bb_lower']) / (dataframe['bb_upper'] - dataframe['bb_lower'])
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']
        
        # MACD for momentum
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macd_hist'] = macd['macdhist']
        
        # Volume indicators
        dataframe['volume_sma'] = ta.SMA(dataframe, timeperiod=20, price='volume')
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # 5m Market regime detection
        dataframe['ema_diff_pct'] = ((dataframe['ema_50'] - dataframe['ema_200']) / dataframe['ema_200']) * 100
        
        dataframe['uptrend_5m'] = (
            (dataframe['close'] > dataframe['ema_50']) &
            (dataframe['ema_50'] > dataframe['ema_200']) &
            (dataframe['adx'] > 20)
        )
        
        dataframe['downtrend_5m'] = (
            (dataframe['close'] < dataframe['ema_50']) &
            (dataframe['ema_50'] < dataframe['ema_200']) &
            (dataframe['adx'] > 20)
        )
        
        dataframe['sideways_5m'] = (
            (dataframe['adx'] < 20) |
            (abs(dataframe['ema_diff_pct']) < 1.0)
        )
        
        # Merge higher timeframe data
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '4h'), self.timeframe, '4h', ffill=True)
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '1h'), self.timeframe, '1h', ffill=True)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adaptive entry logic based on market regime
        """
        
        # UPTREND LOGIC: Prioritize buys on dips
        uptrend_condition = (
            # Higher timeframe uptrend confirmation
            (
                (dataframe['uptrend_4h'] == 1) |  # 4H uptrend OR
                (dataframe['uptrend_1h'] == 1)    # 1H uptrend
            ) &
            
            # 5m entry signals for uptrend
            (
                # Price above key EMAs or slight dip
                (
                    (dataframe['close'] > dataframe['ema_21']) |  # Above EMA21 OR
                    (dataframe['close'] > dataframe['ema_9'])     # Above EMA9 (minor dip)
                ) &
                
                # RSI not overbought, allow some momentum
                (dataframe['rsi'] < 75) &
                (dataframe['rsi'] > 35) &  # Not oversold either
                
                # EMA alignment (short-term bullish)
                (dataframe['ema_9'] > dataframe['ema_21']) &
                
                # MACD momentum
                (
                    (dataframe['macd'] > dataframe['macdsignal']) |  # Bullish MACD OR
                    (dataframe['macd_hist'] > dataframe['macd_hist'].shift(1))  # Improving MACD
                ) &
                
                # Volume confirmation
                (dataframe['volume_ratio'] > 0.8) &
                
                # Not at Bollinger upper band (avoid buying tops)
                (dataframe['bb_percent'] < 0.85)
            )
        )
        
        # DOWNTREND LOGIC: Only strong bounce setups
        downtrend_condition = (
            # Higher timeframe downtrend
            (
                (dataframe['downtrend_4h'] == 1) |
                (dataframe['downtrend_1h'] == 1)
            ) &
            
            # 5m bounce signals in downtrend
            (
                # Oversold bounce setup
                (dataframe['rsi'] < 35) &  # Oversold
                (dataframe['rsi'] > dataframe['rsi'].shift(1)) &  # RSI improving
                
                # Bollinger Band bounce
                (dataframe['bb_percent'] < 0.2) &  # Near lower BB
                (dataframe['close'] > dataframe['bb_lower']) &  # Above lower BB
                
                # MACD showing improvement
                (dataframe['macd_hist'] > dataframe['macd_hist'].shift(1)) &
                
                # Strong volume on bounce
                (dataframe['volume_ratio'] > 1.2) &
                
                # Price action improvement
                (dataframe['close'] > dataframe['close'].shift(1))  # Green candle
            )
        )
        
        # SIDEWAYS LOGIC: Mean reversion trades
        sideways_condition = (
            # Higher timeframe sideways
            (
                (dataframe['sideways_4h'] == 1) |
                (dataframe['sideways_1h'] == 1) |
                (dataframe['sideways_5m'] == 1)
            ) &
            
            # 5m mean reversion signals
            (
                # Oversold conditions for mean reversion
                (
                    (dataframe['rsi'] < 40) &  # Oversold RSI
                    (dataframe['bb_percent'] < 0.25)  # Near lower Bollinger Band
                ) |
                
                # Support bounce
                (
                    (dataframe['close'] > dataframe['ema_50']) &  # Above EMA50
                    (dataframe['rsi'] < 50) &  # Not overbought
                    (dataframe['bb_percent'] < 0.4) &  # Below middle BB
                    (dataframe['macd'] > dataframe['macdsignal'])  # MACD bullish
                )
            ) &
            
            # Volume and momentum filters
            (dataframe['volume_ratio'] > 0.6) &
            (dataframe['bb_width'] > 0.015)  # Sufficient volatility
        )
        
        # Combine all conditions
        dataframe.loc[
            (
                (uptrend_condition | downtrend_condition | sideways_condition) &
                
                # Basic filters
                (dataframe['volume'] > 0) &
                (dataframe['close'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adaptive exit logic based on market regime
        """
        
        # UPTREND EXIT: Ride the trend but exit on momentum loss
        uptrend_exit = (
            (
                (dataframe['uptrend_4h'] == 1) |
                (dataframe['uptrend_1h'] == 1)
            ) &
            (
                # RSI overbought
                (dataframe['rsi'] > 75) |
                
                # EMA reversal
                (dataframe['ema_9'] < dataframe['ema_21']) |
                
                # Upper Bollinger Band rejection
                (dataframe['bb_percent'] > 0.9) |
                
                # MACD deterioration
                (
                    (dataframe['macd'] < dataframe['macdsignal']) &
                    (dataframe['rsi'] > 60)
                )
            )
        )
        
        # DOWNTREND EXIT: Quick profits on bounces
        downtrend_exit = (
            (
                (dataframe['downtrend_4h'] == 1) |
                (dataframe['downtrend_1h'] == 1)
            ) &
            (
                # Quick profit taking in downtrend
                (dataframe['rsi'] > 55) |  # Not too greedy
                
                # Bollinger middle band resistance
                (dataframe['bb_percent'] > 0.6) |
                
                # MACD losing momentum
                (dataframe['macd_hist'] < dataframe['macd_hist'].shift(1))
            )
        )
        
        # SIDEWAYS EXIT: Mean reversion targets
        sideways_exit = (
            (
                (dataframe['sideways_4h'] == 1) |
                (dataframe['sideways_1h'] == 1) |
                (dataframe['sideways_5m'] == 1)
            ) &
            (
                # Upper Bollinger Band (sell high in range)
                (dataframe['bb_percent'] > 0.8) |
                
                # Overbought in sideways
                (dataframe['rsi'] > 65) |
                
                # EMA resistance
                (
                    (dataframe['close'] < dataframe['ema_21']) &
                    (dataframe['rsi'] > 50)
                )
            )
        )
        
        # General exit conditions (apply to all regimes)
        general_exit = (
            # Strong reversal signals
            (dataframe['rsi'] > 80) |  # Extreme overbought
            
            # Volume spike with rejection
            (
                (dataframe['volume_ratio'] > 2.0) &
                (dataframe['close'] < dataframe['open'])  # Red candle with high volume
            )
        )
        
        # Combine all exit conditions
        dataframe.loc[
            (uptrend_exit | downtrend_exit | sideways_exit | general_exit),
            'exit_long'] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Custom stoploss logic adapted to market regime
        """
        
        # Get current dataframe
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return self.stoploss
            
        latest_candle = dataframe.iloc[-1]
        
        # Adaptive stoploss based on market regime
        if latest_candle.get('uptrend_4h', 0) or latest_candle.get('uptrend_1h', 0):
            # Wider stops in uptrend to ride trends
            return -0.03  # -3%
        elif latest_candle.get('downtrend_4h', 0) or latest_candle.get('downtrend_1h', 0):
            # Tighter stops in downtrend (quick bounces)
            return -0.02  # -2%
        else:  # Sideways
            # Standard stops for mean reversion
            return -0.025  # -2.5%

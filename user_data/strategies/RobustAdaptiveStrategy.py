from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import informative, merge_informative_pair
from freqtrade.persistence import Trade
from pandas import DataFrame
import talib.abstract as ta
import pandas as pd
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)


class RobustAdaptiveStrategy(IStrategy):
    """
    Robust Adaptive Multi-Timeframe Strategy
    
    Final production-ready strategy that balances trade generation with quality:
    - EMA200, EMA50, price action, and ADX for market regime detection
    - Adaptive logic for uptrend, downtrend, and sideways markets
    - Relaxed enough to generate trades but selective enough for good win rate
    - Built on learnings from SelectiveAdaptiveStrategy (52.8% win rate, -1.9% loss)
    
    Target: Profitable returns with 50%+ win rate and reasonable trade frequency
    """
    
    # Strategy interface version
    INTERFACE_VERSION = 3

    # Primary timeframe for entries/exits
    timeframe = '5m'

    # Cannot short
    can_short = False

    # Balanced ROI
    minimal_roi = {
        "0": 0.05,    # 5% target
        "60": 0.035,  # 3.5% after 1 hour
        "180": 0.025, # 2.5% after 3 hours
        "360": 0.02,  # 2% after 6 hours
        "720": 0.015  # 1.5% after 12 hours
    }

    # Stop loss
    stoploss = -0.03  # -3% stop loss

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.012  # Start trailing at 1.2%
    trailing_stop_positive_offset = 0.02  # Trail by 2%

    # Maximum open trades
    max_open_trades = 3

    # Protection
    protections = [
        {
            "method": "CooldownPeriod", 
            "stop_duration_candles": 5
        },
        {
            "method": "MaxDrawdown",
            "lookback_period_candles": 200,
            "trade_limit": 10,
            "stop_duration_candles": 10,
            "max_allowed_drawdown": 0.12  # Stop trading if 12% drawdown
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
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        
        # ADX for trend strength
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['di_plus'] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe['di_minus'] = ta.MINUS_DI(dataframe, timeperiod=14)
        
        # RSI for momentum
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Trend classification - more relaxed than ultra-strict version
        dataframe['uptrend'] = (
            (dataframe['close'] > dataframe['ema_50']) &
            (dataframe['ema_50'] > dataframe['ema_200']) &
            (dataframe['adx'] > 22) &  # Moderate trend strength
            (dataframe['di_plus'] > dataframe['di_minus']) &
            (dataframe['rsi'] > 45) & (dataframe['rsi'] < 80)
        )
        
        dataframe['downtrend'] = (
            (dataframe['close'] < dataframe['ema_50']) &
            (dataframe['ema_50'] < dataframe['ema_200']) &
            (dataframe['adx'] > 22) &
            (dataframe['di_minus'] > dataframe['di_plus']) &
            (dataframe['rsi'] < 55) & (dataframe['rsi'] > 20)
        )
        
        dataframe['sideways'] = (
            (dataframe['adx'] < 22) |
            (abs(dataframe['ema_50'] - dataframe['ema_200']) / dataframe['ema_200'] < 0.02)
        )
        
        return dataframe

    @informative('1h')
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """1H timeframe for medium-term context"""
        # EMAs
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_100'] = ta.EMA(dataframe, timeperiod=100)
        
        # ADX and DI
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['di_plus'] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe['di_minus'] = ta.MINUS_DI(dataframe, timeperiod=14)
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Volume
        dataframe['volume_sma'] = ta.SMA(dataframe, timeperiod=20, price='volume')
        
        # 1H trend confirmation
        dataframe['uptrend_1h'] = (
            (dataframe['close'] > dataframe['ema_20']) &
            (dataframe['ema_20'] > dataframe['ema_50']) &
            (dataframe['adx'] > 18) &
            (dataframe['di_plus'] > dataframe['di_minus'])
        )
        
        dataframe['downtrend_1h'] = (
            (dataframe['close'] < dataframe['ema_20']) &
            (dataframe['ema_20'] < dataframe['ema_50']) &
            (dataframe['adx'] > 18) &
            (dataframe['di_minus'] > dataframe['di_plus'])
        )
        
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """5m timeframe indicators for entry/exit signals"""
        
        # EMAs for trend and signals
        dataframe['ema_9'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema_21'] = ta.EMA(dataframe, timeperiod=21)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_100'] = ta.EMA(dataframe, timeperiod=100)
        
        # ADX system
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['di_plus'] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe['di_minus'] = ta.MINUS_DI(dataframe, timeperiod=14)
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Bollinger Bands
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_percent'] = (dataframe['close'] - dataframe['bb_lower']) / (dataframe['bb_upper'] - dataframe['bb_lower'])
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']
        
        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macd_hist'] = macd['macdhist']
        
        # Stochastic
        stoch = ta.STOCH(dataframe)
        dataframe['slowk'] = stoch['slowk']
        dataframe['slowd'] = stoch['slowd']
        
        # Volume indicators
        dataframe['volume_sma'] = ta.SMA(dataframe, timeperiod=20, price='volume')
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # ATR for volatility
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_pct'] = (dataframe['atr'] / dataframe['close']) * 100
        
        # Merge higher timeframe data
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '4h'), self.timeframe, '4h', ffill=True)
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '1h'), self.timeframe, '1h', ffill=True)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Balanced entry logic - Trade generation with quality focus
        """
        
        # UPTREND ENTRIES: Pullbacks and momentum trades
        uptrend_entry = (
            # 4H uptrend OR 1H uptrend (more flexible)
            (
                (dataframe['uptrend_4h'] == 1) |
                (dataframe['uptrend_1h_1h'] == 1)
            ) &
            
            # 5m entry conditions
            (
                # EMA pullback entries
                (
                    (dataframe['close'] > dataframe['ema_21']) &
                    (dataframe['close'] <= dataframe['ema_21'] * 1.012) &  # Within 1.2% of EMA21
                    (dataframe['ema_9'] > dataframe['ema_21'])  # Short-term bullish
                ) |
                
                # Oversold bounce in uptrend
                (
                    (dataframe['rsi'] < 42) &  # Oversold but not extreme
                    (dataframe['rsi'] > dataframe['rsi'].shift(1)) &  # RSI improving
                    (dataframe['bb_percent'] < 0.35) &  # Lower part of BB
                    (dataframe['close'] > dataframe['ema_50'])  # Above medium-term trend
                ) |
                
                # Momentum continuation
                (
                    (dataframe['close'] > dataframe['ema_9']) &
                    (dataframe['ema_9'] > dataframe['ema_21']) &
                    (dataframe['rsi'] > 50) & (dataframe['rsi'] < 70) &
                    (dataframe['macd'] > dataframe['macdsignal'])
                )
            ) &
            
            # Additional confirmations
            (dataframe['volume_ratio'] > 0.9) &
            (dataframe['slowk'] < 80) &  # Not overbought
            (dataframe['bb_percent'] < 0.8)  # Not at upper BB
        )
        
        # DOWNTREND BOUNCE ENTRIES: Counter-trend with strict conditions
        downtrend_bounce_entry = (
            # 4H downtrend
            (dataframe['downtrend_4h'] == 1) &
            
            # Oversold bounce conditions
            (dataframe['rsi'] < 32) &  # Oversold
            (dataframe['rsi'] > dataframe['rsi'].shift(1)) &  # RSI improving
            (dataframe['bb_percent'] < 0.15) &  # Very near lower BB
            (dataframe['slowk'] < 25) &  # Stoch oversold
            (dataframe['slowk'] > dataframe['slowk'].shift(1)) &  # Stoch improving
            
            # Volume and price action
            (dataframe['volume_ratio'] > 1.3) &  # Strong volume
            (dataframe['close'] > dataframe['open']) &  # Green candle
            (dataframe['close'] > dataframe['close'].shift(1)) &  # Higher close
            
            # MACD improvement
            (dataframe['macd_hist'] > dataframe['macd_hist'].shift(1))
        )
        
        # SIDEWAYS RANGE ENTRIES: Mean reversion
        sideways_entry = (
            # 4H sideways OR weak trend
            (
                (dataframe['sideways_4h'] == 1) |
                (
                    (dataframe['uptrend_4h'] != 1) &
                    (dataframe['downtrend_4h'] != 1)
                )
            ) &
            
            # Range bottom conditions
            (
                # Lower BB area
                (dataframe['bb_percent'] < 0.25) |
                
                # EMA support
                (
                    (dataframe['close'] <= dataframe['ema_50'] * 1.008) &
                    (dataframe['close'] > dataframe['ema_50'] * 0.992) &
                    (dataframe['rsi'] < 45)
                )
            ) &
            
            # Oversold conditions
            (dataframe['rsi'] < 42) &
            (dataframe['slowk'] < 35) &
            
            # Improvement signals
            (
                (dataframe['rsi'] > dataframe['rsi'].shift(1)) |
                (dataframe['macd_hist'] > dataframe['macd_hist'].shift(1))
            ) &
            
            # Volume and volatility
            (dataframe['volume_ratio'] > 0.7) &
            (dataframe['bb_width'] > 0.015)  # Sufficient range
        )
        
        # Quality filters (less restrictive than ultra-selective version)
        quality_filters = (
            # Basic data quality
            (dataframe['volume'] > 0) &
            (dataframe['close'] > 0) &
            
            # Minimum volume
            (dataframe['volume_ratio'] > 0.6) &
            
            # Volatility bounds
            (dataframe['atr_pct'] > 0.4) & (dataframe['atr_pct'] < 5.0) &
            
            # No extreme price moves
            (abs((dataframe['close'] - dataframe['close'].shift(1)) / dataframe['close'].shift(1)) < 0.04)
        )
        
        # Combine all conditions
        dataframe.loc[
            (
                (uptrend_entry | downtrend_bounce_entry | sideways_entry) &
                quality_filters
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Balanced exit logic to capture profits and limit losses
        """
        
        # UPTREND EXITS
        uptrend_exit = (
            (
                (dataframe['uptrend_4h'] == 1) |
                (dataframe['uptrend_1h_1h'] == 1)
            ) &
            (
                # Overbought conditions
                (dataframe['rsi'] > 76) |
                
                # BB upper rejection
                (
                    (dataframe['bb_percent'] > 0.88) &
                    (dataframe['close'] < dataframe['close'].shift(1))
                ) |
                
                # EMA trend break
                (dataframe['ema_9'] < dataframe['ema_21']) |
                
                # MACD deterioration
                (
                    (dataframe['macd'] < dataframe['macdsignal']) &
                    (dataframe['rsi'] > 62)
                ) |
                
                # Stoch overbought turn
                (
                    (dataframe['slowk'] > 82) &
                    (dataframe['slowk'] < dataframe['slowk'].shift(1))
                )
            )
        )
        
        # DOWNTREND EXITS (quick profits)
        downtrend_exit = (
            (dataframe['downtrend_4h'] == 1) &
            (
                # Quick profit taking
                (dataframe['rsi'] > 52) |
                
                # BB middle resistance
                (dataframe['bb_percent'] > 0.6) |
                
                # Stoch overbought
                (dataframe['slowk'] > 72) |
                
                # MACD losing momentum
                (dataframe['macd_hist'] < dataframe['macd_hist'].shift(1))
            )
        )
        
        # SIDEWAYS EXITS
        sideways_exit = (
            (
                (dataframe['sideways_4h'] == 1) |
                (
                    (dataframe['uptrend_4h'] != 1) &
                    (dataframe['downtrend_4h'] != 1)
                )
            ) &
            (
                # Upper range
                (dataframe['bb_percent'] > 0.78) |
                
                # Overbought in range
                (dataframe['rsi'] > 67) |
                
                # Stoch overbought
                (dataframe['slowk'] > 78) |
                
                # EMA resistance
                (
                    (dataframe['close'] > dataframe['ema_100'] * 1.008) &
                    (dataframe['rsi'] > 58)
                )
            )
        )
        
        # General emergency exits
        emergency_exit = (
            # Extreme overbought
            (dataframe['rsi'] > 84) |
            
            # High volume rejection
            (
                (dataframe['volume_ratio'] > 2.8) &
                (dataframe['close'] < dataframe['open']) &
                (dataframe['bb_percent'] > 0.75)
            ) |
            
            # Extreme volatility
            (dataframe['atr_pct'] > 6.0)
        )
        
        # Combine all exit conditions
        dataframe.loc[
            (uptrend_exit | downtrend_exit | sideways_exit | emergency_exit),
            'exit_long'] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Dynamic stoploss based on market conditions
        """
        
        # Get current dataframe
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return self.stoploss
            
        latest_candle = dataframe.iloc[-1]
        
        # Base stop loss
        base_stop = -0.03
        
        # ATR adjustment
        atr_pct = latest_candle.get('atr_pct', 2.0)
        if atr_pct > 3.0:  # High volatility
            atr_adjustment = -0.007  # Wider stop
        elif atr_pct < 1.0:  # Low volatility
            atr_adjustment = 0.005  # Tighter stop
        else:
            atr_adjustment = 0
        
        # Market regime adjustment
        if latest_candle.get('uptrend_4h', 0):
            regime_adjustment = -0.003  # Slightly wider in uptrend
        elif latest_candle.get('downtrend_4h', 0):
            regime_adjustment = 0.003  # Tighter in downtrend (counter-trend)
        else:
            regime_adjustment = 0  # Standard for sideways
        
        # Final calculation
        final_stop = base_stop + atr_adjustment + regime_adjustment
        
        # Bounds
        return max(min(final_stop, -0.015), -0.045)

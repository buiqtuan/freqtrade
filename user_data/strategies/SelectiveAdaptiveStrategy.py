from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import informative, merge_informative_pair
from freqtrade.persistence import Trade
from pandas import DataFrame
import talib.abstract as ta
import pandas as pd
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)


class SelectiveAdaptiveStrategy(IStrategy):
    """
    Selective Adaptive Strategy - Quality over Quantity
    
    Uses EMA200, EMA50, price action, and ADX for market regime detection
    with much more selective entry criteria to improve win rate and reduce losses.
    
    Key improvements:
    - Stricter entry conditions for better trade quality
    - Enhanced trend confirmation across multiple timeframes
    - Better risk/reward filtering
    - Adaptive stop losses based on market volatility
    """
    
    # Strategy interface version
    INTERFACE_VERSION = 3

    # Primary timeframe for entries/exits
    timeframe = '5m'

    # Cannot short
    can_short = False

    # More conservative ROI
    minimal_roi = {
        "0": 0.04,    # 4% target (higher for quality trades)
        "60": 0.03,   # 3% after 1 hour
        "180": 0.02,  # 2% after 3 hours
        "360": 0.015  # 1.5% after 6 hours
    }

    # Stop loss
    stoploss = -0.03  # -3% stop loss (wider for volatility)

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.012  # Start trailing at 1.2%
    trailing_stop_positive_offset = 0.018  # Trail by 1.8%

    # Maximum open trades
    max_open_trades = 3

    # Protection - more conservative
    protections = [
        {
            "method": "CooldownPeriod", 
            "stop_duration_candles": 5  # Longer cooldown
        },
        {
            "method": "MaxDrawdown",
            "lookback_period_candles": 200,
            "trade_limit": 10,
            "stop_duration_candles": 10,
            "max_allowed_drawdown": 0.15  # Stop trading if 15% drawdown
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
        
        # Strong trend detection (strict)
        dataframe['strong_uptrend'] = (
            (dataframe['close'] > dataframe['ema_20']) &
            (dataframe['ema_20'] > dataframe['ema_50']) &
            (dataframe['ema_50'] > dataframe['ema_200']) &
            (dataframe['adx'] > 25) &  # Strong trend
            (dataframe['di_plus'] > dataframe['di_minus']) &
            (dataframe['rsi'] > 45) & (dataframe['rsi'] < 75)  # Not overbought
        )
        
        dataframe['strong_downtrend'] = (
            (dataframe['close'] < dataframe['ema_20']) &
            (dataframe['ema_20'] < dataframe['ema_50']) &
            (dataframe['ema_50'] < dataframe['ema_200']) &
            (dataframe['adx'] > 25) &
            (dataframe['di_minus'] > dataframe['di_plus']) &
            (dataframe['rsi'] < 55) & (dataframe['rsi'] > 25)  # Not oversold
        )
        
        dataframe['sideways'] = (
            (dataframe['adx'] < 25) &
            (abs(dataframe['ema_20'] - dataframe['ema_50']) / dataframe['ema_50'] < 0.02)  # EMAs close
        )
        
        return dataframe

    @informative('1h')
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """1H timeframe for medium-term context"""
        # EMAs
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        
        # ADX and DI
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['di_plus'] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe['di_minus'] = ta.MINUS_DI(dataframe, timeperiod=14)
        
        # RSI for momentum
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Volume
        dataframe['volume_sma'] = ta.SMA(dataframe, timeperiod=20, price='volume')
        
        # Trend confirmation
        dataframe['uptrend_1h'] = (
            (dataframe['close'] > dataframe['ema_20']) &
            (dataframe['ema_20'] > dataframe['ema_50']) &
            (dataframe['adx'] > 20) &
            (dataframe['di_plus'] > dataframe['di_minus'])
        )
        
        dataframe['downtrend_1h'] = (
            (dataframe['close'] < dataframe['ema_20']) &
            (dataframe['ema_20'] < dataframe['ema_50']) &
            (dataframe['adx'] > 20) &
            (dataframe['di_minus'] > dataframe['di_plus'])
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
        dataframe['di_plus'] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe['di_minus'] = ta.MINUS_DI(dataframe, timeperiod=14)
        
        # RSI for momentum
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_sma'] = ta.SMA(dataframe, timeperiod=5, price='rsi')  # Smoothed RSI
        
        # Bollinger Bands for volatility and entry points
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_percent'] = (dataframe['close'] - dataframe['bb_lower']) / (dataframe['bb_upper'] - dataframe['bb_lower'])
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']
        
        # MACD for momentum confirmation
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macd_hist'] = macd['macdhist']
        
        # Stochastic for additional momentum
        stoch = ta.STOCH(dataframe)
        dataframe['slowk'] = stoch['slowk']
        dataframe['slowd'] = stoch['slowd']
        
        # Volume indicators
        dataframe['volume_sma'] = ta.SMA(dataframe, timeperiod=20, price='volume')
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # Average True Range for volatility
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_pct'] = (dataframe['atr'] / dataframe['close']) * 100
        
        # Merge higher timeframe data
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '4h'), self.timeframe, '4h', ffill=True)
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '1h'), self.timeframe, '1h', ffill=True)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Highly selective entry logic - Quality over Quantity
        """
        
        # STRONG UPTREND ENTRIES: Only highest probability setups
        strong_uptrend_entry = (
            # 4H strong uptrend confirmation
            (dataframe['strong_uptrend_4h'] == 1) &
            
            # 1H trend alignment
            (dataframe['uptrend_1h_1h'] == 1) &
            
            # 5m pullback to value entries
            (
                # Pullback to EMA21 in uptrend
                (
                    (dataframe['close'] <= dataframe['ema_21'] * 1.005) &  # At or slightly above EMA21
                    (dataframe['close'] > dataframe['ema_21'] * 0.995) &   # But not too far below
                    (dataframe['ema_9'] > dataframe['ema_21'])  # Short-term trend still up
                ) |
                
                # Oversold bounce in uptrend
                (
                    (dataframe['rsi'] < 40) &  # Oversold
                    (dataframe['rsi'] > dataframe['rsi'].shift(1)) &  # RSI improving
                    (dataframe['bb_percent'] < 0.3)  # Near lower BB
                )
            ) &
            
            # Momentum confirmation
            (
                (dataframe['macd'] > dataframe['macdsignal']) |  # MACD bullish
                (dataframe['macd_hist'] > dataframe['macd_hist'].shift(1))  # MACD improving
            ) &
            
            # Stochastic not overbought
            (dataframe['slowk'] < 80) &
            
            # Volume confirmation
            (dataframe['volume_ratio'] > 1.0) &
            
            # Volatility filter
            (dataframe['atr_pct'] > 0.5) & (dataframe['atr_pct'] < 4.0) &  # Reasonable volatility
            
            # Not at resistance
            (dataframe['bb_percent'] < 0.75)
        )
        
        # OVERSOLD BOUNCE IN DOWNTREND: Highly selective counter-trend
        downtrend_bounce_entry = (
            # 4H downtrend but not too strong
            (dataframe['strong_downtrend_4h'] == 1) &
            
            # RSI deeply oversold but improving
            (dataframe['rsi'] < 30) &
            (dataframe['rsi'] > dataframe['rsi'].shift(1)) &
            (dataframe['rsi'] > dataframe['rsi'].shift(2)) &  # 2 periods of improvement
            
            # Bollinger band extreme
            (dataframe['bb_percent'] < 0.1) &  # Very near lower BB
            
            # Stochastic oversold and turning
            (dataframe['slowk'] < 20) &
            (dataframe['slowk'] > dataframe['slowk'].shift(1)) &
            
            # Strong volume on bounce
            (dataframe['volume_ratio'] > 1.5) &
            
            # Price action confirmation
            (dataframe['close'] > dataframe['open']) &  # Green candle
            (dataframe['close'] > dataframe['close'].shift(1)) &  # Higher close
            
            # MACD showing improvement
            (dataframe['macd_hist'] > dataframe['macd_hist'].shift(1))
        )
        
        # SIDEWAYS RANGE TRADING: Mean reversion in ranging markets
        sideways_entry = (
            # 4H sideways market
            (dataframe['sideways_4h'] == 1) &
            
            # Near support levels
            (
                # Lower Bollinger Band support
                (dataframe['bb_percent'] < 0.2) |
                
                # EMA support in range
                (
                    (dataframe['close'] <= dataframe['ema_50'] * 1.01) &
                    (dataframe['close'] > dataframe['ema_50'] * 0.98) &
                    (dataframe['rsi'] < 45)
                )
            ) &
            
            # Oversold but not extreme
            (dataframe['rsi'] < 40) &
            (dataframe['rsi'] > 25) &
            
            # Stochastic oversold
            (dataframe['slowk'] < 30) &
            
            # MACD improvement
            (dataframe['macd_hist'] > dataframe['macd_hist'].shift(1)) &
            
            # Sufficient volatility for mean reversion
            (dataframe['bb_width'] > 0.02) &
            
            # Volume confirmation
            (dataframe['volume_ratio'] > 0.8)
        )
        
        # Additional quality filters for ALL entries
        quality_filters = (
            # Basic data quality
            (dataframe['volume'] > 0) &
            (dataframe['close'] > 0) &
            
            # Avoid low liquidity periods
            (dataframe['volume_ratio'] > 0.5) &
            
            # Avoid extreme volatility
            (dataframe['atr_pct'] < 5.0) &
            
            # Trend alignment on 5m (for trend trades)
            (
                (strong_uptrend_entry & (dataframe['ema_9'] > dataframe['ema_21'])) |
                (downtrend_bounce_entry) |  # Counter-trend, no alignment needed
                (sideways_entry)  # Range trading, no alignment needed
            )
        )
        
        # Combine all conditions
        dataframe.loc[
            (
                (strong_uptrend_entry | downtrend_bounce_entry | sideways_entry) &
                quality_filters
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Conservative exit logic to protect profits
        """
        
        # UPTREND EXITS: Protect profits but ride trends
        uptrend_exit = (
            (dataframe['strong_uptrend_4h'] == 1) &
            (
                # Overbought conditions
                (dataframe['rsi'] > 75) |
                
                # Bollinger upper band rejection
                (
                    (dataframe['bb_percent'] > 0.9) &
                    (dataframe['close'] < dataframe['close'].shift(1))  # Rejection candle
                ) |
                
                # EMA trend breakdown
                (dataframe['ema_9'] < dataframe['ema_21']) |
                
                # MACD deterioration with high RSI
                (
                    (dataframe['macd'] < dataframe['macdsignal']) &
                    (dataframe['rsi'] > 65)
                ) |
                
                # Stochastic overbought with divergence
                (
                    (dataframe['slowk'] > 80) &
                    (dataframe['slowk'] < dataframe['slowk'].shift(1))  # Turning down
                )
            )
        )
        
        # DOWNTREND BOUNCE EXITS: Quick profit taking
        downtrend_exit = (
            (dataframe['strong_downtrend_4h'] == 1) &
            (
                # Quick profit target in counter-trend
                (dataframe['rsi'] > 50) |  # Don't be greedy
                
                # Bollinger middle band resistance
                (dataframe['bb_percent'] > 0.5) |
                
                # Stochastic overbought
                (dataframe['slowk'] > 70) |
                
                # MACD losing momentum
                (dataframe['macd_hist'] < dataframe['macd_hist'].shift(1))
            )
        )
        
        # SIDEWAYS EXITS: Mean reversion targets
        sideways_exit = (
            (dataframe['sideways_4h'] == 1) &
            (
                # Upper range target
                (dataframe['bb_percent'] > 0.8) |
                
                # Overbought in range
                (dataframe['rsi'] > 65) |
                
                # Stochastic overbought
                (dataframe['slowk'] > 80) |
                
                # EMA resistance
                (
                    (dataframe['close'] > dataframe['ema_50'] * 1.02) &
                    (dataframe['rsi'] > 55)
                )
            )
        )
        
        # Emergency exits for all conditions
        emergency_exit = (
            # Extreme overbought
            (dataframe['rsi'] > 85) |
            
            # High volume rejection
            (
                (dataframe['volume_ratio'] > 3.0) &
                (dataframe['close'] < dataframe['open']) &  # Red candle
                (dataframe['bb_percent'] > 0.8)  # At upper levels
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
        Dynamic stoploss based on volatility and market regime
        """
        
        # Get current dataframe
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return self.stoploss
            
        latest_candle = dataframe.iloc[-1]
        
        # Get ATR for volatility adjustment
        atr_pct = latest_candle.get('atr_pct', 2.0)
        
        # Base stop loss
        base_stop = -0.03
        
        # Adjust based on volatility
        if atr_pct > 3.0:  # High volatility
            adjusted_stop = base_stop - 0.01  # Wider stop
        elif atr_pct < 1.0:  # Low volatility
            adjusted_stop = base_stop + 0.005  # Tighter stop
        else:
            adjusted_stop = base_stop
        
        # Market regime adjustment
        if latest_candle.get('strong_uptrend_4h', 0):
            # Wider stops in strong uptrends
            adjusted_stop = min(adjusted_stop - 0.005, -0.02)
        elif latest_candle.get('strong_downtrend_4h', 0):
            # Tighter stops in downtrends (counter-trend trades)
            adjusted_stop = max(adjusted_stop + 0.005, -0.05)
        
        return max(adjusted_stop, -0.05)  # Never wider than -5%

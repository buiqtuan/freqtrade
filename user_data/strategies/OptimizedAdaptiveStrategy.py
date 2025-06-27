from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import informative, merge_informative_pair
from freqtrade.persistence import Trade
from pandas import DataFrame
import talib.abstract as ta
import pandas as pd
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)


class OptimizedAdaptiveStrategy(IStrategy):
    """
    Optimized Adaptive Multi-Timeframe Strategy v2.0
    
    Enhanced version based on backtest analysis results:
    - 15m execution timeframe with 4H trend detection
    - Fixed regime-based stop losses (no trailing stops)
    - Time-based filtering to avoid worst performing hours (14:00, 15:00, 17:00 UTC)
    - Improved sideways market filtering using RSI/MACD only (no Bollinger Bands)
    - Enhanced entry signal quality with stricter conditions
    
    Target: Positive returns with improved win rate (>50%) and reduced losses
    """
    
    # Strategy interface version
    INTERFACE_VERSION = 3

    # Primary timeframe for entries/exits
    timeframe = '15m'

    # Cannot short
    can_short = False

    # Optimized ROI - adjusted for 15m timeframe with 5% profit-taking
    minimal_roi = {
        "0": 0.05,    # 5% profit-taking target
        "60": 0.04,   # 4% after 1 hour
        "180": 0.025, # 2.5% after 3 hours
        "360": 0.02,  # 2% after 6 hours
        "720": 0.015  # 1.5% after 12 hours
    }

    # Fixed stop loss per regime (no trailing)
    stoploss = -0.03  # Base 3% stop loss

    # No trailing stop - using fixed regime-based stops
    trailing_stop = False

    # Maximum open trades
    max_open_trades = 3

    # Enhanced protection
    protections = [
        {
            "method": "CooldownPeriod", 
            "stop_duration_candles": 8  # Longer cooldown between trades
        },
        {
            "method": "MaxDrawdown",
            "lookback_period_candles": 150,
            "trade_limit": 8,
            "stop_duration_candles": 15,
            "max_allowed_drawdown": 0.10  # Stop trading if 10% drawdown
        },
        {
            "method": "LowProfitPairs",
            "lookback_period_candles": 400,
            "trade_limit": 20,
            "stop_duration": 120,  # 2 hours
            "required_profit": -0.05  # Block pairs with < -5% profit
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
        
        # ADX and DI for trend strength and direction
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['di_plus'] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe['di_minus'] = ta.MINUS_DI(dataframe, timeperiod=14)
        
        # RSI for momentum
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Volume for confirmation
        dataframe['volume_sma'] = ta.SMA(dataframe, timeperiod=20, price='volume')
        
        # Relaxed trend detection for better trade generation
        dataframe['strong_uptrend'] = (
            (dataframe['close'] > dataframe['ema_50']) &
            (dataframe['ema_50'] > dataframe['ema_200']) &
            (dataframe['adx'] > 22) &  # Reduced from 28 to 22
            (dataframe['di_plus'] > dataframe['di_minus']) &
            (dataframe['rsi'] > 40) & (dataframe['rsi'] < 80)  # Relaxed RSI range
        )
        
        dataframe['strong_downtrend'] = (
            (dataframe['close'] < dataframe['ema_50']) &
            (dataframe['ema_50'] < dataframe['ema_200']) &
            (dataframe['adx'] > 22) &  # Reduced from 28 to 22
            (dataframe['di_minus'] > dataframe['di_plus']) &
            (dataframe['rsi'] < 60) & (dataframe['rsi'] > 20)  # Relaxed RSI range
        )
        
        dataframe['consolidation'] = (
            (dataframe['adx'] < 22) |  # Increased threshold
            (abs(dataframe['ema_50'] - dataframe['ema_200']) / dataframe['ema_200'] < 0.02)  # Use EMA200 as base
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
        
        # RSI and Stochastic
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        stoch = ta.STOCH(dataframe)
        dataframe['slowk'] = stoch['slowk']
        
        # Volume
        dataframe['volume_sma'] = ta.SMA(dataframe, timeperiod=20, price='volume')
        
        # Bollinger Bands for volatility context
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_percent'] = (dataframe['close'] - bollinger['lowerband']) / (bollinger['upperband'] - bollinger['lowerband'])
        
        # More relaxed medium-term trend confirmation
        dataframe['uptrend_1h'] = (
            (dataframe['close'] > dataframe['ema_20']) &
            (dataframe['ema_20'] > dataframe['ema_50']) &
            (dataframe['adx'] > 18) &  # Reduced from 22 to 18
            (dataframe['di_plus'] > dataframe['di_minus'])
        )
        
        dataframe['downtrend_1h'] = (
            (dataframe['close'] < dataframe['ema_20']) &
            (dataframe['ema_20'] < dataframe['ema_50']) &
            (dataframe['adx'] > 18) &  # Reduced from 22 to 18
            (dataframe['di_minus'] > dataframe['di_plus'])
        )
        
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """15m timeframe indicators for entry/exit signals"""
        
        # EMAs for trend and signals
        dataframe['ema_9'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema_21'] = ta.EMA(dataframe, timeperiod=21)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_100'] = ta.EMA(dataframe, timeperiod=100)
        
        # ADX system
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['di_plus'] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe['di_minus'] = ta.MINUS_DI(dataframe, timeperiod=14)
        
        # RSI with multiple periods
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_fast'] = ta.RSI(dataframe, timeperiod=7)
        
        # MACD for momentum
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
        
        # Support/Resistance levels (simplified)
        dataframe['resistance'] = ta.MAX(dataframe['high'], timeperiod=20)
        dataframe['support'] = ta.MIN(dataframe['low'], timeperiod=20)
        
        # Time-based filtering - avoid worst performing hours
        dataframe['hour'] = pd.to_datetime(dataframe.index).hour
        dataframe['weekday'] = pd.to_datetime(dataframe.index).weekday  # 0=Monday, 6=Sunday
        dataframe['is_weekend'] = dataframe['weekday'].isin([5, 6])  # Saturday, Sunday
        dataframe['avoid_time'] = dataframe['hour'].isin([14, 15, 17]) & ~dataframe['is_weekend']  # Relax time filter on weekends
        
        # Merge higher timeframe data
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '4h'), self.timeframe, '4h', ffill=True)
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '1h'), self.timeframe, '1h', ffill=True)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Moderately relaxed entry logic with controlled weekend aggression
        """
        
        # Time-based filter - relaxed on weekends
        time_filter = ~dataframe['avoid_time']
        
        # Weekend aggression multiplier - balanced approach
        weekend_factor = dataframe['is_weekend'] * 0.75  # Between moderate (0.5) and aggressive (1.0)
        
        # BALANCED RELAXED UPTREND ENTRIES
        premium_uptrend_entry = (
            # 4H strong uptrend OR 1H uptrend (balanced relaxation on weekends)
            (
                (dataframe['strong_uptrend_4h'] == 1) |
                (dataframe['uptrend_1h_1h'] == 1) |
                # Weekdays: accept weaker uptrend signals
                ((weekend_factor == 0) & (dataframe['close'] > dataframe['ema_50_4h']) & (dataframe['rsi_4h'] > 46)) |
                # Weekend: more relaxed uptrend signals
                (weekend_factor > 0 & (dataframe['close'] > dataframe['ema_50_4h'] * 0.999) & (dataframe['rsi_4h'] > 43))
            ) &
            
            # 15m entry conditions (balanced relaxation)
            (
                # EMA pullback entry (moderately more permissive)
                (
                    (dataframe['close'] > dataframe['ema_21']) &
                    (dataframe['close'] <= dataframe['ema_21'] * (1.024 + weekend_factor * 0.003)) &  # 2.4% weekdays, 2.6% weekends
                    (dataframe['ema_9'] > dataframe['ema_21'] * (0.9985 - weekend_factor * 0.0015))  # Slightly relaxed on weekends
                ) |
                
                # RSI oversold bounce (balanced relaxation)
                (
                    (dataframe['rsi'] < (42 + weekend_factor * 4)) &  # 42 weekdays, 45 weekends
                    (dataframe['rsi'] > dataframe['rsi'].shift(1)) &
                    (dataframe['close'] > dataframe['ema_50'] * (0.998 - weekend_factor * 0.002))  # Slightly relaxed on weekends
                ) |
                
                # MACD momentum continuation (balanced relaxation)
                (
                    (dataframe['close'] > dataframe['ema_9']) &
                    (dataframe['ema_9'] > dataframe['ema_21'] * (0.9995 - weekend_factor * 0.0015)) &  # Slightly relaxed on weekends
                    (dataframe['rsi'] > (48 - weekend_factor * 3)) & (dataframe['rsi'] < (72 + weekend_factor * 3)) &  # Balanced range
                    (dataframe['macd'] > dataframe['macdsignal'] * (0.99 - weekend_factor * 0.015)) &  # Balanced MACD
                    (dataframe['macd_hist'] > dataframe['macd_hist'].shift(1) * (0.96 - weekend_factor * 0.04))  # Balanced momentum
                )
            ) &
            
            # Momentum confirmation (balanced relaxation)
            (
                (dataframe['macd'] > dataframe['macdsignal'] * (0.99 - weekend_factor * 0.02)) |  # Balanced permissive
                (dataframe['macd_hist'] > dataframe['macd_hist'].shift(1) * (0.96 - weekend_factor * 0.025))  # Balanced relaxed
            ) &
            
            # Volume and basic filters (balanced relaxation)
            (dataframe['volume_ratio'] > (0.72 - weekend_factor * 0.08)) &  # 0.72 weekdays, 0.66 weekends
            (dataframe['slowk'] < (83 + weekend_factor * 4))  # 83 weekdays, 86 weekends
        )
        
        # BALANCED RELAXED OVERSOLD BOUNCE
        selective_bounce_entry = (
            # 4H downtrend context (balanced permissive on weekends)
            (
                (dataframe['strong_downtrend_4h'] == 1) |
                # Weekdays: accept weaker downtrend signals for bounce
                ((weekend_factor == 0) & (dataframe['close'] < dataframe['ema_50_4h']) & (dataframe['rsi_4h'] < 53)) |
                # Weekend: moderately relaxed downtrend signals for bounce
                (weekend_factor > 0 & (dataframe['close'] < dataframe['ema_50_4h'] * 1.005) & (dataframe['rsi_4h'] < 56))
            ) &
            
            # Oversold conditions (balanced relaxation)
            (dataframe['rsi'] < (32 + weekend_factor * 3)) &  # 32 weekdays, 34 weekends
            (dataframe['rsi'] > dataframe['rsi'].shift(1) * (0.985 - weekend_factor * 0.015)) &  # Balanced improvement on weekends
            (dataframe['slowk'] < (27 + weekend_factor * 4)) &  # 27 weekdays, 30 weekends
            
            # MACD improvement (balanced relaxation)
            (dataframe['macd_hist'] > dataframe['macd_hist'].shift(1) * (0.96 - weekend_factor * 0.025)) &
            
            # Volume and price action (balanced relaxation)
            (dataframe['volume_ratio'] > (1.05 - weekend_factor * 0.12)) &  # 1.05 weekdays, 0.96 weekends
            (
                (dataframe['close'] > dataframe['open']) |  # Green candle OR
                (weekend_factor > 0 & (dataframe['close'] > dataframe['open'] * 0.9985))  # Nearly green on weekends
            )
        )
        
        # BALANCED RELAXED SIDEWAYS REVERSAL
        improved_sideways_entry = (
            # 4H consolidation (balanced permissive on weekends)
            (
                (dataframe['consolidation_4h'] == 1) |
                (
                    (dataframe['strong_uptrend_4h'] != 1) &
                    (dataframe['strong_downtrend_4h'] != 1)
                ) |
                # Weekdays: accept broader non-extreme trend
                ((weekend_factor == 0) & (dataframe['rsi_4h'] > 31) & (dataframe['rsi_4h'] < 69)) |
                # Weekend: accept moderately broader non-extreme trend
                (weekend_factor > 0 & (dataframe['rsi_4h'] > 29) & (dataframe['rsi_4h'] < 71))
            ) &
            
            # BALANCED RELAXED RSI-based oversold conditions
            (
                (dataframe['rsi'] < (37 + weekend_factor * 4)) &  # 37 weekdays, 40 weekends
                (dataframe['rsi'] > dataframe['rsi'].shift(1) * (0.985 - weekend_factor * 0.015)) &  # Balanced improvement
                (dataframe['rsi_fast'] > dataframe['rsi_fast'].shift(1) * (0.97 - weekend_factor * 0.025))  # Balanced on weekends
            ) &
            
            # BALANCED RELAXED MACD momentum improvement
            (
                (dataframe['macd_hist'] > dataframe['macd_hist'].shift(1) * (0.94 - weekend_factor * 0.06)) &  # Balanced relaxed
                (
                    (dataframe['macd_hist'] > dataframe['macd_hist'].shift(2) * (0.90 - weekend_factor * 0.10)) |  # Balanced relaxed on weekends
                    (weekend_factor > 0)  # Skip this check on weekends (balanced aggressive)
                ) &
                (
                    (dataframe['macd'] > dataframe['macdsignal'] * (0.98 - weekend_factor * 0.02)) |  # MACD above signal (balanced relaxed)
                    (
                        (dataframe['macd'] > dataframe['macd'].shift(1) * (0.96 - weekend_factor * 0.03)) &  # MACD improving (balanced relaxed)
                        (
                            (dataframe['macd'] > dataframe['macd'].shift(2) * (0.93 - weekend_factor * 0.07)) |  # Consistently improving (balanced relaxed)
                            (weekend_factor > 0)  # Skip this check on weekends
                        )
                    )
                )
            ) &
            
            # Additional quality filters (balanced relaxed)
            (dataframe['slowk'] < (43 + weekend_factor * 6)) &  # 43 weekdays, 47.5 weekends
            (dataframe['volume_ratio'] > (0.72 - weekend_factor * 0.08)) &  # 0.72 weekdays, 0.66 weekends
            (
                (dataframe['close'] > dataframe['open']) |  # Green candle OR
                (weekend_factor > 0 & (dataframe['close'] > dataframe['open'] * 0.9975))  # Nearly green on weekends
            ) &
            (dataframe['close'] > dataframe['ema_50'] * (0.995 - weekend_factor * 0.004)) &  # Balanced EMA requirement on weekends
            
            # Volatility filter (balanced relaxed)
            (dataframe['atr_pct'] > (0.42 - weekend_factor * 0.06))  # 0.42 weekdays, 0.375 weekends
        )
        
        # Balanced quality filters to maintain quality while allowing more entries
        quality_filters = (
            # Time filter - relaxed on weekends
            time_filter &
            
            # Basic data quality
            (dataframe['volume'] > 0) &
            (dataframe['close'] > 0) &
            
            # Minimum liquidity (balanced)
            (dataframe['volume_ratio'] > (0.55 - weekend_factor * 0.08)) &  # 0.55 weekdays, 0.49 weekends
            
            # Volatility bounds (balanced permissive)
            (dataframe['atr_pct'] > (0.38 - weekend_factor * 0.06)) & (dataframe['atr_pct'] < (5.3 + weekend_factor * 0.15)) &  # Balanced range
            
            # No extreme movements (balanced relaxed)
            (abs((dataframe['close'] - dataframe['close'].shift(1)) / dataframe['close'].shift(1)) < (0.043 + weekend_factor * 0.004))  # 4.3% weekdays, 4.6% weekends
        )
        
        # Combine all conditions with entry tags
        dataframe.loc[
            (premium_uptrend_entry & quality_filters),
            ['enter_long', 'enter_tag']] = (1, 'uptrend_entry')
        
        dataframe.loc[
            (selective_bounce_entry & quality_filters),
            ['enter_long', 'enter_tag']] = (1, 'downtrend_bounce')
        
        dataframe.loc[
            (improved_sideways_entry & quality_filters),
            ['enter_long', 'enter_tag']] = (1, 'sideways_reversal')

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Simplified exit logic - only rely on ROI and stop loss
        Range exits and emergency exits removed to prevent premature exits
        """
        
        # No manual exit signals - let ROI and stop loss handle exits
        # This allows trades to naturally reach their profit targets or stop losses
        
        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Fixed regime-based stoploss - no trailing stops
        """
        
        # Get current dataframe
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return self.stoploss
            
        latest_candle = dataframe.iloc[-1]
        
        # Fixed stop loss based on market regime
        if latest_candle.get('strong_uptrend_4h', 0):
            # Wider stops in strong uptrends to ride trends
            regime_stop = -0.035  # 3.5% stop in uptrends
        elif latest_candle.get('strong_downtrend_4h', 0):
            # Tighter stops in downtrends (counter-trend trades)
            regime_stop = -0.025  # 2.5% stop in downtrends
        else:
            # Medium stops for consolidation/sideways
            regime_stop = -0.030  # 3.0% stop in sideways markets
        
        # ATR-based volatility adjustment
        atr_pct = latest_candle.get('atr_pct', 2.0)
        if atr_pct > 3.0:  # High volatility
            volatility_adjustment = -0.005  # Slightly wider stop
        elif atr_pct < 1.0:  # Low volatility
            volatility_adjustment = 0.005  # Slightly tighter stop
        else:
            volatility_adjustment = 0
        
        # Calculate final stop
        final_stop = regime_stop + volatility_adjustment
        
        # Ensure reasonable bounds
        final_stop = max(final_stop, -0.045)  # Never wider than -4.5%
        final_stop = min(final_stop, -0.020)  # Never tighter than -2.0%
        
        return final_stop

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                   current_rate: float, current_profit: float, **kwargs) -> str:
        """
        Custom exit logic - Timeout commented out for testing
        """
        # Calculate trade duration in minutes
        # trade_duration = (current_time - trade.open_date_utc).total_seconds() / 60
        
        # For analysis, log long-running trades but don't exit
        # if trade_duration >= 240:
        #     logger.info(f"Trade {pair} has been open for 4+ hours. Duration: {trade_duration:.1f} min, Profit: {current_profit:.2%}")
        #     # Note: Not exiting on timeout to test natural exits
        
        return None

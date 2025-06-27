from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import informative, merge_informative_pair
from freqtrade.persistence import Trade
from pandas import DataFrame
import talib.abstract as ta
import pandas as pd
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)


class MultiTimeframeTrendStrategy(IStrategy):
    """
    Multi-Timeframe Trend Following Strategy
    
    CONCEPT:
    - Use 4H timeframe to determine overall trend direction
    - Use 15m and 1H for mid-term trend confirmation
    - Execute entries/exits on 5m timeframe based on aligned signals
    - Prioritize buy signals during uptrends, avoid longs during downtrends
    
    KEY FEATURES:
    - Maximum 3 open trades to manage risk
    - Bollinger Bands to avoid flat/ranging markets
    - ADX >20 on 4H to confirm trend strength
    - Dynamic ROI/SL based on 4H trend strength
    - Active trading hours only (UTC 00:00-18:00)
    - 5m entry signals require 5m exit signals for consistency
    """
    
    # Strategy interface version
    INTERFACE_VERSION = 3

    # Primary timeframe for entries/exits
    timeframe = '5m'

    # Cannot short
    can_short = False

    # Dynamic ROI based on trend strength (will be overridden by custom_roi)
    minimal_roi = {
        "0": 0.03,    # 3% for strong trends
        "60": 0.02,   # 2% after 1 hour
        "180": 0.015, # 1.5% after 3 hours
        "360": 0.01   # 1% after 6 hours
    }

    # Dynamic stop loss (will be overridden by custom_stoploss)
    stoploss = -0.025  # -2.5% base stop loss

    # Trailing stop for strong trends
    trailing_stop = True
    trailing_stop_positive = 0.005  # Start trailing at 0.5%
    trailing_stop_positive_offset = 0.01  # Trail by 1%

    # Maximum 3 open trades
    max_open_trades = 3

    # Protection settings
    protections = [
        {
            "method": "CooldownPeriod",
            "stop_duration_candles": 2  # 10min cooldown
        },
        {
            "method": "MaxDrawdown",
            "lookback_period_candles": 288,  # 24 hours
            "trade_limit": 2,
            "stop_duration_candles": 12,  # 1 hour
            "max_allowed_drawdown": 0.08  # 8% max drawdown
        }
    ]

    # Order types
    order_types = {
        'entry': 'market',
        'exit': 'market',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    # Store entry timeframe for each trade
    custom_info = {}

    def is_market_active(self, current_time: datetime) -> bool:
        """
        Check if current time is within active market hours (UTC 00:00-18:00)
        """
        current_hour = current_time.hour
        return 0 <= current_hour < 18



    @informative('4h')
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        4H timeframe indicators for trend confirmation
        """
        # ADX for trend strength
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        
        # EMAs for trend direction
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        
        # RSI for momentum
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Trend direction
        dataframe['trend_up'] = (
            (dataframe['ema_20'] > dataframe['ema_50']) &
            (dataframe['close'] > dataframe['ema_20']) &
            (dataframe['adx'] > 20)
        )
        
        dataframe['trend_down'] = (
            (dataframe['ema_20'] < dataframe['ema_50']) &
            (dataframe['close'] < dataframe['ema_20']) &
            (dataframe['adx'] > 20)
        )
        
        # Trend strength
        dataframe['trend_strength'] = 0
        dataframe.loc[dataframe['adx'] > 25, 'trend_strength'] = 1
        dataframe.loc[dataframe['adx'] > 35, 'trend_strength'] = 2
        
        return dataframe

    @informative('1h')
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        1H timeframe indicators for mid-term trend
        """
        # EMAs
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        
        # Trend direction
        dataframe['trend_up'] = (
            (dataframe['ema_20'] > dataframe['ema_50']) &
            (dataframe['close'] > dataframe['ema_20']) &
            (dataframe['macd'] > dataframe['macdsignal'])
        )
        
        return dataframe

    @informative('15m')
    def populate_indicators_15m(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        15m timeframe indicators for entry timing
        """
        # EMAs
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Bollinger Bands to avoid flat markets
        bollinger = ta.BBANDS(dataframe, timeperiod=20)
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['close']
        
        # Trend direction
        dataframe['trend_up'] = (
            (dataframe['ema_20'] > dataframe['ema_50']) &
            (dataframe['close'] > dataframe['ema_20'])
        )
        
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        5m timeframe indicators for precise entry/exit
        """
        # EMAs for trend
        dataframe['ema_9'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema_21'] = ta.EMA(dataframe, timeperiod=21)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        
        # RSI for momentum
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_fast'] = ta.RSI(dataframe, timeperiod=7)
        
        # Bollinger Bands
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_percent'] = (dataframe['close'] - dataframe['bb_lower']) / (dataframe['bb_upper'] - dataframe['bb_lower'])
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['close']
        
        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']
        
        # Volume indicators
        dataframe['volume_sma'] = ta.SMA(dataframe, timeperiod=20, price='volume')
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # ATR for volatility
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        
        # Merge higher timeframe data (removed 1D)
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '4h'), self.timeframe, '4h', ffill=True)
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '1h'), self.timeframe, '1h', ffill=True)
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '15m'), self.timeframe, '15m', ffill=True)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Multi-timeframe entry logic
        """
        # Current time check for market hours
        current_time = datetime.now()
        is_active_hours = self.is_market_active(current_time)
        
        dataframe.loc[
            (
                # Market hours filter
                is_active_hours &
                
                # 4H trend confirmation (removed 1D dependency)
                (
                    (dataframe['trend_up_4h'] == 1) |  # 4H uptrend OR
                    (
                        (dataframe['adx_4h'] > 20) &  # Strong 4H momentum
                        (dataframe['rsi_4h'] < 70)    # Not overbought
                    )
                ) &
                
                # 1H trend support
                (dataframe['trend_up_1h'] == 1) &
                
                # 15m confirmation
                (dataframe['trend_up_15m'] == 1) &
                
                # 5m entry signals
                (
                    # RSI oversold but recovering
                    (dataframe['rsi'] < 45) &
                    (dataframe['rsi'] > dataframe['rsi'].shift(1)) &
                    
                    # EMA alignment
                    (dataframe['ema_9'] > dataframe['ema_21']) &
                    
                    # MACD bullish
                    (dataframe['macd'] > dataframe['macdsignal']) &
                    
                    # Volume confirmation
                    (dataframe['volume_ratio'] > 1.2) &
                    
                    # Bollinger Band position (avoid flat markets)
                    (dataframe['bb_width'] > 0.02) &  # Minimum volatility
                    (dataframe['bb_percent'] < 0.8) &  # Not at upper band
                    (dataframe['bb_percent'] > 0.2)    # Not at lower band
                ) &
                
                # Basic filters
                (dataframe['volume'] > 0) &
                (dataframe['atr'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        5m exit signals (since we enter on 5m, we exit on 5m)
        """
        dataframe.loc[
            (
                # RSI overbought
                (dataframe['rsi'] > 75) |
                
                # EMA reversal
                (
                    (dataframe['ema_9'] < dataframe['ema_21']) &
                    (dataframe['ema_9'].shift(1) >= dataframe['ema_21'].shift(1))
                ) |
                
                # MACD deterioration
                (
                    (dataframe['macd'] < dataframe['macdsignal']) &
                    (dataframe['macdhist'] < 0) &
                    (dataframe['rsi'] > 60)
                ) |
                
                # Bollinger Band exit
                (
                    (dataframe['bb_percent'] > 0.9) &
                    (dataframe['rsi'] > 65)
                ) |
                
                # Higher timeframe trend reversal
                (
                    (dataframe['trend_down_4h'] == 1) &
                    (dataframe['adx_4h'] > 25)
                )
            ),
            'exit_long'] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Dynamic stop loss based on trend strength and ATR (4H focus, no 1D dependency)
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        if 'atr' not in last_candle or pd.isna(last_candle['atr']):
            return self.stoploss
        
        # Get trend strength from 4H timeframe only
        trend_strength_4h = last_candle.get('trend_strength_4h', 0)
        
        # Base ATR multiplier
        atr_multiplier = 2.0
        
        # Adjust based on 4H trend strength only
        if trend_strength_4h >= 2:
            # Very strong 4H trend - allow more room
            atr_multiplier = 2.5
            base_stop = -0.035
        elif trend_strength_4h >= 1:
            # Strong 4H trend - moderate room
            atr_multiplier = 2.2
            base_stop = -0.03
        else:
            # Weak/no trend - tighter stop
            atr_multiplier = 1.8
            base_stop = -0.025
        
        # Calculate ATR-based stop
        atr_stop_distance = (last_candle['atr'] * atr_multiplier) / current_rate
        dynamic_stoploss = max(base_stop, -atr_stop_distance)
        
        # Trailing stop for profitable trades
        if current_profit > 0.01:  # 1% profit
            # Lock in some profit
            profit_protection = current_profit * 0.4  # Protect 40% of profit
            dynamic_stoploss = max(dynamic_stoploss, profit_protection - current_profit)
        
        return dynamic_stoploss

    def custom_roi(self, pair: str, trade: Trade, current_time: datetime,
                   current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Dynamic ROI based on 4H trend strength (no 1D dependency)
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # Get trend strength from 4H timeframe only
        trend_strength_4h = last_candle.get('trend_strength_4h', 0)
        
        # Calculate trade duration in minutes
        trade_duration = (current_time - trade.open_date_utc).total_seconds() / 60
        
        # Dynamic ROI based on 4H trend strength only
        if trend_strength_4h >= 2:
            # Very strong 4H trend - higher ROI targets
            if trade_duration < 60:
                return 0.04  # 4% within 1 hour
            elif trade_duration < 180:
                return 0.03  # 3% within 3 hours
            else:
                return 0.02  # 2% after 3 hours
        elif trend_strength_4h >= 1:
            # Strong 4H trend - moderate ROI targets
            if trade_duration < 60:
                return 0.03  # 3% within 1 hour
            elif trade_duration < 180:
                return 0.025  # 2.5% within 3 hours
            else:
                return 0.015  # 1.5% after 3 hours
        else:
            # Weak 4H trend - conservative ROI targets
            if trade_duration < 60:
                return 0.02  # 2% within 1 hour
            elif trade_duration < 180:
                return 0.015  # 1.5% within 3 hours
            else:
                return 0.01  # 1% after 3 hours

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                          rate: float, time_in_force: str, current_time: datetime,
                          entry_tag: str, side: str, **kwargs) -> bool:
        """
        Final confirmation before entering trade
        """
        # Check market hours
        if not self.is_market_active(current_time):
            logger.info(f"Trade rejected for {pair}: Outside active market hours")
            return False
        
        # Check max open trades
        if len(Trade.get_open_trades()) >= self.max_open_trades:
            logger.info(f"Trade rejected for {pair}: Max open trades reached")
            return False
        
        # Store entry timeframe info
        self.custom_info[pair] = {
            'entry_timeframe': '5m',
            'entry_time': current_time
        }
        
        return True

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str, amount: float,
                         rate: float, time_in_force: str, exit_reason: str,
                         current_time: datetime, **kwargs) -> bool:
        """
        Confirm trade exit - ensure 5m entries exit on 5m signals
        """
        # Always allow exit for stop losses and ROI
        if exit_reason in ['stop_loss', 'roi', 'trailing_stop_loss']:
            return True
        
        # For signal-based exits, ensure consistency with entry timeframe
        entry_info = self.custom_info.get(pair, {})
        entry_timeframe = entry_info.get('entry_timeframe', '5m')
        
        # Since we only enter on 5m, we should exit on 5m signals
        if entry_timeframe == '5m':
            return True
        
        return True

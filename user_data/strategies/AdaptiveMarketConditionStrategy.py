from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import informative, merge_informative_pair
from freqtrade.persistence import Trade
from pandas import DataFrame
import talib.abstract as ta
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AdaptiveMarketConditionStrategy(IStrategy):
    """
    Adaptive Multi-Market Condition Strategy
    
    MARKET DETECTION:
    - EMA200 for long-term trend
    - EMA50 for mid-term momentum  
    - Price action vs EMAs
    - ADX for trend strength
    
    MARKET CONDITIONS:
    - UPTREND: Price > EMA50 and EMA50 > EMA200 and ADX > 20
    - DOWNTREND: Price < EMA50 and EMA50 < EMA200 and ADX > 20  
    - SIDEWAYS: ADX < 20 or (EMA50 ~ EMA200 ± small margin)
    
    TRADING LOGIC:
    - UPTREND: Prioritize long entries on pullbacks
    - DOWNTREND: Avoid longs, wait for reversal signals
    - SIDEWAYS: Bollinger Band mean reversion with tight stops
    """
    
    # Strategy interface version
    INTERFACE_VERSION = 3

    # Primary timeframe for entries/exits
    timeframe = '5m'

    # Cannot short
    can_short = False

    # Dynamic ROI based on market condition
    minimal_roi = {
        "0": 0.03,    # 3% target (will be adjusted dynamically)
        "60": 0.02,   # 2% after 1 hour
        "180": 0.015, # 1.5% after 3 hours
        "360": 0.01   # 1% after 6 hours
    }

    # Dynamic stop loss (will be overridden by custom_stoploss)
    stoploss = -0.025  # -2.5% base stop loss

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.008  # Start trailing at 0.8%
    trailing_stop_positive_offset = 0.012  # Trail by 1.2%

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
            "lookbook_period_candles": 200,
            "trade_limit": 2,
            "stop_duration_candles": 10,
            "max_allowed_drawdown": 0.06  # 6% max drawdown
        }
    ]

    # Order types
    order_types = {
        'entry': 'market',
        'exit': 'market', 
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    # Store market condition info
    custom_info = {}

    @informative('4h')
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        4H timeframe for primary trend detection
        """
        # Long-term and mid-term EMAs
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        
        # ADX for trend strength
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        
        # RSI for momentum
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Market condition detection
        ema_diff_pct = abs(dataframe['ema_50'] - dataframe['ema_200']) / dataframe['ema_200'] * 100
        
        # UPTREND: Price > EMA50 and EMA50 > EMA200 and ADX > 20
        dataframe['uptrend'] = (
            (dataframe['close'] > dataframe['ema_50']) &
            (dataframe['ema_50'] > dataframe['ema_200']) &
            (dataframe['adx'] > 20)
        )
        
        # DOWNTREND: Price < EMA50 and EMA50 < EMA200 and ADX > 20
        dataframe['downtrend'] = (
            (dataframe['close'] < dataframe['ema_50']) &
            (dataframe['ema_50'] < dataframe['ema_200']) &
            (dataframe['adx'] > 20)
        )
        
        # SIDEWAYS: ADX < 20 or EMAs close together
        dataframe['sideways'] = (
            (dataframe['adx'] < 20) |
            (ema_diff_pct < 1.5)  # EMAs within 1.5% of each other
        )
        
        # Trend strength score (0-3: weak to very strong)
        dataframe['trend_strength'] = 0
        dataframe.loc[dataframe['adx'] > 20, 'trend_strength'] = 1
        dataframe.loc[dataframe['adx'] > 30, 'trend_strength'] = 2
        dataframe.loc[dataframe['adx'] > 40, 'trend_strength'] = 3
        
        return dataframe

    @informative('1h')
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        1H timeframe for entry timing confirmation
        """
        # EMAs for trend confirmation
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        
        # RSI for momentum
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # MACD for momentum confirmation
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        
        # 1H trend confirmation
        dataframe['trend_up'] = (
            (dataframe['close'] > dataframe['ema_20']) &
            (dataframe['ema_20'] > dataframe['ema_50'])
        )
        
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        5m timeframe indicators for precise entry/exit
        """
        # EMAs for short-term trend
        dataframe['ema_9'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema_21'] = ta.EMA(dataframe, timeperiod=21)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        
        # RSI for momentum and oversold/overbought
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_fast'] = ta.RSI(dataframe, timeperiod=7)
        
        # Bollinger Bands for mean reversion (especially in sideways markets)
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_percent'] = (dataframe['close'] - dataframe['bb_lower']) / (dataframe['bb_upper'] - dataframe['bb_lower'])
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['close']
        
        # MACD for momentum
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']
        
        # Volume indicators
        dataframe['volume_sma'] = ta.SMA(dataframe, timeperiod=20, price='volume')
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # ATR for volatility-based stops
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        
        # Stochastic for additional oversold/overbought signals
        stoch = ta.STOCH(dataframe)
        dataframe['stoch_k'] = stoch['slowk']
        dataframe['stoch_d'] = stoch['slowd']
        
        # Merge higher timeframe data
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '4h'), self.timeframe, '4h', ffill=True)
        dataframe = merge_informative_pair(dataframe, self.dp.get_pair_dataframe(metadata['pair'], '1h'), self.timeframe, '1h', ffill=True)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adaptive entry logic based on market condition
        """
        
        # UPTREND STRATEGY: Prioritize long entries on pullbacks
        uptrend_condition = (
            (dataframe['uptrend_4h'] == 1) &
            
            # Wait for pullback in uptrend
            (
                (dataframe['rsi'] < 50) |  # Pullback in momentum
                (dataframe['close'] < dataframe['ema_21'])  # Price below short EMA
            ) &
            
            # Entry signals
            (
                # RSI recovering from oversold
                (dataframe['rsi'] > dataframe['rsi'].shift(1)) &
                (dataframe['rsi'] > 35) &  # Not extremely oversold
                
                # EMA starting to align
                (dataframe['ema_9'] > dataframe['ema_21'].shift(1)) &
                
                # MACD showing strength
                (dataframe['macd'] > dataframe['macdsignal']) &
                
                # Volume confirmation
                (dataframe['volume_ratio'] > 1.1) &
                
                # 1H trend support
                (dataframe['trend_up_1h'] == 1)
            )
        )
        
        # DOWNTREND STRATEGY: Avoid longs, wait for reversal signals
        downtrend_condition = (
            (dataframe['downtrend_4h'] == 1) &
            
            # Only enter if strong reversal signals
            (
                # Strong oversold bounce
                (dataframe['rsi'] < 25) &
                (dataframe['rsi'] > dataframe['rsi'].shift(2)) &  # RSI rising for 2 periods
                
                # Bollinger Band squeeze and bounce
                (dataframe['bb_percent'] < 0.1) &  # Near lower band
                (dataframe['close'] > dataframe['close'].shift(1)) &  # Price bouncing
                
                # Volume spike
                (dataframe['volume_ratio'] > 1.5) &
                
                # MACD divergence (price lower but MACD higher)
                (dataframe['macd'] > dataframe['macd'].shift(1))
            )
        )
        
        # SIDEWAYS STRATEGY: Bollinger Band mean reversion
        sideways_condition = (
            (dataframe['sideways_4h'] == 1) &
            
            # Mean reversion setup
            (
                # Near lower Bollinger Band (oversold)
                (dataframe['bb_percent'] < 0.3) &
                (dataframe['bb_percent'] > 0.1) &  # Not extreme
                
                # RSI oversold but not extreme
                (dataframe['rsi'] < 40) &
                (dataframe['rsi'] > 25) &
                
                # Stochastic oversold
                (dataframe['stoch_k'] < 30) &
                
                # Price bouncing off support
                (dataframe['close'] > dataframe['close'].shift(1)) &
                
                # Volume confirmation
                (dataframe['volume_ratio'] > 1.0) &
                
                # Bollinger Band not too tight (some volatility)
                (dataframe['bb_width'] > 0.015)
            )
        )
        
        # Combine all conditions
        dataframe.loc[
            (
                (uptrend_condition | downtrend_condition | sideways_condition) &
                
                # Basic filters
                (dataframe['volume'] > 0) &
                (dataframe['atr'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adaptive exit logic based on market condition
        """
        
        # UPTREND EXITS: Let winners run, cut losers quickly
        uptrend_exit = (
            (dataframe['uptrend_4h'] == 1) &
            (
                # RSI extremely overbought
                (dataframe['rsi'] > 80) |
                
                # EMA breakdown
                (
                    (dataframe['ema_9'] < dataframe['ema_21']) &
                    (dataframe['rsi'] > 60)  # Only if we had some profit
                ) |
                
                # MACD divergence
                (
                    (dataframe['macd'] < dataframe['macdsignal']) &
                    (dataframe['macdhist'] < dataframe['macdhist'].shift(1)) &
                    (dataframe['rsi'] > 65)
                )
            )
        )
        
        # DOWNTREND EXITS: Quick exits, don't fight the trend
        downtrend_exit = (
            (dataframe['downtrend_4h'] == 1) &
            (
                # Any sign of weakness
                (dataframe['rsi'] > 60) |
                (dataframe['ema_9'] < dataframe['ema_21']) |
                (dataframe['macd'] < dataframe['macdsignal']) |
                
                # Back to upper Bollinger Band
                (dataframe['bb_percent'] > 0.7)
            )
        )
        
        # SIDEWAYS EXITS: Take profits at resistance, cut losses quickly
        sideways_exit = (
            (dataframe['sideways_4h'] == 1) &
            (
                # Near upper Bollinger Band (resistance)
                (dataframe['bb_percent'] > 0.8) |
                
                # RSI overbought
                (dataframe['rsi'] > 70) |
                
                # Stochastic overbought
                (dataframe['stoch_k'] > 80) |
                
                # Quick exit if goes against us
                (
                    (dataframe['close'] < dataframe['bb_middle']) &
                    (dataframe['rsi'] < 45)
                )
            )
        )
        
        # Universal exits (apply to all market conditions)
        universal_exit = (
            # Volume drying up with negative momentum
            (
                (dataframe['volume_ratio'] < 0.5) &
                (dataframe['rsi'] < 40)
            ) |
            
            # Strong reversal signal
            (
                (dataframe['ema_9'] < dataframe['ema_21']) &
                (dataframe['ema_9'].shift(1) >= dataframe['ema_21'].shift(1)) &  # Just crossed
                (dataframe['macd'] < dataframe['macdsignal'])
            )
        )
        
        dataframe.loc[
            (uptrend_exit | downtrend_exit | sideways_exit | universal_exit),
            'exit_long'] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Dynamic stop loss based on market condition and ATR
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        if 'atr' not in last_candle or pd.isna(last_candle['atr']):
            return self.stoploss
        
        # Get market condition
        is_uptrend = last_candle.get('uptrend_4h', False)
        is_downtrend = last_candle.get('downtrend_4h', False) 
        is_sideways = last_candle.get('sideways_4h', False)
        trend_strength = last_candle.get('trend_strength_4h', 0)
        
        # Base ATR multiplier
        atr_multiplier = 2.0
        
        # Adjust based on market condition
        if is_uptrend:
            # Allow more room in uptrends
            if trend_strength >= 2:
                atr_multiplier = 3.0
                base_stop = -0.04  # 4% max
            else:
                atr_multiplier = 2.5
                base_stop = -0.03  # 3% max
                
        elif is_downtrend:
            # Tight stops in downtrends
            atr_multiplier = 1.5
            base_stop = -0.02  # 2% max
            
        elif is_sideways:
            # Medium stops for sideways (key for mean reversion)
            atr_multiplier = 2.0
            base_stop = -0.025  # 2.5% max - crucial for sideways strategy
            
        else:
            # Default
            atr_multiplier = 2.0
            base_stop = -0.025
        
        # Calculate ATR-based stop
        atr_stop_distance = (last_candle['atr'] * atr_multiplier) / current_rate
        dynamic_stoploss = max(base_stop, -atr_stop_distance)
        
        # Trailing stop for profitable trades
        if current_profit > 0.01:  # 1% profit
            if is_uptrend:
                # Generous trailing in uptrends
                profit_protection = current_profit * 0.3  # Protect 30% of profit
            else:
                # Conservative trailing in other conditions
                profit_protection = current_profit * 0.5  # Protect 50% of profit
                
            dynamic_stoploss = max(dynamic_stoploss, profit_protection - current_profit)
        
        return dynamic_stoploss

    def custom_roi(self, pair: str, trade: Trade, current_time: datetime,
                   current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Dynamic ROI based on market condition
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # Get market condition
        is_uptrend = last_candle.get('uptrend_4h', False)
        is_downtrend = last_candle.get('downtrend_4h', False)
        is_sideways = last_candle.get('sideways_4h', False)
        trend_strength = last_candle.get('trend_strength_4h', 0)
        
        # Calculate trade duration in minutes
        trade_duration = (current_time - trade.open_date_utc).total_seconds() / 60
        
        # Dynamic ROI based on market condition
        if is_uptrend:
            # Let winners run in uptrends
            if trend_strength >= 2:  # Strong uptrend
                if trade_duration < 60:
                    return 0.05  # 5% within 1 hour
                elif trade_duration < 240:
                    return 0.04  # 4% within 4 hours
                else:
                    return 0.03  # 3% after 4 hours
            else:  # Moderate uptrend
                if trade_duration < 60:
                    return 0.03  # 3% within 1 hour
                elif trade_duration < 180:
                    return 0.025  # 2.5% within 3 hours
                else:
                    return 0.02  # 2% after 3 hours
                    
        elif is_downtrend:
            # Quick profits in downtrends (fighting the trend)
            if trade_duration < 30:
                return 0.02  # 2% within 30 minutes
            elif trade_duration < 60:
                return 0.015  # 1.5% within 1 hour
            else:
                return 0.01  # 1% after 1 hour
                
        elif is_sideways:
            # Medium targets for mean reversion
            if trade_duration < 60:
                return 0.025  # 2.5% within 1 hour
            elif trade_duration < 180:
                return 0.02   # 2% within 3 hours
            else:
                return 0.015  # 1.5% after 3 hours
        else:
            # Default conservative targets
            if trade_duration < 60:
                return 0.02   # 2% within 1 hour
            else:
                return 0.015  # 1.5% after 1 hour

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                          rate: float, time_in_force: str, current_time: datetime,
                          entry_tag: str, side: str, **kwargs) -> bool:
        """
        Final trade confirmation with market condition awareness
        """
        # Check max open trades
        if len(Trade.get_open_trades()) >= self.max_open_trades:
            logger.info(f"Trade rejected for {pair}: Max open trades reached")
            return False
        
        # Get current market condition for logging
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        market_condition = "unknown"
        if last_candle.get('uptrend_4h', False):
            market_condition = "uptrend"
        elif last_candle.get('downtrend_4h', False):
            market_condition = "downtrend"
        elif last_candle.get('sideways_4h', False):
            market_condition = "sideways"
        
        # Store entry info
        self.custom_info[pair] = {
            'entry_time': current_time,
            'market_condition': market_condition,
            'entry_rate': rate
        }
        
        logger.info(f"Entering {pair} in {market_condition} market at {rate}")
        return True

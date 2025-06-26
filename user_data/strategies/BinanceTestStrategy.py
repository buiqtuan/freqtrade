from freqtrade.strategy.interface import IStrategy
from freqtrade.persistence import Trade
from pandas import DataFrame
import talib.abstract as ta
import pandas as pd
from datetime import datetime


class BinanceTestStrategy(IStrategy):
    """
    BTC/USDT Mean Reversion Strategy with Trend Confirmation
    Entry: RSI < 30, EMA9 > EMA21, Volume surge
    Exit: 3% profit, RSI > 70, EMA crossover, ATR-based stop loss
    """
    
    # Strategy interface version - allow new iterations of the strategy interface.
    INTERFACE_VERSION = 3

    # Optimal timeframe for the strategy (5m for scalping)
    timeframe = '5m'

    # Can this strategy go short?
    can_short = False

    # Take profit at 3% as specified
    minimal_roi = {
        "0": 0.03  # 3% profit target
    }

    # Dynamic stop loss will be handled in custom_stoploss
    # Base stoploss as fallback
    stoploss = -0.035  # -3.5% max stop loss

    # Enable trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.01  # Start trailing at 1% profit
    trailing_stop_positive_offset = 0.015  # Trail by 1.5% (must be > trailing_stop_positive)

    # Protection settings
    protections = [
        {
            "method": "CooldownPeriod",
            "stop_duration_candles": 3  # 15min cooldown (3 * 5min candles)
        },
        {
            "method": "MaxDrawdown",
            "lookback_period_candles": 200,
            "trade_limit": 1,
            "stop_duration_candles": 12,  # 1 hour
            "max_allowed_drawdown": 0.05  # 5% max drawdown
        }
    ]

    # Max concurrent trades
    max_open_trades = 1

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

        # EMAs for trend confirmation
        dataframe['ema_9'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema_21'] = ta.EMA(dataframe, timeperiod=21)
        
        # MACD for bullish divergence (optional)
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        # ATR for dynamic stop loss
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        # Volume indicators for surge detection
        dataframe['volume_sma'] = ta.SMA(dataframe, timeperiod=20, price='volume')
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']

        # EMA crossover signals
        dataframe['ema_cross_above'] = (
            (dataframe['ema_9'] > dataframe['ema_21']) &
            (dataframe['ema_9'].shift(1) <= dataframe['ema_21'].shift(1))
        )
        
        dataframe['ema_cross_below'] = (
            (dataframe['ema_9'] < dataframe['ema_21']) &
            (dataframe['ema_9'].shift(1) >= dataframe['ema_21'].shift(1))
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        Entry Conditions (More relaxed for better trade frequency):
        - RSI(14) < 35 (oversold - relaxed from 30)
        - EMA(9) > EMA(21) (trend condition - not requiring crossover)
        - Volume surge (>1.2x average volume) OR MACD bullish
        """
        dataframe.loc[
            (
                (dataframe['rsi'] < 35) &  # RSI oversold condition (relaxed)
                (dataframe['ema_9'] > dataframe['ema_21']) &  # Bullish trend (not crossover)
                (
                    (dataframe['volume_ratio'] > 1.2) |  # Volume surge (relaxed) OR
                    (dataframe['macd'] > dataframe['macdsignal'])  # MACD bullish
                ) &
                (dataframe['volume'] > 0)  # Make sure volume is not 0
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        Exit Conditions:
        - RSI(14) > 70 (overbought)
        - EMA(9) crosses below EMA(21)
        - MACD crosses below signal line
        """
        dataframe.loc[
            (
                (dataframe['rsi'] > 70) |  # RSI overbought
                (dataframe['ema_cross_below']) |  # EMA(9) crosses below EMA(21)
                (dataframe['macd'] < dataframe['macdsignal'])  # MACD below signal
            ),
            'exit_long'] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Dynamic stop loss based on ATR
        Uses 2.5x to 3.5x ATR for stop loss calculation
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        if 'atr' not in last_candle or pd.isna(last_candle['atr']):
            return self.stoploss  # Fallback to fixed stoploss
        
        # Calculate ATR-based stop loss
        atr_multiplier = 2.8  # Between 2.5x and 3.5x ATR
        atr_stop_distance = (last_candle['atr'] * atr_multiplier) / current_rate
        
        # Dynamic stop loss between -2.5% and -3.5%
        dynamic_stoploss = max(-0.035, min(-0.025, -atr_stop_distance))
        
        return dynamic_stoploss

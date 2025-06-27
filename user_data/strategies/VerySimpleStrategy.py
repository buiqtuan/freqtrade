from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta

class VerySimpleStrategy(IStrategy):
    """
    Extremely simple strategy that should generate trades
    """
    
    timeframe = '5m'
    can_short = False
    minimal_roi = {"0": 0.02}
    stoploss = -0.02
    max_open_trades = 3
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Minimal indicators
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=5)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=10)
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Very simple entry: fast EMA above slow EMA
        dataframe.loc[
            (dataframe['ema_fast'] > dataframe['ema_slow']) &
            (dataframe['volume'] > 0),
            'enter_long'] = 1
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Very simple exit: fast EMA below slow EMA
        dataframe.loc[
            (dataframe['ema_fast'] < dataframe['ema_slow']),
            'exit_long'] = 1
        return dataframe

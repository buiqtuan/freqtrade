
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta

class SimplifiedTestStrategy(IStrategy):
    timeframe = '5m'
    can_short = False
    minimal_roi = {"0": 0.02}
    stoploss = -0.02
    max_open_trades = 3
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema_9'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema_21'] = ta.EMA(dataframe, timeperiod=21)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['ema_9'] > dataframe['ema_21']) &
                (dataframe['rsi'] < 50) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe['rsi'] > 70),
            'exit_long'] = 1
        return dataframe

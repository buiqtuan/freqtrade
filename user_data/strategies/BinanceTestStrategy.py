from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta


class BinanceTestStrategy(IStrategy):
    """
    Simple test strategy for Binance demo testing
    """
    
    # Strategy interface version - allow new iterations of the strategy interface.
    INTERFACE_VERSION = 3

    # Optimal timeframe for the strategy.
    timeframe = '5m'

    # Can this strategy go short?
    can_short = False

    # Minimal ROI designed for the strategy.
    minimal_roi = {
        "60": 0.01,
        "30": 0.02,
        "0": 0.04
    }

    # Optimal stoploss designed for the strategy.
    stoploss = -0.10

    # Trailing stoploss
    trailing_stop = False

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame
        """
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe)

        # Simple Moving Averages
        dataframe['sma_20'] = ta.SMA(dataframe, timeperiod=20)
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=50)
        
        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        """
        dataframe.loc[
            (
                (dataframe['rsi'] < 40) &  # RSI oversold (less strict)
                (dataframe['sma_20'] > dataframe['sma_50']) &  # Short MA above long MA
                (dataframe['macd'] > dataframe['macdsignal']) &  # MACD above signal
                (dataframe['volume'] > 0)  # Make sure volume is not 0
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        """
        dataframe.loc[
            (
                (dataframe['rsi'] > 70) |  # RSI overbought
                (dataframe['sma_20'] < dataframe['sma_50']) |  # Short MA below long MA
                (dataframe['macd'] < dataframe['macdsignal'])  # MACD below signal
            ),
            'exit_long'] = 1

        return dataframe

from app.engine.strategy import Strategy

class DataCollectionStrategy(Strategy):
    """
    A null strategy that intentionally does not execute any trades.
    It exists purely to keep a live/paper session running, allowing the engine
    to silently harvest live ticks, construct intraday bars, and persist them 
    to the MongoDB historical collection.
    """
    def __init__(self, broker, position_sizer=None):
        super().__init__(broker, position_sizer)

    def on_bar(self, df, current_index):
        # We deliberately do nothing here. The live engine handles building
        # and saving the OHLCV dataframe.
        pass

from app.engine.position_sizing import FullCapitalSizer


class Strategy:
    """
    Base class for all trading strategies.
    Subclasses implement on_bar() with their specific logic
    and call self.buy() / self.sell() to place orders.
    """

    def __init__(self, broker, position_sizer=None):
        self.broker = broker
        self.position_sizer = position_sizer or FullCapitalSizer()

    def on_tick(self, tick_data):
        """Called on every live tick. Override in subclass."""
        pass

    def on_bar(self, df, current_index):
        """Called on every historical bar during backtesting. Override in subclass."""
        pass

    def quantity_for(self, price, df, i):
        """How many shares to buy right now, per the configured PositionSizer
        (defaults to full-capital, i.e. the original always-bet-everything behavior)."""
        return self.position_sizer.size(self.broker.capital, price, df, i)

    def buy(self, symbol, price, quantity, timestamp):
        return self.broker.place_order("BUY", symbol, price, quantity, timestamp)

    def sell(self, symbol, price, quantity, timestamp):
        return self.broker.place_order("SELL", symbol, price, quantity, timestamp)

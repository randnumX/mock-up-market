class Strategy:
    """
    Base class for all trading strategies.
    Subclasses implement on_bar() with their specific logic
    and call self.buy() / self.sell() to place orders.
    """

    def __init__(self, broker):
        self.broker = broker

    def on_tick(self, tick_data):
        """Called on every live tick. Override in subclass."""
        pass

    def on_bar(self, df, current_index):
        """Called on every historical bar during backtesting. Override in subclass."""
        pass

    def buy(self, symbol, price, quantity, timestamp):
        return self.broker.place_order("BUY", symbol, price, quantity, timestamp)

    def sell(self, symbol, price, quantity, timestamp):
        return self.broker.place_order("SELL", symbol, price, quantity, timestamp)

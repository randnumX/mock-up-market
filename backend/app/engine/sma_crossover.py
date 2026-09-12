import pandas as pd
from app.engine.strategy import Strategy


class SMACrossoverStrategy(Strategy):
    """
    Simple Moving Average crossover ("golden cross" / "death cross").

    Buy signal:  fast SMA crosses above slow SMA
    Sell signal: fast SMA crosses below slow SMA
    """

    def __init__(self, broker, fast_period=20, slow_period=50, position_sizer=None):
        super().__init__(broker, position_sizer=position_sizer)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.bought = False

    def on_bar(self, df, current_index):
        i = current_index
        row = df.iloc[i]
        symbol = row.get("scripName", row.get("Security Id", "UNKNOWN"))
        price = row["Value"]
        timestamp = row["priceDate"]

        if i == 0:
            df["sma_fast"] = pd.Series(dtype="float64")
            df["sma_slow"] = pd.Series(dtype="float64")

        df.loc[i, "sma_fast"] = df["Value"].iloc[max(0, i - self.fast_period + 1): i + 1].mean()
        df.loc[i, "sma_slow"] = df["Value"].iloc[max(0, i - self.slow_period + 1): i + 1].mean()

        if i <= self.slow_period:
            return

        fast_curr = df.loc[i, "sma_fast"]
        fast_prev = df.loc[i - 1, "sma_fast"]
        slow_curr = df.loc[i, "sma_slow"]
        slow_prev = df.loc[i - 1, "sma_slow"]

        # Buy: fast SMA crosses above slow SMA
        if fast_curr > slow_curr and fast_prev <= slow_prev and not self.bought:
            quantity = self.quantity_for(price, df, i)
            if quantity > 0:
                if self.buy(symbol, price, quantity, timestamp):
                    self.bought = True

        # Sell: fast SMA crosses below slow SMA
        if fast_curr < slow_curr and fast_prev >= slow_prev and self.bought:
            pos = self.broker.positions.get(symbol, {"qty": 0})
            if pos["qty"] > 0:
                if self.sell(symbol, price, pos["qty"], timestamp):
                    self.bought = False

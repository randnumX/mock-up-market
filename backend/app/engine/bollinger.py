import pandas as pd
from app.engine.strategy import Strategy


class BollingerBandsStrategy(Strategy):
    """
    Bollinger Bands mean-reversion strategy.

    Buy signal:  price closes below the lower band, then closes back above it
    Sell signal: price closes above the upper band, then closes back below it
    """

    def __init__(self, broker, period=20, num_std=2, position_sizer=None):
        super().__init__(broker, position_sizer=position_sizer)
        self.period = period
        self.num_std = num_std
        self.bought = False
        self.was_below_lower = False
        self.was_above_upper = False

    def on_bar(self, df, current_index):
        i = current_index
        row = df.iloc[i]
        symbol = row.get("scripName", row.get("Security Id", "UNKNOWN"))
        price = row["Value"]
        timestamp = row["priceDate"]

        if i == 0:
            df["bb_mid"] = pd.Series(dtype="float64")
            df["bb_upper"] = pd.Series(dtype="float64")
            df["bb_lower"] = pd.Series(dtype="float64")

        window = df["Value"].iloc[max(0, i - self.period + 1): i + 1]
        mid = window.mean()
        std = window.std(ddof=0) if len(window) > 1 else 0

        df.loc[i, "bb_mid"] = mid
        df.loc[i, "bb_upper"] = mid + self.num_std * std
        df.loc[i, "bb_lower"] = mid - self.num_std * std

        if i <= self.period:
            return

        upper = df.loc[i, "bb_upper"]
        lower = df.loc[i, "bb_lower"]

        # Buy: price was below the lower band and has now closed back above it
        if self.was_below_lower and price >= lower and not self.bought:
            quantity = self.quantity_for(price, df, i)
            if quantity > 0:
                if self.buy(symbol, price, quantity, timestamp):
                    self.bought = True

        # Sell: price was above the upper band and has now closed back below it
        if self.was_above_upper and price <= upper and self.bought:
            pos = self.broker.positions.get(symbol, {"qty": 0})
            if pos["qty"] > 0:
                if self.sell(symbol, price, pos["qty"], timestamp):
                    self.bought = False

        self.was_below_lower = price < lower
        self.was_above_upper = price > upper

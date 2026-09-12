import math
import pandas as pd
from app.engine.strategy import Strategy


class RSIStrategy(Strategy):
    """
    RSI (Relative Strength Index) mean-reversion strategy.

    Buy signal:  RSI crosses back above the oversold threshold (default 30)
    Sell signal: RSI crosses back below the overbought threshold (default 70)
    """

    def __init__(self, broker, period=14, oversold=30, overbought=70):
        super().__init__(broker)
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.bought = False

    def on_bar(self, df, current_index):
        i = current_index
        row = df.iloc[i]
        symbol = row.get("scripName", row.get("Security Id", "UNKNOWN"))
        price = row["Value"]
        timestamp = row["priceDate"]

        if i == 0:
            df["change"] = pd.Series(dtype="float64")
            df["rsi"] = pd.Series(dtype="float64")
            df.loc[i, "change"] = 0.0
            df.loc[i, "rsi"] = 50.0
            return

        df.loc[i, "change"] = price - df.loc[i - 1, "Value"]

        if i < self.period:
            df.loc[i, "rsi"] = 50.0
            return

        window = df["change"].iloc[i - self.period + 1: i + 1]
        gains = window.clip(lower=0).mean()
        losses = -window.clip(upper=0).mean()

        if losses == 0:
            rsi = 100.0
        else:
            rs = gains / losses
            rsi = 100 - (100 / (1 + rs))

        df.loc[i, "rsi"] = rsi

        if i <= self.period:
            return

        rsi_curr = df.loc[i, "rsi"]
        rsi_prev = df.loc[i - 1, "rsi"]

        # Buy: RSI crosses back up through the oversold threshold
        if rsi_prev < self.oversold <= rsi_curr and not self.bought:
            quantity = math.floor(self.broker.capital / price)
            if quantity > 0:
                if self.buy(symbol, price, quantity, timestamp):
                    self.bought = True

        # Sell: RSI crosses back down through the overbought threshold
        if rsi_prev > self.overbought >= rsi_curr and self.bought:
            pos = self.broker.positions.get(symbol, {"qty": 0})
            if pos["qty"] > 0:
                if self.sell(symbol, price, pos["qty"], timestamp):
                    self.bought = False

import pandas as pd
from app.engine.strategy import Strategy


class RSIScalpStrategy(Strategy):
    """
    RSI Scalping Strategy (Mean Reversion).
    
    Buy signal: RSI drops below 20 (extreme oversold).
    Sell signal: RSI crosses back above 50 (mean reversion complete).
    """

    def __init__(self, broker, period=14, oversold=20, take_profit=50, position_sizer=None):
        super().__init__(broker, position_sizer=position_sizer)
        self.period = period
        self.oversold = oversold
        self.take_profit = take_profit
        self.bought = False

    def on_bar(self, df, current_index):
        i = current_index
        row = df.iloc[i]
        symbol = row.get("scripName", row.get("Security Id", "UNKNOWN"))
        price = row["Value"]
        timestamp = str(row["priceDate"])

        # Ensure indicator columns exist regardless of index position.
        if "change" not in df.columns:
            df["change"] = pd.Series(dtype="float64")
        if "rsi" not in df.columns:
            df["rsi"] = pd.Series(dtype="float64")

        if i == 0:
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

        # Buy: RSI drops below oversold
        if rsi_curr < self.oversold and rsi_prev >= self.oversold and not self.bought:
            quantity = self.quantity_for(price, df, i)
            if quantity > 0:
                if self.buy(symbol, price, quantity, timestamp):
                    self.bought = True

        # Sell: RSI crosses back above take profit level (50)
        if rsi_curr > self.take_profit and rsi_prev <= self.take_profit and self.bought:
            pos = self.broker.positions.get(symbol, {"qty": 0})
            if pos["qty"] > 0:
                if self.sell(symbol, price, pos["qty"], timestamp):
                    self.bought = False

import pandas as pd
from app.engine.strategy import Strategy


class EMAScalpStrategy(Strategy):
    """
    EMA Scalping Strategy (Momentum).
    
    Buy signal: Fast EMA (9) crosses above Slow EMA (21).
    Sell signal: Price closes below the Fast EMA (9).
    """

    def __init__(self, broker, fast_days=9, slow_days=21, position_sizer=None):
        super().__init__(broker, position_sizer=position_sizer)
        self.fast_days = fast_days
        self.slow_days = slow_days
        self.bought = False

    def on_bar(self, df, current_index):
        i = current_index
        row = df.iloc[i]

        symbol = row.get("scripName", row.get("Security Id", "UNKNOWN"))
        price = row["Value"]
        timestamp = str(row["priceDate"])

        # Initialize indicator columns on first bar
        if i == 0:
            df["ema_fast"] = pd.Series(dtype="float64")
            df["ema_slow"] = pd.Series(dtype="float64")
            df.loc[i, "ema_fast"] = price
            df.loc[i, "ema_slow"] = price
            return

        # Calculate EMAs
        if i > self.fast_days:
            k_fast = 2 / (self.fast_days + 1)
            df.loc[i, "ema_fast"] = price * k_fast + df.loc[i - 1, "ema_fast"] * (1 - k_fast)
        else:
            df.loc[i, "ema_fast"] = df["Value"][: i + 1].mean()

        if i > self.slow_days:
            k_slow = 2 / (self.slow_days + 1)
            df.loc[i, "ema_slow"] = price * k_slow + df.loc[i - 1, "ema_slow"] * (1 - k_slow)
        else:
            df.loc[i, "ema_slow"] = df["Value"][: i + 1].mean()

        # Wait for enough data before generating signals
        if i <= self.slow_days:
            return

        ema_fast_curr = df.loc[i, "ema_fast"]
        ema_fast_prev = df.loc[i - 1, "ema_fast"]
        ema_slow_curr = df.loc[i, "ema_slow"]
        ema_slow_prev = df.loc[i - 1, "ema_slow"]

        # Buy: Fast EMA crosses above Slow EMA
        if ema_fast_curr > ema_slow_curr and ema_fast_prev <= ema_slow_prev and not self.bought:
            quantity = self.quantity_for(price, df, i)
            if quantity > 0:
                if self.buy(symbol, price, quantity, timestamp):
                    self.bought = True

        # Sell: Price closes below Fast EMA
        if price < ema_fast_curr and self.bought:
            pos = self.broker.positions.get(symbol, {"qty": 0})
            if pos["qty"] > 0:
                if self.sell(symbol, price, pos["qty"], timestamp):
                    self.bought = False

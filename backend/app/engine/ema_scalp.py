import math

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

        # Ensure indicator columns exist (live engine may rebuild df from stored
        # bars that pre-date any on_bar call, so the columns can be absent even
        # at i > 0).
        if "ema_fast" not in df.columns:
            df["ema_fast"] = pd.Series(dtype="float64")
        if "ema_slow" not in df.columns:
            df["ema_slow"] = pd.Series(dtype="float64")

        # Initialize indicator columns on first bar OR when previous value is
        # missing (e.g. session resumed mid-history after a restart).
        prev_ema_fast = df.loc[i - 1, "ema_fast"] if i > 0 else None
        prev_ema_slow = df.loc[i - 1, "ema_slow"] if i > 0 else None

        prev_fast_valid = prev_ema_fast is not None and not pd.isna(prev_ema_fast)
        prev_slow_valid = prev_ema_slow is not None and not pd.isna(prev_ema_slow)

        if i == 0 or not prev_fast_valid:
            df.loc[i, "ema_fast"] = price
        elif i > self.fast_days and prev_fast_valid:
            k_fast = 2 / (self.fast_days + 1)
            df.loc[i, "ema_fast"] = price * k_fast + prev_ema_fast * (1 - k_fast)
        else:
            df.loc[i, "ema_fast"] = df["Value"][: i + 1].mean()

        if i == 0 or not prev_slow_valid:
            df.loc[i, "ema_slow"] = price
        elif i > self.slow_days and prev_slow_valid:
            k_slow = 2 / (self.slow_days + 1)
            df.loc[i, "ema_slow"] = price * k_slow + prev_ema_slow * (1 - k_slow)
        else:
            df.loc[i, "ema_slow"] = df["Value"][: i + 1].mean()

        if i == 0:
            return

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

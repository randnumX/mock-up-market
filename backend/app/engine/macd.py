import pandas as pd
import warnings
from app.engine.strategy import Strategy

warnings.filterwarnings("ignore")


class MACDStrategy(Strategy):
    """
    MACD (Moving Average Convergence Divergence) trading strategy.

    Buy signal:  MACD crosses above Signal line while MACD < 0 (bullish reversal)
    Sell signal: MACD crosses below Signal line while MACD > 0 (bearish reversal)
    """

    def __init__(self, broker, shorter_days=12, longer_days=26, signal_days=9, position_sizer=None):
        super().__init__(broker, position_sizer=position_sizer)
        self.shorter_days = shorter_days
        self.longer_days = longer_days
        self.signal_days = signal_days
        self.bought = False

    def on_bar(self, df, current_index):
        i = current_index
        row = df.iloc[i]

        symbol = row.get("scripName", row.get("Security Id", "UNKNOWN"))
        price = row["Value"]
        timestamp = row["priceDate"]

        # Ensure indicator columns exist regardless of index position.
        # The live engine rebuilds df from stored bars every tick, so columns
        # written by a previous on_bar call may be absent if bars pre-date any run.
        for col in ("shorter_data_ema", "longer_data_ema", "macd_value", "signal"):
            if col not in df.columns:
                df[col] = pd.Series(dtype="float64")

        # Helper: is the previous row's value usable for a recursive formula?
        def _prev(col, default):
            if i == 0:
                return default
            v = df.loc[i - 1, col]
            return default if pd.isna(v) else v

        # Calculate EMAs (fall back to seeding from price when prev is missing)
        prev_short = _prev("shorter_data_ema", price)
        prev_long  = _prev("longer_data_ema",  price)
        prev_sig   = _prev("signal", 0)

        if i > self.shorter_days and not pd.isna(df.loc[i - 1, "shorter_data_ema"] if i > 0 else float("nan")):
            k_short = 2 / (self.shorter_days + 1)
            df.loc[i, "shorter_data_ema"] = price * k_short + prev_short * (1 - k_short)
        else:
            df.loc[i, "shorter_data_ema"] = df["Value"][: i + 1].mean()

        if i > self.longer_days and not pd.isna(df.loc[i - 1, "longer_data_ema"] if i > 0 else float("nan")):
            k_long = 2 / (self.longer_days + 1)
            df.loc[i, "longer_data_ema"] = price * k_long + prev_long * (1 - k_long)
            df.loc[i, "macd_value"] = df.loc[i, "shorter_data_ema"] - df.loc[i, "longer_data_ema"]
            k_sig = 2 / (self.signal_days + 1)
            df.loc[i, "signal"] = df.loc[i, "macd_value"] * k_sig + prev_sig * (1 - k_sig)
        else:
            df.loc[i, "longer_data_ema"] = df["Value"][: i + 1].mean()
            df.loc[i, "macd_value"] = 0
            df.loc[i, "signal"] = df["macd_value"][: i + 1].mean() if i > 0 else 0

        if i == 0:
            return

        # Wait for enough data before generating signals
        if i <= 30:
            return

        macd_curr = df.loc[i, "macd_value"]
        macd_prev = df.loc[i - 1, "macd_value"]
        sig_curr = df.loc[i, "signal"]
        sig_prev = df.loc[i - 1, "signal"]

        # Buy: MACD crosses above signal, MACD < 0 (bullish reversal from below)
        if macd_curr > sig_curr and macd_prev < sig_prev and macd_curr < 0 and not self.bought:
            quantity = self.quantity_for(price, df, i)
            if quantity > 0:
                if self.buy(symbol, price, quantity, timestamp):
                    self.bought = True

        # Sell: MACD crosses below signal, MACD > 0 (bearish reversal from above)
        if macd_curr < sig_curr and macd_prev > sig_prev and macd_curr > 0 and self.bought:
            pos = self.broker.positions.get(symbol, {"qty": 0})
            if pos["qty"] > 0:
                if self.sell(symbol, price, pos["qty"], timestamp):
                    self.bought = False

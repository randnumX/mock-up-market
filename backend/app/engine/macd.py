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

        # Initialize indicator columns on first bar
        if i == 0:
            df["shorter_data_ema"] = pd.Series(dtype="float64")
            df["longer_data_ema"] = pd.Series(dtype="float64")
            df["macd_value"] = pd.Series(dtype="float64")
            df["signal"] = pd.Series(dtype="float64")

            df.loc[i, "shorter_data_ema"] = price
            df.loc[i, "longer_data_ema"] = price
            df.loc[i, "macd_value"] = 0
            df.loc[i, "signal"] = 0
            return

        # Calculate EMAs
        if i > self.shorter_days:
            k_short = 2 / (self.shorter_days + 1)
            df.loc[i, "shorter_data_ema"] = price * k_short + df.loc[i - 1, "shorter_data_ema"] * (1 - k_short)
        else:
            df.loc[i, "shorter_data_ema"] = df["Value"][: i + 1].mean()

        if i > self.longer_days:
            k_long = 2 / (self.longer_days + 1)
            df.loc[i, "longer_data_ema"] = price * k_long + df.loc[i - 1, "longer_data_ema"] * (1 - k_long)
            df.loc[i, "macd_value"] = df.loc[i, "shorter_data_ema"] - df.loc[i, "longer_data_ema"]
            k_sig = 2 / (self.signal_days + 1)
            df.loc[i, "signal"] = df.loc[i, "macd_value"] * k_sig + df.loc[i - 1, "signal"] * (1 - k_sig)
        else:
            df.loc[i, "longer_data_ema"] = df["Value"][: i + 1].mean()
            df.loc[i, "macd_value"] = 0
            df.loc[i, "signal"] = df["macd_value"][: i + 1].mean() if i > 0 else 0

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

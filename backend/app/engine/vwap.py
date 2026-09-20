import pandas as pd
import warnings
from app.engine.strategy import Strategy

warnings.filterwarnings("ignore")


class VWAPStrategy(Strategy):
    """
    Volume Weighted Average Price (VWAP) intraday strategy.
    
    VWAP resets every day. 
    Buy signal: Price crosses above VWAP line (bullish intraday momentum).
    Sell signal: Price crosses below VWAP line, or end of day (15:15) is reached.
    """

    def __init__(self, broker, position_sizer=None):
        super().__init__(broker, position_sizer=position_sizer)
        self.bought = False
        self.current_date = None
        self.cum_vol = 0
        self.cum_pv = 0

    def on_bar(self, df, current_index):
        i = current_index
        row = df.iloc[i]

        symbol = row.get("scripName", row.get("Security Id", "UNKNOWN"))
        price = row["Value"]
        volume = row.get("Volume", 0)
        timestamp = str(row["priceDate"])

        date_str = timestamp[:10]
        time_str = timestamp[11:16] if len(timestamp) > 10 else "00:00"

        # Initialize indicator columns on first bar
        if i == 0:
            df["vwap"] = pd.Series(dtype="float64")

        # Reset VWAP at the start of a new day
        if date_str != self.current_date:
            self.current_date = date_str
            self.cum_vol = 0
            self.cum_pv = 0

        # Calculate Typical Price (H+L+C)/3 if High/Low are available, else just use Close
        high = row.get("High", price)
        low = row.get("Low", price)
        typical_price = (high + low + price) / 3.0

        self.cum_vol += volume
        self.cum_pv += (typical_price * volume)

        vwap_val = self.cum_pv / self.cum_vol if self.cum_vol > 0 else price
        df.loc[i, "vwap"] = vwap_val

        # Wait for at least 1 previous bar
        if i < 1:
            return

        vwap_curr = df.loc[i, "vwap"]
        vwap_prev = df.loc[i - 1, "vwap"]
        price_prev = df.loc[i - 1, "Value"]

        # Close positions at end of day (Intraday squaring off)
        if self.bought and time_str >= "15:15":
            pos = self.broker.positions.get(symbol, {"qty": 0})
            if pos["qty"] > 0:
                if self.sell(symbol, price, pos["qty"], timestamp):
                    self.bought = False
            return

        # Buy: Price crosses above VWAP
        if price > vwap_curr and price_prev <= vwap_prev and not self.bought:
            quantity = self.quantity_for(price, df, i)
            if quantity > 0:
                if self.buy(symbol, price, quantity, timestamp):
                    self.bought = True

        # Sell: Price crosses below VWAP
        if price < vwap_curr and price_prev >= vwap_prev and self.bought:
            pos = self.broker.positions.get(symbol, {"qty": 0})
            if pos["qty"] > 0:
                if self.sell(symbol, price, pos["qty"], timestamp):
                    self.bought = False

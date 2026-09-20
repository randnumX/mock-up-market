import pandas as pd
import warnings
from app.engine.strategy import Strategy

warnings.filterwarnings("ignore")


class ORBStrategy(Strategy):
    """
    Opening Range Breakout (ORB) Strategy.
    
    Monitors the High and Low of the first 15 minutes of the trading day.
    Buy signal: Price breaks above the 15-minute High.
    Sell (Short) signal: Price breaks below the 15-minute Low.
    Positions are squared off at 15:15.
    """

    def __init__(self, broker, position_sizer=None):
        super().__init__(broker, position_sizer=position_sizer)
        self.current_date = None
        self.orb_high = -1
        self.orb_low = float('inf')
        self.orb_established = False

    def on_bar(self, df, current_index):
        i = current_index
        row = df.iloc[i]

        symbol = row.get("scripName", row.get("Security Id", "UNKNOWN"))
        price = row["Value"]
        timestamp = str(row["priceDate"])

        date_str = timestamp[:10]
        time_str = timestamp[11:16] if len(timestamp) > 10 else "00:00"

        # Initialize columns
        if i == 0:
            df["orb_high"] = pd.Series(dtype="float64")
            df["orb_low"] = pd.Series(dtype="float64")

        # Reset at the start of a new day
        if date_str != self.current_date:
            self.current_date = date_str
            self.orb_high = -1
            self.orb_low = float('inf')
            self.orb_established = False

        high = row.get("High", price)
        low = row.get("Low", price)

        # Build the opening range (before 09:30)
        # Assuming NSE market opens at 09:15, so 09:15 to 09:29 is the first 15 mins.
        if time_str < "09:30":
            self.orb_high = max(self.orb_high, high)
            self.orb_low = min(self.orb_low, low)
            df.loc[i, "orb_high"] = None
            df.loc[i, "orb_low"] = None
            return
        else:
            self.orb_established = True

        df.loc[i, "orb_high"] = self.orb_high if self.orb_high != -1 else None
        df.loc[i, "orb_low"] = self.orb_low if self.orb_low != float('inf') else None

        if not self.orb_established:
            return

        pos = self.broker.positions.get(symbol, {"qty": 0})
        qty = pos["qty"]

        # Close positions at end of day
        if qty != 0 and time_str >= "15:15":
            if qty > 0:
                self.sell(symbol, price, qty, timestamp)
            elif qty < 0:
                self.buy(symbol, price, abs(qty), timestamp)
            return
            
        # Stop trading for the day if we already hold a position
        # (Usually ORB is a one-shot per day)
        if qty != 0:
            return

        # Buy: Breakout above ORB High
        if price > self.orb_high:
            quantity = self.quantity_for(price, df, i)
            if quantity > 0:
                self.buy(symbol, price, quantity, timestamp)

        # Short: Breakdown below ORB Low
        elif price < self.orb_low:
            quantity = self.quantity_for(price, df, i)
            if quantity > 0:
                self.sell(symbol, price, quantity, timestamp)

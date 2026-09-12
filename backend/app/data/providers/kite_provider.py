from datetime import datetime, timedelta
import pandas as pd
from app.data.providers.base import DataProvider
from app.data.kite_ingest import DEFAULT_TICKERS, get_instrument_token


class KiteProvider(DataProvider):
    """
    Live data straight from Zerodha Kite Connect - no MongoDB required.
    Only active once the user has connected via the "Connect Zerodha" flow.
    Independent of MongoProvider: /api/kite/sync additionally *persists*
    Kite data into Mongo for offline/history reuse, but this provider can
    serve backtests directly from the API too.
    """
    name = "kite"

    def __init__(self, kite):
        self.kite = kite

    def is_available(self):
        return self.kite is not None

    def get_tickers(self):
        return sorted(DEFAULT_TICKERS)

    def get_history(self, ticker, days=365):
        if not self.is_available():
            return None
        try:
            token = get_instrument_token(self.kite, ticker)
            if not token:
                return None
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)
            candles = self.kite.historical_data(token, from_date, to_date, interval="day")
        except Exception:
            return None

        if not candles:
            return None

        return pd.DataFrame({
            "scripName": ticker,
            "priceDate": [c["date"].strftime("%Y-%m-%d") if hasattr(c["date"], "strftime") else str(c["date"]) for c in candles],
            "Value": [float(c["close"]) for c in candles],
            "Volume": [int(c["volume"]) for c in candles],
        })

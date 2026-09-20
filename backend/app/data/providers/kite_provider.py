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

    def get_history(self, ticker, days=365, from_date=None, to_date=None, interval="day"):
        if not self.is_available():
            return None
        try:
            token = get_instrument_token(self.kite, ticker)
            if not token:
                return None
            # Kite caps how far back intraday intervals can be queried in
            # one call (e.g. 5minute is max ~100 days, minute ~60) - mirrors
            # the same cap kite_ingest.fetch_and_store applies.
            if interval in ["minute", "3minute", "5minute", "10minute", "15minute", "30minute", "60minute"]:
                days = min(days, 100 if interval != "minute" else 60)
            range_end = datetime.strptime(to_date, "%Y-%m-%d") if to_date else datetime.now()
            range_start = datetime.strptime(from_date, "%Y-%m-%d") if from_date else range_end - timedelta(days=days)
            candles = self.kite.historical_data(token, range_start, range_end, interval=interval)
        except Exception:
            return None

        if not candles:
            return None

        return pd.DataFrame({
            "scripName": ticker,
            "priceDate": [c["date"].strftime("%Y-%m-%d %H:%M:%S") if hasattr(c["date"], "strftime") else str(c["date"]) for c in candles],
            "Value": [float(c["close"]) for c in candles],
            "Open": [float(c["open"]) for c in candles],
            "High": [float(c["high"]) for c in candles],
            "Low": [float(c["low"]) for c in candles],
            "Volume": [int(c["volume"]) for c in candles],
            "interval": interval,
        })

    def get_latest_price(self, ticker, last_known_price=None):
        if not self.is_available():
            return None
        
        # 1. Try to get 0-latency price from WebSocket cache first
        from app.live.ticker import get_latest_price as get_ws_price
        cached_price = get_ws_price(ticker)
        if cached_price is not None:
            return float(cached_price)

        # 2. Fall back to REST API
        try:
            quote = self.kite.ltp([f"NSE:{ticker}"])
            return float(quote[f"NSE:{ticker}"]["last_price"])
        except Exception:
            return None

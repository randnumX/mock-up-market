import pandas as pd
from app.config import Config
from app.data.providers.base import DataProvider


class MongoProvider(DataProvider):
    """Reads previously-ingested data (via Kite sync or any other loader) from MongoDB."""
    name = "mongodb"

    def __init__(self, db):
        self.db = db

    def is_available(self):
        return self.db is not None

    def get_tickers(self):
        if not self.is_available():
            return []
        try:
            return sorted(self.db[Config.COLLECTION_HISTORICAL].distinct("scripName"))
        except Exception:
            return []

    def get_history(self, ticker, days=365):
        if not self.is_available():
            return None
        try:
            records = list(self.db[Config.COLLECTION_HISTORICAL].find({"scripName": ticker}))
        except Exception:
            return None
        if not records:
            return None
        return pd.DataFrame(records)

    def get_latest_price(self, ticker, last_known_price=None):
        """Mongo only holds daily candles, not a live feed - last stored close is the
        best it can offer. Sessions using this provider should expect coarse ticks."""
        if not self.is_available():
            return None
        try:
            doc = self.db[Config.COLLECTION_HISTORICAL].find_one(
                {"scripName": ticker}, sort=[("priceDate", -1)]
            )
        except Exception:
            return None
        return float(doc["Value"]) if doc else None

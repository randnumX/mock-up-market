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

    def get_history(self, ticker, days=365, from_date=None, to_date=None):
        if not self.is_available():
            return None

        query = {"scripName": ticker}
        if from_date or to_date:
            # priceDate is stored as an ISO "YYYY-MM-DD" string everywhere it's
            # written (kite_ingest, fetch_bse_data), so lexicographic range
            # comparison is exact - no date parsing needed.
            date_filter = {}
            if from_date:
                date_filter["$gte"] = from_date
            if to_date:
                date_filter["$lte"] = to_date
            query["priceDate"] = date_filter

        try:
            records = list(self.db[Config.COLLECTION_HISTORICAL].find(query))
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

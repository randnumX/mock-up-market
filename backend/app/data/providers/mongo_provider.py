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

    def get_history(self, ticker, days=365, from_date=None, to_date=None, interval="day"):
        if not self.is_available():
            return None

        query = {"scripName": ticker}
        if interval == "day":
            query["$or"] = [{"interval": "day"}, {"interval": {"$exists": False}}]
        else:
            query["interval"] = interval

        if from_date or to_date:
            # priceDate is stored as an ISO "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS" string 
            date_filter = {}
            if from_date:
                date_filter["$gte"] = from_date
            if to_date:
                date_filter["$lte"] = to_date + " 23:59:59" if len(to_date) == 10 else to_date
            query["priceDate"] = date_filter

        try:
            records = list(self.db[Config.COLLECTION_HISTORICAL].find(query).sort("priceDate", 1))
        except Exception:
            return None
        if not records:
            return None
        return pd.DataFrame(records)

    def get_latest_price(self, ticker, last_known_price=None, interval="day"):
        """Mongo only holds stored candles, not a live feed - last stored close is the
        best it can offer. Sessions using this provider should expect coarse ticks."""
        if not self.is_available():
            return None
        try:
            query = {"scripName": ticker}
            if interval == "day":
                query["$or"] = [{"interval": "day"}, {"interval": {"$exists": False}}]
            else:
                query["interval"] = interval
                
            doc = self.db[Config.COLLECTION_HISTORICAL].find_one(
                query, sort=[("priceDate", -1)]
            )
        except Exception:
            return None
        return float(doc["Value"]) if doc else None

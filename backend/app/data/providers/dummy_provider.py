from datetime import datetime, timedelta
import numpy as np
from app.data.providers.base import DataProvider
from app.utils.dummy_data import generate_stock_data, get_dummy_tickers, STOCK_PROFILES


class DummyProvider(DataProvider):
    """Synthetic GBM data. Always available - the guaranteed last resort so the
    app is fully functional with zero setup (no DB, no broker connection)."""
    name = "generated"

    def is_available(self):
        return True

    def get_tickers(self):
        return get_dummy_tickers()

    def get_history(self, ticker, days=365, from_date=None, to_date=None):
        if not (from_date or to_date):
            return generate_stock_data(ticker, days=days)

        end = datetime.strptime(to_date, "%Y-%m-%d") if to_date else datetime.now()
        start = datetime.strptime(from_date, "%Y-%m-%d") if from_date else end - timedelta(days=days)
        weekdays = sum(1 for d in range((end - start).days + 1) if (start + timedelta(days=d)).weekday() < 5)
        return generate_stock_data(ticker, days=max(weekdays, 1), end_date=end)

    def get_latest_price(self, ticker, last_known_price=None):
        """
        Simulates a live tick with one more GBM step, so "paper trading"
        works with zero setup (no Kite, no Mongo) just like the backtester.
        """
        profile = STOCK_PROFILES.get(ticker, {"base_price": 500, "volatility": 0.02, "drift": 0.0002})
        base = last_known_price if last_known_price else profile["base_price"]
        shock = np.random.normal(0, 1)
        change = base * (profile["drift"] + profile["volatility"] * shock)
        return round(max(base + change, base * 0.92), 2)

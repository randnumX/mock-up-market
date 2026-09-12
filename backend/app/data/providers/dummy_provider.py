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

    def get_history(self, ticker, days=365):
        return generate_stock_data(ticker, days=days)

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

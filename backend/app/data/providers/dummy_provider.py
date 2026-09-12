from app.data.providers.base import DataProvider
from app.utils.dummy_data import generate_stock_data, get_dummy_tickers


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

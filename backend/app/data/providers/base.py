class DataProvider:
    """
    Common interface every market-data source implements, so the routes
    layer never hardcodes "Mongo" or "Kite" — it just asks the active
    provider for tickers/history. Swapping or adding a data source means
    writing one of these and registering it; nothing else changes.
    """
    name = "base"

    def is_available(self):
        """Cheap check: can this provider currently serve data at all?"""
        raise NotImplementedError

    def get_tickers(self):
        """Return a sorted list of ticker symbols this provider can serve."""
        raise NotImplementedError

    def get_history(self, ticker, days=365):
        """
        Return a pandas DataFrame with columns scripName/priceDate/Value/Volume
        for `ticker`, or None/empty if unavailable for that ticker.
        """
        raise NotImplementedError

    def get_latest_price(self, ticker, last_known_price=None):
        """
        Return the current/latest tradeable price for `ticker` as a float,
        or None if unavailable. Used by the live trading engine to advance
        a running session one tick at a time. `last_known_price` lets a
        simulated provider (no real feed) generate a plausible next tick
        instead of replaying static history.
        """
        raise NotImplementedError

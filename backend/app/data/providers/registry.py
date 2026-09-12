"""
Central place that wires up every DataProvider and decides which one
serves a given request. This is the "dependency injection" seam: routes
never import Mongo/Kite/dummy-data code directly, they just call
get_provider_chain() or get_provider(name) and use whatever comes back.

Default precedence (first available wins, when the caller doesn't force
a specific source): Kite (real, live) > MongoDB (real, previously synced)
> generated (synthetic, always available). Any provider can be swapped
out or a new one added here without touching route code.
"""
from app.data.db import get_db
from app.data.kite_client import get_kite
from app.data.providers.kite_provider import KiteProvider
from app.data.providers.mongo_provider import MongoProvider
from app.data.providers.dummy_provider import DummyProvider


def build_providers():
    """Instantiate every known provider, in default precedence order."""
    return [
        KiteProvider(get_kite()),
        MongoProvider(get_db()),
        DummyProvider(),  # always available - guaranteed fallback
    ]


def get_provider(name=None):
    """
    Return a single provider. `name` forces a specific source
    ("kite" | "mongodb" | "generated"); omit it to get the first
    available provider in default precedence order.
    """
    providers = build_providers()

    if name:
        for p in providers:
            if p.name == name:
                return p if p.is_available() else None
        return None

    for p in providers:
        if p.is_available():
            return p
    return None


def get_history_with_fallback(ticker, days=365, preferred=None, from_date=None, to_date=None):
    """
    Try providers in order (preferred first, if given and available),
    falling back down the chain until one returns data for `ticker`.
    `from_date`/`to_date` (ISO "YYYY-MM-DD", inclusive) restrict the range
    explicitly, e.g. a user-selected backtest window in the UI.
    Returns (dataframe, provider_name_used).
    """
    providers = build_providers()
    if preferred:
        providers.sort(key=lambda p: p.name != preferred)

    for p in providers:
        if not p.is_available():
            continue
        df = p.get_history(ticker, days=days, from_date=from_date, to_date=to_date)
        if df is not None and not df.empty:
            return df, p.name

    return None, None

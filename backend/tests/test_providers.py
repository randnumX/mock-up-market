from app.data.providers.dummy_provider import DummyProvider
from app.data.providers.mongo_provider import MongoProvider
from app.data.providers.kite_provider import KiteProvider


def test_dummy_provider_is_always_available():
    provider = DummyProvider()
    assert provider.is_available() is True
    assert "SBIN" in provider.get_tickers()


def test_dummy_provider_returns_history_for_any_ticker():
    provider = DummyProvider()
    df = provider.get_history("SBIN", days=100)
    assert len(df) == 100
    assert list(df.columns) == ["scripName", "priceDate", "Value", "Volume"]


def test_mongo_provider_unavailable_when_db_is_none():
    provider = MongoProvider(None)
    assert provider.is_available() is False
    assert provider.get_tickers() == []
    assert provider.get_history("SBIN") is None


def test_kite_provider_unavailable_when_not_connected():
    provider = KiteProvider(None)
    assert provider.is_available() is False
    assert provider.get_history("SBIN") is None

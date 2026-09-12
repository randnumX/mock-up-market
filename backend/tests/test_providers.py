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


def test_dummy_provider_respects_explicit_date_range():
    provider = DummyProvider()
    df = provider.get_history("SBIN", from_date="2024-01-01", to_date="2024-01-31")
    assert not df.empty
    assert df["priceDate"].min() >= "2024-01-01"
    assert df["priceDate"].max() <= "2024-01-31"


def test_mongo_provider_filters_by_date_range():
    import mongomock
    db = mongomock.MongoClient().db
    db["LastOneYearStockData"].insert_many([
        {"scripName": "SBIN", "priceDate": "2024-01-01", "Value": 100, "Volume": 1},
        {"scripName": "SBIN", "priceDate": "2024-06-15", "Value": 110, "Volume": 1},
        {"scripName": "SBIN", "priceDate": "2024-12-31", "Value": 120, "Volume": 1},
    ])
    provider = MongoProvider(db)

    df = provider.get_history("SBIN", from_date="2024-02-01", to_date="2024-11-01")
    assert list(df["priceDate"]) == ["2024-06-15"]

    df_all = provider.get_history("SBIN")
    assert len(df_all) == 3

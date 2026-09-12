"""
Pulls real historical daily candles from Zerodha Kite Connect and stores
them in MongoDB in the same shape the rest of the app already reads
(scripName / priceDate / Value / Volume in Config.COLLECTION_HISTORICAL),
so switching from synthetic data to real data is transparent to the
backtest engine and the frontend.
"""
from datetime import datetime, timedelta
from app.config import Config

# Default watchlist: the same large-cap NSE names the dummy-data generator
# knows about, so the UI's ticker list stays meaningful either way.
DEFAULT_TICKERS = [
    "SBIN", "RELIANCE", "HDFCBANK", "INFY", "TCS",
    "ICICIBANK", "TATAMOTORS", "WIPRO", "BAJFINANCE", "MARUTI",
]

_instrument_cache = None


def get_instrument_token(kite, tradingsymbol, exchange="NSE"):
    """Resolve an NSE trading symbol (e.g. 'SBIN') to its Kite instrument_token."""
    global _instrument_cache
    if _instrument_cache is None:
        _instrument_cache = kite.instruments(exchange)

    for inst in _instrument_cache:
        if inst["tradingsymbol"] == tradingsymbol and inst["instrument_type"] == "EQ":
            return inst["instrument_token"]
    return None


def fetch_and_store(kite, db, tickers=None, days=730, progress=None):
    """
    Fetch `days` of daily OHLCV history for each ticker from Kite and
    upsert it into Mongo, replacing any previously stored rows for that
    ticker so re-syncing doesn't create duplicates.

    Returns a summary dict: {synced: [...], failed: [{ticker, reason}], total_candles}
    """
    tickers = tickers or DEFAULT_TICKERS
    collection = db[Config.COLLECTION_HISTORICAL]

    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)

    synced, failed, total_candles = [], [], 0

    for ticker in tickers:
        try:
            token = get_instrument_token(kite, ticker)
            if not token:
                failed.append({"ticker": ticker, "reason": "instrument not found on NSE"})
                continue

            candles = kite.historical_data(token, from_date, to_date, interval="day")
            if not candles:
                failed.append({"ticker": ticker, "reason": "no historical data returned"})
                continue

            docs = [
                {
                    "scripName": ticker,
                    "priceDate": c["date"].strftime("%Y-%m-%d") if hasattr(c["date"], "strftime") else str(c["date"]),
                    "Value": float(c["close"]),
                    "Volume": int(c["volume"]),
                }
                for c in candles
            ]

            collection.delete_many({"scripName": ticker})
            collection.insert_many(docs)

            synced.append(ticker)
            total_candles += len(docs)
        except Exception as e:
            failed.append({"ticker": ticker, "reason": str(e)})

        if progress:
            progress(ticker)

    return {"synced": synced, "failed": failed, "total_candles": total_candles}

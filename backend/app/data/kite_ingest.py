"""
Pulls real historical daily candles from Zerodha Kite Connect and stores
them in MongoDB in the same shape the rest of the app already reads
(scripName / priceDate / Value / Volume in Config.COLLECTION_HISTORICAL),
so switching from synthetic data to real data is transparent to the
backtest engine and the frontend.
"""
from datetime import datetime, timedelta
from app.config import Config
from app.utils.intervals import kite_max_days, INTRADAY_IDS

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


def fetch_and_store(kite, db, tickers=None, days=730, interval="day", progress=None):
    """
    Fetch `days` of historical OHLCV history for each ticker from Kite and
    upsert it into Mongo, replacing any previously stored rows for that
    ticker and interval so re-syncing doesn't create duplicates.

    Returns a summary dict: {synced: [...], failed: [{ticker, reason}], total_candles}
    """
    tickers = tickers or DEFAULT_TICKERS
    collection = db[Config.COLLECTION_HISTORICAL]

    to_date = datetime.now()
    # Kite API limits intraday history (e.g. 5minute is max 100 days).
    if interval in INTRADAY_IDS:
        days = min(days, kite_max_days(interval))
        
    from_date = to_date - timedelta(days=days)

    synced, failed, total_candles = [], [], 0

    total_requested = len(tickers)
    for idx, ticker in enumerate(tickers):
        try:
            token = get_instrument_token(kite, ticker)
            if not token:
                failed.append({"ticker": ticker, "reason": "instrument not found on NSE"})
                if progress:
                    progress(ticker, idx + 1, total_requested)
                continue

            # Smart Sync: Check DB for the most recent date we already have for this interval
            latest_doc = collection.find_one(
                {"scripName": ticker, "interval": interval}, 
                sort=[("priceDate", -1)]
            )
            
            if latest_doc and "priceDate" in latest_doc:
                last_date_str = latest_doc["priceDate"]
                # Fetch starting from the last date we have, so we can update any partial candles
                fetch_from = datetime.strptime(last_date_str[:10], "%Y-%m-%d")
            else:
                fetch_from = from_date

            candles = kite.historical_data(token, fetch_from, to_date, interval=interval)
            if not candles:
                failed.append({"ticker": ticker, "reason": "no historical data returned"})
                if progress:
                    progress(ticker, idx + 1, total_requested)
                continue

            docs = [
                {
                    "scripName": ticker,
                    "interval": interval,
                    "priceDate": c["date"].strftime("%Y-%m-%d %H:%M:%S") if hasattr(c["date"], "strftime") else str(c["date"])[:19],
                    "Value": float(c["close"]),
                    "Volume": int(c["volume"]),
                    # Store real OHLC since we have it, strategies like VWAP/ORB need High/Low
                    "Open": float(c["open"]),
                    "High": float(c["high"]),
                    "Low": float(c["low"]),
                }
                for c in candles
            ]

            # Delete any overlapping dates to prevent duplicates, then insert the fresh ones
            fetch_from_str = fetch_from.strftime("%Y-%m-%d")
            collection.delete_many({
                "scripName": ticker, 
                "interval": interval,
                "priceDate": {"$gte": fetch_from_str}
            })
            
            if docs:
                collection.insert_many(docs)

            synced.append(ticker)
            total_candles += len(docs)
        except Exception as e:
            failed.append({"ticker": ticker, "reason": str(e)})

        if progress:
            progress(ticker, idx + 1, total_requested)

    return {"synced": synced, "failed": failed, "total_candles": total_candles}

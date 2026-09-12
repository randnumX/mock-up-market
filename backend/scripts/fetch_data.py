#!/usr/bin/env python3
"""
Pulls real historical data from Zerodha Kite Connect into MongoDB, for
headless/cron use. Equivalent to the in-app "Sync Real Data" button.
Requires an active Kite session - run kite_login.py first if needed.

Usage:
    cd backend && python scripts/fetch_data.py [TICKER ...] [--days 730]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app.data import kite_client  # noqa: E402
from app.data.db import get_db  # noqa: E402
from app.data.kite_ingest import fetch_and_store, DEFAULT_TICKERS  # noqa: E402


def main():
    args = sys.argv[1:]
    days = 730
    if "--days" in args:
        idx = args.index("--days")
        days = int(args[idx + 1])
        del args[idx:idx + 2]

    tickers = args or DEFAULT_TICKERS

    kite = kite_client.get_kite()
    if kite is None:
        print("Not connected to Zerodha. Run scripts/kite_login.py first.")
        sys.exit(1)

    db = get_db()
    if db is None:
        print("MongoDB is not reachable. Check MONGO_URI in backend/.env.")
        sys.exit(1)

    print(f"Fetching {days} days of history for: {', '.join(tickers)}")
    result = fetch_and_store(kite, db, tickers=tickers, days=days, progress=lambda t: print(f"  ✓ {t}"))

    print(f"\nSynced {len(result['synced'])} tickers, {result['total_candles']} candles total.")
    if result["failed"]:
        print("Failed:")
        for f in result["failed"]:
            print(f"  ✗ {f['ticker']}: {f['reason']}")


if __name__ == "__main__":
    main()

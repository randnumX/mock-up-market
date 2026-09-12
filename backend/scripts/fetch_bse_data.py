#!/usr/bin/env python3
"""
Loads real historical price data from BSE's public (undocumented)
StockReachGraph API directly into MongoDB - no broker account or API
key needed, unlike the Kite Connect path in fetch_data.py.

This is a revival of the old AlgoTrading/onetime_twentyfourmonth_load.py
script, wired to the current backend instead of the removed AlgoTrading/
package, generalized from one hardcoded ticker to BSE's full active
equity list (backend/Equity.csv, the official T+1 list from
bseindia.com/corporates/List_Scrips.aspx), and cleaned up to write only
the columns the engine actually reads (scripName/priceDate/Value/Volume)
instead of raw+debug fields.

Caveat: this hits an undocumented BSE endpoint via plain HTTP with a
spoofed browser User-Agent - it works today, but BSE could change or
block it at any time without notice. For anything long-term/production,
prefer the Kite Connect path (fetch_data.py) instead.

Important: `flag=12M` is the ceiling for genuine DAILY history on this
endpoint (~249 trading days). Anything above 12M (15M/18M/24M/2Y/5Y/...)
silently switches the response to INTRADAY MINUTE TICKS for today only,
still wrapped in a valid-looking timestamp - inserting those as if they
were historical daily bars would quietly corrupt the data. Confirmed by
direct testing; ALLOWED_FLAGS below is the enforced safe set. For more
than ~1 year of real history, use fetch_data.py (Kite Connect) instead.

Usage:
    cd backend && python scripts/fetch_bse_data.py                  # all ~5000 active equities, resumable
    cd backend && python scripts/fetch_bse_data.py SBIN RELIANCE    # just these tickers
    cd backend && python scripts/fetch_bse_data.py --limit 50       # first 50 only (for testing)
    cd backend && python scripts/fetch_bse_data.py --force          # re-fetch even already-loaded tickers
    cd backend && python scripts/fetch_bse_data.py --delay 0.5      # seconds between requests (default 0.3)
"""
import os
import sys
import csv
import json
import time
import datetime
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app.config import Config  # noqa: E402
from app.data.db import get_db  # noqa: E402

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Origin': 'https://www.bseindia.com',
    'Referer': 'https://www.bseindia.com/',
}

EQUITY_CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Equity.csv')

# Anything above 12M returns intraday ticks for today instead of more
# history (see module docstring) - deliberately not exposing those flags.
ALLOWED_FLAGS = {"1M", "3M", "6M", "12M"}


def load_scrip_codes(csv_path=EQUITY_CSV_PATH):
    """
    Ticker (BSE 'Security Id') -> scrip code ('Security Code'), from the
    official active-equity list. Source: bseindia.com/corporates/List_Scrips.aspx
    (T+1 segment, Active status), exported to backend/Equity.csv.
    """
    codes = {}
    with open(csv_path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if row.get('Instrument', '').strip() != 'Equity':
                continue
            ticker = row.get('Security Id', '').strip()
            code = row.get('Security Code', '').strip()
            if ticker and code:
                codes[ticker] = code
    return codes


def fetch_ticker(ticker, scrip_code, flag="12M"):
    """Fetch and clean one ticker's history. Returns a list of docs or raises."""
    url = (
        f"https://api.bseindia.com/BseIndiaAPI/api/StockReachGraph/w"
        f"?scripcode={scrip_code}&flag={flag}&fromdate=&todate=&seriesid="
    )
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    payload = json.loads(response.content.decode())
    raw_points = json.loads(payload["Data"])

    docs = []
    for point in raw_points:
        try:
            price_date = datetime.datetime.strptime(point["dttm"], "%a %b %d %Y %H:%M:%S")
        except (KeyError, ValueError):
            continue  # skip malformed points rather than inserting garbage
        try:
            value = float(point["vale1"])
            volume = float(point.get("vole", 0))
        except (KeyError, ValueError):
            continue

        docs.append({
            "scripName": ticker,
            "priceDate": price_date.strftime("%Y-%m-%d"),
            "Value": value,
            "Volume": volume,
        })
    return docs


def fetch_and_store(db, tickers, flag="12M", delay=0.3, progress=None):
    scrip_codes = load_scrip_codes()
    collection = db[Config.COLLECTION_HISTORICAL]
    synced, failed, total_candles = [], [], 0

    for i, ticker in enumerate(tickers):
        scrip_code = scrip_codes.get(ticker)
        if not scrip_code:
            failed.append({"ticker": ticker, "reason": "not found in Equity.csv"})
            continue
        try:
            docs = fetch_ticker(ticker, scrip_code, flag=flag)
            if not docs:
                failed.append({"ticker": ticker, "reason": "no usable data points returned"})
            else:
                collection.delete_many({"scripName": ticker})
                collection.insert_many(docs)
                synced.append(ticker)
                total_candles += len(docs)
        except Exception as e:
            failed.append({"ticker": ticker, "reason": str(e)})

        if progress:
            progress(i + 1, len(tickers), ticker)
        if delay and i < len(tickers) - 1:
            time.sleep(delay)

    return {"synced": synced, "failed": failed, "total_candles": total_candles}


def _parse_args(argv):
    flag, delay, limit, force = "12M", 0.3, None, False
    tickers = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--flag":
            flag = argv[i + 1]
            if flag not in ALLOWED_FLAGS:
                raise SystemExit(
                    f"--flag {flag} is not allowed: BSE returns intraday ticks (not more history) above 12M. "
                    f"Choose one of {sorted(ALLOWED_FLAGS)}, or use fetch_data.py (Kite) for longer history."
                )
            i += 2
        elif arg == "--delay":
            delay = float(argv[i + 1])
            i += 2
        elif arg == "--limit":
            limit = int(argv[i + 1])
            i += 2
        elif arg == "--force":
            force = True
            i += 1
        else:
            tickers.append(arg)
            i += 1
    return flag, delay, limit, force, tickers


def main():
    flag, delay, limit, force, explicit_tickers = _parse_args(sys.argv[1:])

    db = get_db()
    if db is None:
        print("MongoDB is not reachable. Check MONGO_URI in backend/.env (or `docker compose up -d`).")
        sys.exit(1)

    scrip_codes = load_scrip_codes()
    tickers = explicit_tickers or sorted(scrip_codes.keys())

    if not force:
        already_loaded = set(db[Config.COLLECTION_HISTORICAL].distinct("scripName"))
        remaining = [t for t in tickers if t not in already_loaded]
        skipped = len(tickers) - len(remaining)
        if skipped:
            print(f"Skipping {skipped} already-loaded tickers (use --force to re-fetch them).")
        tickers = remaining

    if limit:
        tickers = tickers[:limit]

    if not tickers:
        print("Nothing to do - all requested tickers are already loaded.")
        return

    print(f"Fetching BSE history ({flag}) for {len(tickers)} ticker(s), ~{delay}s between requests "
          f"(ETA ~{len(tickers) * delay / 60:.1f} min)...")

    def report(done, total, ticker):
        print(f"  [{done}/{total}] {ticker}")

    result = fetch_and_store(db, tickers, flag=flag, delay=delay, progress=report)

    print(f"\nSynced {len(result['synced'])} tickers, {result['total_candles']} candles total.")
    if result["failed"]:
        print(f"Failed ({len(result['failed'])}):")
        for f in result["failed"][:20]:
            print(f"  ✗ {f['ticker']}: {f['reason']}")
        if len(result["failed"]) > 20:
            print(f"  ... and {len(result['failed']) - 20} more")


if __name__ == "__main__":
    main()

import logging
import threading
import time
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import Config
from app.data.db import get_db
from app.data.kite_client import get_kite
from app.live.ticker import get_latest_price, subscribe_symbols
from app.engine.registry import STRATEGIES

logger = logging.getLogger("scanner")

# Global scanner state
# {
#   "active": bool,
#   "strategy": "MACD",
#   "watchlist": ["RELIANCE", "INFY"],
#   "signals": { "RELIANCE": {"signal": "BUY", "price": 2500, "timestamp": "..."} }
# }
SCANNER_STATE = {
    "active": False,
    "strategy": "MACDStrategy",
    "interval": "day",
    "watchlist": [],
    "signals": {}
}

_scanner_scheduler = None
_scanner_bars_cache = {}  # { ticker: [list of bar dicts] }

class DummyBroker:
    def __init__(self):
        self.positions = {}
        self.history = []

    def buy(self, symbol, price, qty=1, reason=""):
        self.positions[symbol] = {"qty": qty, "avg_price": price}

    def sell(self, symbol, price, qty=1, reason=""):
        if symbol in self.positions:
            del self.positions[symbol]


def _init_bars_for_ticker(db, ticker, interval="day", num_bars=50):
    """Fetch the most recent bars from Mongo to 'warm up' the indicators."""
    collection = db[Config.COLLECTION_HISTORICAL]
    query = {"scripName": ticker}
    if interval == "day":
        query["$or"] = [{"interval": "day"}, {"interval": {"$exists": False}}]
    else:
        query["interval"] = interval
        
    docs = list(collection.find(query).sort("priceDate", -1).limit(num_bars))
    docs.reverse()
    
    bars = []
    for d in docs:
        bars.append({
            "scripName": d["scripName"],
            "priceDate": d["priceDate"],
            "Value": d["Value"],
            "Volume": d.get("Volume", 0),
            "Open": d.get("Open", d["Value"]),
            "High": d.get("High", d["Value"]),
            "Low": d.get("Low", d["Value"])
        })
    return bars


def _run_scanner_tick():
    if not SCANNER_STATE["active"]:
        return

    db = get_db()
    kite = get_kite()
    if not db or not kite:
        return

    strategy_name = SCANNER_STATE["strategy"]
    watchlist = SCANNER_STATE["watchlist"]
    
    if not watchlist:
        return
        
    StrategyClass = STRATEGIES.get(strategy_name)
    if not StrategyClass:
        return

    # Subscribe websocket to watchlist
    subscribe_symbols(watchlist)

    new_signals = {}
    timestamp = pd.Timestamp.now("UTC").isoformat()

    interval = SCANNER_STATE.get("interval", "day")
    
    for ticker in watchlist:
        # 1. Get latest price from websocket cache
        price = get_latest_price(ticker)
        if not price:
            # Fallback to existing signals if no price yet
            if ticker in SCANNER_STATE["signals"]:
                new_signals[ticker] = SCANNER_STATE["signals"][ticker]
            continue

        # 2. Get or init bars
        if ticker not in _scanner_bars_cache:
            _scanner_bars_cache[ticker] = _init_bars_for_ticker(db, ticker, interval)
            
        bars = _scanner_bars_cache[ticker]
        bars.append({
            "scripName": ticker, 
            "priceDate": timestamp, 
            "Value": price, 
            "Volume": 0,
            "Open": price,
            "High": price,
            "Low": price
        })
        
        # Keep window bounded so memory doesn't explode
        if len(bars) > 100:
            bars = bars[-100:]
            _scanner_bars_cache[ticker] = bars

        # 3. Evaluate Strategy
        df = pd.DataFrame(bars)
        
        if interval != "day" and not df.empty:
            freq_map = {"minute": "1T", "3minute": "3T", "5minute": "5T", "10minute": "10T", "15minute": "15T", "30minute": "30T", "60minute": "60T"}
            freq = freq_map.get(interval)
            if freq:
                if "Open" not in df.columns: df["Open"] = df["Value"]
                if "High" not in df.columns: df["High"] = df["Value"]
                if "Low" not in df.columns: df["Low"] = df["Value"]
                
                df["priceDate"] = pd.to_datetime(df["priceDate"])
                df.set_index("priceDate", inplace=True)
                df = df.resample(freq).agg({
                    "scripName": "first",
                    "Value": "last",
                    "Volume": "sum",
                    "Open": "first",
                    "High": "max",
                    "Low": "min"
                }).dropna().reset_index()
                df["priceDate"] = df["priceDate"].dt.strftime("%Y-%m-%d %H:%M:%S")

        broker = DummyBroker()
        
        # We assume they are NOT bought currently, we just want to see if this bar triggers a BUY
        strategy = StrategyClass(broker, position_sizer=None)
        strategy.bought = False 

        try:
            strategy.on_bar(df, len(df) - 1)
            
            # Check if a signal was generated
            if ticker in broker.positions:
                new_signals[ticker] = {
                    "signal": "BUY",
                    "price": price,
                    "timestamp": timestamp
                }
            elif ticker in SCANNER_STATE["signals"]:
                # If it was a BUY before, check if it's still a BUY, or if it generated a SELL
                # But since bought was False, a SELL won't trigger if it checks self.bought.
                # Just keep the old signal unless we want to clear it.
                # Let's just keep the old signal for visibility.
                new_signals[ticker] = SCANNER_STATE["signals"][ticker]
                
        except Exception:
            logger.exception(f"Scanner failed to evaluate {strategy_name} for {ticker}")

    SCANNER_STATE["signals"] = new_signals


def start_scanner_scheduler():
    global _scanner_scheduler
    if _scanner_scheduler is not None:
        return _scanner_scheduler
        
    _scanner_scheduler = BackgroundScheduler(daemon=True)
    _scanner_scheduler.add_job(
        _run_scanner_tick,
        "interval",
        seconds=Config.LIVE_POLL_INTERVAL_SECONDS,
        id="scanner_engine_tick",
        max_instances=1,
        coalesce=True,
    )
    _scanner_scheduler.start()
    return _scanner_scheduler

def set_scanner(active, strategy, watchlist, interval="day"):
    SCANNER_STATE["active"] = active
    if active:
        SCANNER_STATE["strategy"] = strategy
        SCANNER_STATE["interval"] = interval
        SCANNER_STATE["watchlist"] = watchlist
        # Clear cache so we pull fresh history when switching strategies/tickers
        _scanner_bars_cache.clear()
        SCANNER_STATE["signals"].clear()
        logger.info(f"Scanner activated for {strategy} ({interval}) on {len(watchlist)} tickers.")
    else:
        logger.info("Scanner deactivated.")

def get_scanner_state():
    return SCANNER_STATE

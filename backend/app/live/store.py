"""
Mongo persistence for live trading sessions, so a session survives a
backend restart. Requires MongoDB - live trading (unlike backtesting)
has no synthetic-data-only fallback, since a session's whole point is
to keep running unattended.
"""
import uuid
from datetime import datetime, timezone
from app.config import Config
from app.utils.serialization import to_native

MAX_BARS = 600  # generous headroom over the largest strategy lookback (SMA-50)
MAX_EQUITY_POINTS = 2000  # one point per tick; a few tiny fields each, cheap to keep more of these than bars


def _now():
    return datetime.now(timezone.utc).isoformat()


def create_session(db, tickers, strategy, mode, capital, max_capital_per_trade=None,
                    daily_loss_limit=None, position_sizing=None, interval="day"):
    """`tickers`: a list of one or more symbols sharing one capital pool for
    this session - same portfolio model as multi-ticker backtests, applied
    to live/paper trading instead of one independent session per symbol."""
    doc = {
        "_id": str(uuid.uuid4()),
        "tickers": list(tickers),
        "strategy": strategy,
        "interval": interval,
        "mode": mode,  # "paper" | "live"
        "status": "running",  # "running" | "stopped" | "halted"
        "halt_reason": None,
        "capital": capital,
        "cash": capital,
        "positions": {},
        "history": [],
        "realized_pnl": 0.0,
        "total_taxes": 0.0,
        "max_capital_per_trade": max_capital_per_trade,
        "daily_loss_limit": daily_loss_limit,
        # {"mode": "full"|"fixed_fraction"|"volatility_target", ...params} - see
        # app/engine/position_sizing.py; None/omitted = full-capital (default)
        "position_sizing": position_sizing,
        "daily_realized_pnl": 0.0,
        "daily_date": datetime.now(timezone.utc).date().isoformat(),
        "bars": {ticker: [] for ticker in tickers},  # keyed by ticker, like BacktestRunner.dfs
        "last_prices": {},  # {ticker: price}
        "equity_curve": [],  # [{time, equity, price}, ...] - one point per tick
        "tick_count": 0,
        "created_at": _now(),
        "updated_at": _now(),
    }
    db[Config.COLLECTION_LIVE_SESSIONS].insert_one(doc)
    return doc


def get_session(db, session_id):
    return db[Config.COLLECTION_LIVE_SESSIONS].find_one({"_id": session_id})


def list_sessions(db, status=None):
    query = {"status": status} if status else {}
    return list(db[Config.COLLECTION_LIVE_SESSIONS].find(query).sort("created_at", -1))


def save_session(db, session):
    session["updated_at"] = _now()
    for ticker, bars in session.get("bars", {}).items():
        if len(bars) > MAX_BARS:
            session["bars"][ticker] = bars[-MAX_BARS:]
    if len(session.get("equity_curve", [])) > MAX_EQUITY_POINTS:
        session["equity_curve"] = session["equity_curve"][-MAX_EQUITY_POINTS:]
    # Prices/quantities/indicator state all ultimately trace back to pandas
    # DataFrame cells (numpy scalar types), which pymongo's BSON encoder
    # can't serialize - sanitize the whole document here, once, rather than
    # chasing every individual numpy leak across the engine/strategies.
    session = to_native(session)
    db[Config.COLLECTION_LIVE_SESSIONS].replace_one({"_id": session["_id"]}, session, upsert=True)
    return session


def stop_session(db, session_id, reason=None):
    db[Config.COLLECTION_LIVE_SESSIONS].update_one(
        {"_id": session_id},
        {"$set": {"status": "stopped", "halt_reason": reason, "updated_at": _now()}},
    )


def halt_session(db, session_id, reason):
    db[Config.COLLECTION_LIVE_SESSIONS].update_one(
        {"_id": session_id},
        {"$set": {"status": "halted", "halt_reason": reason, "updated_at": _now()}},
    )


def delete_session(db, session_id):
    """Permanently removes a session document. Only meant for sessions that
    are already stopped/halted - deleting a running session would just let
    it keep trading with no record, so callers must stop it first."""
    result = db[Config.COLLECTION_LIVE_SESSIONS].delete_one({"_id": session_id})
    return result.deleted_count > 0


def stop_all_sessions(db, reason="Kill switch triggered"):
    result = db[Config.COLLECTION_LIVE_SESSIONS].update_many(
        {"status": "running"},
        {"$set": {"status": "stopped", "halt_reason": reason, "updated_at": _now()}},
    )
    return result.modified_count

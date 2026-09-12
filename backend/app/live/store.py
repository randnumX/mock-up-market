"""
Mongo persistence for live trading sessions, so a session survives a
backend restart. Requires MongoDB - live trading (unlike backtesting)
has no synthetic-data-only fallback, since a session's whole point is
to keep running unattended.
"""
import uuid
from datetime import datetime, timezone
from app.config import Config

MAX_BARS = 600  # generous headroom over the largest strategy lookback (SMA-50)


def _now():
    return datetime.now(timezone.utc).isoformat()


def create_session(db, ticker, strategy, mode, capital, max_capital_per_trade=None, daily_loss_limit=None):
    doc = {
        "_id": str(uuid.uuid4()),
        "ticker": ticker,
        "strategy": strategy,
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
        "daily_realized_pnl": 0.0,
        "daily_date": datetime.now(timezone.utc).date().isoformat(),
        "bars": [],
        "last_price": None,
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
    if len(session.get("bars", [])) > MAX_BARS:
        session["bars"] = session["bars"][-MAX_BARS:]
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


def stop_all_sessions(db, reason="Kill switch triggered"):
    result = db[Config.COLLECTION_LIVE_SESSIONS].update_many(
        {"status": "running"},
        {"$set": {"status": "stopped", "halt_reason": reason, "updated_at": _now()}},
    )
    return result.modified_count

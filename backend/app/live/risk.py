"""
Pure, DB-free risk checks the live engine consults every tick. Kept
separate from engine.py so the safety logic itself is trivially unit
testable without spinning up Mongo/Kite.
"""
from datetime import datetime, timezone


def rollover_daily_pnl(session):
    """Reset the daily realized-PnL counter when UTC date has changed."""
    today = datetime.now(timezone.utc).date().isoformat()
    if session.get("daily_date") != today:
        session["daily_date"] = today
        session["daily_realized_pnl"] = 0.0
    return session


def check_daily_loss_limit(session):
    """
    Returns (breached: bool, reason: str|None). A daily_loss_limit is a
    positive rupee amount; breached once cumulative losses for the day
    meet or exceed it.
    """
    limit = session.get("daily_loss_limit")
    if not limit:
        return False, None
    daily_pnl = session.get("daily_realized_pnl", 0.0)
    if daily_pnl <= -abs(limit):
        return True, f"Daily loss limit hit: ₹{abs(daily_pnl):.2f} lost (limit ₹{limit:.2f})"
    return False, None


def check_capital_exhausted(session):
    """A session that has burned through essentially all its cash and holds
    no position can't trade further - halt instead of spinning forever."""
    cash = session.get("cash", 0)
    has_position = bool(session.get("positions"))
    if not has_position and cash < 1:
        return True, "Capital exhausted"
    return False, None

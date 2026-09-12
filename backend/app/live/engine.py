"""
The live trading engine: an in-process APScheduler job that wakes up
every LIVE_POLL_INTERVAL_SECONDS, advances every running session by one
price tick, and runs that session's Strategy exactly the way the
backtester does (same on_bar contract) - just one bar at a time, against
whatever the session's Broker (PaperBroker or KiteLiveBroker) does with it.

Session state (cash, positions, trade history, and the rolling bar
history with whatever indicator columns the strategy has computed so
far) is persisted to Mongo after every tick, so a backend restart picks
up exactly where each session left off.
"""
import logging
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import Config
from app.data.db import get_db
from app.data.kite_client import get_kite
from app.data.providers.kite_provider import KiteProvider
from app.data.providers.dummy_provider import DummyProvider
from app.engine.registry import STRATEGIES
from app.live.broker import PaperBroker, KiteLiveBroker
from app.live import store, risk
from app.live.market_hours import is_market_open

logger = logging.getLogger("live_engine")
_scheduler = None


def _price_provider_for_session(session, kite):
    """
    Live mode always needs Kite (real prices for real orders). Paper mode
    prefers real Kite prices when connected, but falls back to a simulated
    tick generator so "start a paper session" works with zero setup too.
    """
    if session["mode"] == "live":
        return KiteProvider(kite) if kite else None
    return KiteProvider(kite) if kite else DummyProvider()


def _hydrate_broker(session, kite):
    if session["mode"] == "paper":
        broker = PaperBroker(session["capital"], session.get("max_capital_per_trade"))
    else:
        broker = KiteLiveBroker(kite, session["capital"], session.get("max_capital_per_trade"))
    broker.capital = session["cash"]
    broker.positions = session["positions"]
    broker.history = session["history"]
    broker.realized_pnl = session["realized_pnl"]
    broker.total_taxes = session["total_taxes"]
    return broker


def run_tick(db, session, kite):
    """Advance one session by exactly one price tick. Mutates and persists `session`."""
    risk.rollover_daily_pnl(session)

    provider = _price_provider_for_session(session, kite)
    if provider is None:
        # Live mode with no Kite connection - can't safely trade, wait for reconnect.
        return session

    last_known = session.get("last_price") or (session["bars"][-1]["Value"] if session["bars"] else None)
    price = provider.get_latest_price(session["ticker"], last_known_price=last_known)
    if price is None:
        return session

    bars = session.get("bars", [])
    bars.append({"scripName": session["ticker"], "priceDate": pd.Timestamp.now("UTC").isoformat(), "Value": price, "Volume": 0})
    df = pd.DataFrame(bars)

    broker = _hydrate_broker(session, kite)
    StrategyClass = STRATEGIES[session["strategy"]]
    strategy = StrategyClass(broker)
    for k, v in session.get("strategy_state", {}).items():
        setattr(strategy, k, v)
    # Position state is the ground truth (safer than a possibly-stale flag).
    strategy.bought = session["ticker"] in broker.positions

    trades_before = len(broker.history)
    try:
        strategy.on_bar(df, len(df) - 1)
    except Exception:
        logger.exception("Strategy on_bar failed for session %s", session["_id"])

    new_trades = broker.history[trades_before:]
    for t in new_trades:
        if t.get("type") == "SELL" and "pnl" in t:
            session["daily_realized_pnl"] = session.get("daily_realized_pnl", 0.0) + t["pnl"]

    session["bars"] = df.to_dict(orient="records")
    session["strategy_state"] = {k: v for k, v in vars(strategy).items() if k != "broker"}
    session["cash"] = broker.capital
    session["positions"] = broker.positions
    session["history"] = broker.history
    session["realized_pnl"] = broker.realized_pnl
    session["total_taxes"] = broker.total_taxes
    session["last_price"] = price
    session["tick_count"] = session.get("tick_count", 0) + 1

    breached, reason = risk.check_daily_loss_limit(session)
    if not breached:
        breached, reason = risk.check_capital_exhausted(session)
    if breached:
        session["status"] = "halted"
        session["halt_reason"] = reason
        logger.warning("Session %s halted: %s", session["_id"], reason)

    return session


def summarize_session(session):
    """Derived, display-ready fields on top of the raw persisted session doc."""
    last_price = session.get("last_price") or 0
    positions = session.get("positions", {}).values()
    open_value = sum(pos["qty"] * last_price for pos in positions)
    open_cost = sum(pos["qty"] * pos["avg_price"] for pos in positions)
    equity = session.get("cash", 0) + open_value
    roi = ((equity - session["capital"]) / session["capital"] * 100) if session["capital"] else 0
    return {
        **session,
        "open_position_value": round(open_value, 2),
        "unrealized_pnl": round(open_value - open_cost, 2),
        "equity": round(equity, 2),
        "roi": round(roi, 2),
    }


def _tick_all_sessions():
    db = get_db()
    if db is None:
        return

    kite = get_kite()
    ignore_hours = Config.LIVE_IGNORE_MARKET_HOURS

    for session in store.list_sessions(db, status="running"):
        uses_real_feed = session["mode"] == "live" or kite is not None
        if uses_real_feed and not ignore_hours and not is_market_open():
            continue
        try:
            session = run_tick(db, session, kite)
            store.save_session(db, session)
        except Exception:
            logger.exception("Tick failed for session %s", session.get("_id"))


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _tick_all_sessions,
        "interval",
        seconds=Config.LIVE_POLL_INTERVAL_SECONDS,
        id="live_engine_tick",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    return _scheduler

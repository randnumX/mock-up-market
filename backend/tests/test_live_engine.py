import mongomock
from app.live import store
from app.live.engine import run_tick, summarize_session


def make_db():
    return mongomock.MongoClient().db


def test_paper_session_ticks_without_kite_using_simulated_feed():
    db = make_db()
    session = store.create_session(db, ticker="SBIN", strategy="rsi", mode="paper", capital=50000)

    for _ in range(5):
        session = run_tick(db, session, kite=None)

    assert session["tick_count"] == 5
    assert len(session["bars"]) == 5
    assert session["last_price"] is not None
    assert session["status"] == "running"


def test_session_survives_round_trip_through_mongo():
    db = make_db()
    session = store.create_session(db, ticker="TCS", strategy="macd", mode="paper", capital=25000)
    session = run_tick(db, session, kite=None)
    store.save_session(db, session)

    reloaded = store.get_session(db, session["_id"])
    assert reloaded["tick_count"] == 1
    assert reloaded["ticker"] == "TCS"

    # Engine must be able to resume ticking from a freshly reloaded document.
    reloaded = run_tick(db, reloaded, kite=None)
    assert reloaded["tick_count"] == 2


def test_daily_loss_limit_halts_session_on_next_tick():
    db = make_db()
    session = store.create_session(
        db, ticker="SBIN", strategy="macd", mode="paper", capital=50000, daily_loss_limit=1000
    )
    session["daily_realized_pnl"] = -5000  # simulate prior losses today

    session = run_tick(db, session, kite=None)

    assert session["status"] == "halted"
    assert "loss limit" in session["halt_reason"].lower()


def test_summarize_session_includes_derived_fields():
    db = make_db()
    session = store.create_session(db, ticker="INFY", strategy="bollinger", mode="paper", capital=10000)
    session = run_tick(db, session, kite=None)

    summary = summarize_session(session)
    assert "equity" in summary
    assert "roi" in summary
    assert "open_position_value" in summary

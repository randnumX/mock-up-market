import mongomock
from app.live import store
from app.live.engine import run_tick, summarize_session


def make_db():
    return mongomock.MongoClient().db


def test_paper_session_ticks_without_kite_using_simulated_feed():
    db = make_db()
    session = store.create_session(db, tickers=["SBIN"], strategy="rsi", mode="paper", capital=50000)

    for _ in range(5):
        session = run_tick(db, session, kite=None)

    assert session["tick_count"] == 5
    assert len(session["bars"]["SBIN"]) == 5
    assert session["last_prices"]["SBIN"] is not None
    assert session["status"] == "running"


def test_session_survives_round_trip_through_mongo():
    db = make_db()
    session = store.create_session(db, tickers=["TCS"], strategy="macd", mode="paper", capital=25000)
    session = run_tick(db, session, kite=None)
    store.save_session(db, session)

    reloaded = store.get_session(db, session["_id"])
    assert reloaded["tick_count"] == 1
    assert reloaded["tickers"] == ["TCS"]

    # Engine must be able to resume ticking from a freshly reloaded document.
    reloaded = run_tick(db, reloaded, kite=None)
    assert reloaded["tick_count"] == 2


def test_multi_ticker_session_shares_one_capital_pool():
    """A portfolio session (multiple tickers) shares one broker/cash pool -
    same model as a multi-ticker backtest, not N independent accounts."""
    db = make_db()
    session = store.create_session(
        db, tickers=["SBIN", "TCS", "INFY"], strategy="rsi", mode="paper", capital=50000
    )

    for _ in range(3):
        session = run_tick(db, session, kite=None)

    assert session["tick_count"] == 3
    assert set(session["bars"].keys()) == {"SBIN", "TCS", "INFY"}
    assert all(session["last_prices"].get(t) is not None for t in ["SBIN", "TCS", "INFY"])
    # One shared cash pool, not capital-per-ticker.
    assert session["cash"] <= session["capital"]

    summary = summarize_session(session)
    assert set(summary["ticker_stats"].keys()) == {"SBIN", "TCS", "INFY"}


def test_run_tick_appends_one_equity_curve_point_per_tick():
    db = make_db()
    session = store.create_session(db, tickers=["SBIN"], strategy="rsi", mode="paper", capital=50000)

    for _ in range(4):
        session = run_tick(db, session, kite=None)

    assert len(session["equity_curve"]) == 4
    point = session["equity_curve"][-1]
    assert "time" in point and "equity" in point and "price" in point
    assert point["equity"] > 0


def test_save_session_prunes_equity_curve_past_max_points():
    db = make_db()
    session = store.create_session(db, tickers=["SBIN"], strategy="rsi", mode="paper", capital=50000)
    session["equity_curve"] = [{"time": str(i), "equity": 50000, "price": 100} for i in range(store.MAX_EQUITY_POINTS + 50)]

    saved = store.save_session(db, session)

    assert len(saved["equity_curve"]) == store.MAX_EQUITY_POINTS


def test_daily_loss_limit_halts_session_on_next_tick():
    db = make_db()
    session = store.create_session(
        db, tickers=["SBIN"], strategy="macd", mode="paper", capital=50000, daily_loss_limit=1000
    )
    session["daily_realized_pnl"] = -5000  # simulate prior losses today

    session = run_tick(db, session, kite=None)

    assert session["status"] == "halted"
    assert "loss limit" in session["halt_reason"].lower()


def test_summarize_session_includes_derived_fields():
    db = make_db()
    session = store.create_session(db, tickers=["INFY"], strategy="bollinger", mode="paper", capital=10000)
    session = run_tick(db, session, kite=None)

    summary = summarize_session(session)
    assert "equity" in summary
    assert "roi" in summary
    assert "open_position_value" in summary
    assert "ticker_stats" in summary


def test_delete_session_removes_it_from_mongo():
    db = make_db()
    session = store.create_session(db, tickers=["SBIN"], strategy="rsi", mode="paper", capital=50000)
    store.stop_session(db, session["_id"])

    deleted = store.delete_session(db, session["_id"])

    assert deleted is True
    assert store.get_session(db, session["_id"]) is None


def test_delete_session_returns_false_for_unknown_id():
    db = make_db()
    assert store.delete_session(db, "does-not-exist") is False

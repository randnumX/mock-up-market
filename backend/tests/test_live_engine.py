import logging
import mongomock
import pandas as pd
from app.live import store
from app.engine.position_sizing import build_sizer
from app.engine.registry import STRATEGIES
from app.live import engine
from app.live.engine import run_tick, summarize_session, _resample_bars


def make_db():
    return mongomock.MongoClient().db


def test_indicator_columns_persist_across_ticks():
    """A backtest calls on_bar against one long-lived DataFrame so indicator
    columns accumulate; live rebuilds the frame from stored bars every tick.
    If the indicators aren't persisted with the bars, recursive ones
    (EMA/MACD, which read df[i-1]) raise KeyError as soon as they need a
    previous value, and window ones (RSI/VWAP) silently go NaN and never
    trade - 40+ ticks with zero trades and zero visible cause."""
    db = make_db()
    session = store.create_session(db, tickers=["SBIN"], strategy="ema_scalp", mode="paper", capital=50000)

    errors = []

    class CaptureErrors(logging.Handler):
        def emit(self, record):
            if record.levelno >= logging.ERROR:
                errors.append(record.getMessage())

    handler = CaptureErrors()
    logging.getLogger("live_engine").addHandler(handler)
    try:
        # Past ema_scalp's 9/21-bar warm-up, where the recursive EMA starts
        # needing the previous bar's value.
        for _ in range(25):
            session = run_tick(db, session, kite=None)
            store.save_session(db, session)
    finally:
        logging.getLogger("live_engine").removeHandler(handler)

    assert errors == [], f"strategy raised during live ticks: {errors}"
    last_bar = session["bars"]["SBIN"][-1]
    assert "ema_fast" in last_bar and "ema_slow" in last_bar
    assert last_bar["ema_fast"] is not None


def test_run_tick_records_which_data_source_served_the_price():
    """Previously invisible to the UI - a paper session with no Kite
    connection silently traded on simulated data with no indication of
    that anywhere in the session's own record."""
    db = make_db()
    session = store.create_session(db, tickers=["SBIN"], strategy="rsi", mode="paper", capital=50000)
    assert session["data_source"] is None  # unresolved until the first tick

    session = run_tick(db, session, kite=None)

    assert session["data_source"] == "generated"  # DummyProvider.name, since kite=None


def test_run_tick_stamps_bars_in_ist_not_utc():
    """ORB/VWAP parse HH:MM out of a bar's priceDate and compare it against
    literal NSE session times ("09:30", "15:15") - if bars were stamped in
    UTC (5:30 behind IST), every such comparison would silently check the
    wrong clock and both strategies would misbehave in live/paper trading."""
    db = make_db()
    session = store.create_session(db, tickers=["SBIN"], strategy="rsi", mode="paper", capital=50000)
    session = run_tick(db, session, kite=None)

    bar_time = session["bars"]["SBIN"][-1]["priceDate"]
    real_ist_now = pd.Timestamp.now(tz="Asia/Kolkata")
    bar_dt = pd.Timestamp(bar_time)
    if bar_dt.tzinfo is None:
        bar_dt = bar_dt.tz_localize("Asia/Kolkata")

    # The bar's wall-clock hour should match real IST time, not be off by
    # the ~5:30 UTC offset.
    assert abs((bar_dt - real_ist_now).total_seconds()) < 60


def test_resample_bars_output_is_ist_not_utc():
    bars = [
        {"scripName": "SBIN", "priceDate": pd.Timestamp("2026-09-21 09:16:00", tz="Asia/Kolkata").isoformat(),
         "Value": 100, "Volume": 0, "Open": 100, "High": 100, "Low": 100},
    ]
    df = _resample_bars(bars, "SBIN", "5minute")

    assert df.iloc[0]["priceDate"] == "2026-09-21 09:15:00"


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


def test_square_off_closes_intraday_position_at_market_close():
    """An intraday session holding a position when the market closes would
    otherwise just stop ticking and carry it overnight - which for a real
    MIS position means the broker force-closes it at its own price."""
    db = make_db()
    session = store.create_session(
        db, tickers=["SBIN"], strategy="rsi", mode="paper", capital=50000, interval="5minute"
    )
    session["positions"] = {"SBIN": {"qty": 10, "avg_price": 600.0}}
    session["last_prices"] = {"SBIN": 650.0}
    session["cash"] = 44000.0

    closed = engine._square_off_if_needed(db, session, kite=None)

    assert closed is True
    assert session["positions"] == {}
    assert len(session["history"]) == 1
    assert session["history"][0]["type"] == "SELL"


def test_square_off_leaves_day_interval_sessions_alone():
    """`day` interval is the swing/delivery (CNC) case - holding overnight
    is the entire point, so it must not be squared off."""
    db = make_db()
    session = store.create_session(
        db, tickers=["SBIN"], strategy="rsi", mode="paper", capital=50000, interval="day"
    )
    session["positions"] = {"SBIN": {"qty": 10, "avg_price": 600.0}}
    session["last_prices"] = {"SBIN": 650.0}

    assert engine._square_off_if_needed(db, session, kite=None) is False
    assert session["positions"] == {"SBIN": {"qty": 10, "avg_price": 600.0}}


def test_backfill_is_attempted_once_per_ticker():
    """A ticker with no available history must not re-request on every tick
    forever - the attempt is recorded even when it yields nothing."""
    db = make_db()
    session = store.create_session(db, tickers=["NOSUCHTICKER"], strategy="rsi", mode="paper", capital=50000)

    session = run_tick(db, session, kite=None)

    assert "NOSUCHTICKER" in session.get("backfill_attempted", [])


def test_warm_up_computes_indicators_across_backfilled_history():
    """Seeding raw OHLCV bars is not enough. Strategies build indicator
    columns inside on_bar, and several only create them in an `if i == 0`
    branch - handing them a pre-seeded frame they never walked means
    ema_scalp/macd raise KeyError on df[i-1], and the rest end up with a
    value only on the newest row so every df[i-1] lookup is NaN."""
    db = make_db()
    session = store.create_session(
        db, tickers=["SBIN"], strategy="ema_scalp", mode="paper", capital=50000
    )
    # Stand in for backfilled history (no indicator columns, as fetched).
    session["bars"]["SBIN"] = [
        {"scripName": "SBIN", "priceDate": f"2026-03-{(i % 28) + 1:02d}",
         "Value": 600.0 + i, "Volume": 0, "Open": 600.0 + i, "High": 600.0 + i, "Low": 600.0 + i}
        for i in range(60)
    ]

    engine._warm_up_indicators(
        session, "SBIN", STRATEGIES["ema_scalp"], build_sizer(None), session.setdefault("strategy_state", {})
    )

    bars = session["bars"]["SBIN"]
    mid = bars[len(bars) // 2]
    assert mid.get("ema_fast") is not None, "indicators must be warm across history, not just the newest bar"
    assert mid.get("ema_slow") is not None
    # And the strategy must now tick without raising.
    session = run_tick(db, session, kite=None)
    assert session["bars"]["SBIN"][-1].get("ema_fast") is not None

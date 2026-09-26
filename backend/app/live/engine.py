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
import time

import pandas as pd

from app.logging_config import get_logger
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import Config
from app.data.db import get_db
from app.data.kite_client import get_kite
from app.data.providers.kite_provider import KiteProvider
from app.data.providers.dummy_provider import DummyProvider
from app.engine.registry import STRATEGIES
from app.engine.position_sizing import build_sizer
from app.live.broker import PaperBroker, KiteLiveBroker
from app.live import store, risk
from app.live.market_hours import is_market_open
from app.utils.serialization import records_to_native, to_native
from app.utils.intervals import FREQ_MAP, days_for_bars

logger = get_logger("live.engine")
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
    # An intraday-interval session is MIS (and taxed as intraday); a `day`
    # session is delivery/CNC. Previously every order defaulted to CNC
    # regardless, so a 5-minute strategy placed delivery orders and paid
    # delivery STT (~8x the intraday rate) in backtests.
    is_intraday = session.get("interval", "day") != "day"
    if session["mode"] == "paper":
        broker = PaperBroker(session["capital"], session.get("max_capital_per_trade"), is_intraday=is_intraday)
    else:
        broker = KiteLiveBroker(kite, session["capital"], session.get("max_capital_per_trade"), is_intraday=is_intraday)
    broker.capital = session["cash"]
    broker.positions = session["positions"]
    broker.history = session["history"]
    broker.realized_pnl = session["realized_pnl"]
    broker.total_taxes = session["total_taxes"]
    return broker


def _resample_bars(bars, ticker, interval):
    """Same OHLCV resample BacktestRunner-adjacent code uses elsewhere -
    turns raw per-tick bars into interval-sized bars for a single ticker."""
    df = pd.DataFrame(bars)
    if df.empty or interval == "day":
        return df

    freq = FREQ_MAP.get(interval)
    if not freq:
        return df

    if "Open" not in df.columns: df["Open"] = df["Value"]
    if "High" not in df.columns: df["High"] = df["Value"]
    if "Low" not in df.columns: df["Low"] = df["Value"]

    # A freshly-appended raw tick's priceDate is ISO8601-with-T
    # (pd.Timestamp.now().isoformat()), while bars already resampled on a
    # prior tick were re-stored as "%Y-%m-%d %H:%M:%S" (see the strftime
    # below) - the column is genuinely mixed-format, which newer pandas no
    # longer infers automatically without an explicit hint.
    # utc=True: the tz-aware isoformat() ticks and tz-naive re-stored bars
    # can't otherwise coexist in one column (pandas refuses to guess).
    df["priceDate"] = pd.to_datetime(df["priceDate"], format="mixed", utc=True)
    df.set_index("priceDate", inplace=True)

    agg = {
        "scripName": "first",
        "Value": "last",
        "Volume": "sum",
        "Open": "first",
        "High": "max",
        "Low": "min",
    }
    # Carry any indicator columns a strategy wrote on an earlier tick
    # (ema_fast, rsi, vwap, ...) through the resample as well. Dropping them
    # here would hand the strategy a bare OHLCV frame every tick, and any
    # recursive indicator (EMA/MACD read df[i-1]) would have no previous
    # value to build on.
    for col in df.columns:
        if col not in agg:
            agg[col] = "last"

    # subset=["Value"]: only drop buckets with no price data. A bare
    # .dropna() would also delete every row whose indicator columns are
    # still NaN (the warm-up rows before an indicator has enough history).
    df = df.resample(freq).agg(agg).dropna(subset=["Value"]).reset_index()
    # Convert back to IST before stringifying - ORB/VWAP parse the HH:MM out
    # of this string and compare it against literal NSE session times
    # ("09:30", "15:15"), the same convention backtest data (sourced from
    # Kite, already in IST) already uses. Leaving this in UTC after the
    # utc=True resample above silently shifts every such comparison by 5:30.
    df["priceDate"] = df["priceDate"].dt.tz_convert("Asia/Kolkata").dt.strftime("%Y-%m-%d %H:%M:%S")
    return df


# Enough bars to clear every strategy's lookback with headroom (the
# largest is SMA crossover's 50) plus room for today's session so far.
BACKFILL_BARS = 120


def _backfill_ticker(db, session, ticker, kite):
    """
    Seed a ticker's bar history from real historical candles so the strategy
    starts warm.

    Without this a session begins with zero bars and has to accumulate them
    one per interval bucket, so nothing can signal until the strategy's
    lookback is covered: on a 15-minute interval that's ~7.75h for MACD and
    ~12.75h for SMA crossover, both longer than the 6.25h trading day. It's
    also what makes a late-started ORB session compute its opening range
    from real 9:15-9:30 candles instead of whatever it happened to catch.

    Returns the number of bars seeded (0 if no real history was available).
    Deliberately skips DummyProvider: synthetic warm-up would be misleading,
    and it ignores `interval` anyway, so its daily timestamps would corrupt
    intraday resampling.
    """
    interval = session.get("interval", "day")
    provider = KiteProvider(kite) if kite else None
    source = "kite"

    if provider is None or not provider.is_available():
        if db is None:
            return 0
        from app.data.providers.mongo_provider import MongoProvider
        provider = MongoProvider(db)
        source = "mongodb"
        if not provider.is_available():
            return 0

    try:
        df = provider.get_history(
            ticker, days=days_for_bars(interval, BACKFILL_BARS), interval=interval
        )
    except Exception:
        logger.exception("Backfill failed for %s (%s)", ticker, source)
        return 0

    if df is None or df.empty:
        return 0

    df = df.tail(BACKFILL_BARS)
    bars = records_to_native(df.to_dict(orient="records"))
    # Normalize to the bar shape run_tick appends, so resampling and the
    # strategies see one consistent schema.
    seeded = []
    for b in bars:
        value = b.get("Value")
        if value is None:
            continue
        seeded.append({
            "scripName": ticker,
            "priceDate": str(b.get("priceDate")),
            "Value": value,
            "Volume": b.get("Volume", 0) or 0,
            "Open": b.get("Open", value),
            "High": b.get("High", value),
            "Low": b.get("Low", value),
        })

    session["bars"][ticker] = seeded
    return len(seeded)


class _NullBroker:
    """Absorbs orders during indicator warm-up so replaying a strategy over
    backfilled history computes its indicators without booking phantom
    trades against the session's real broker."""
    capital = 0.0

    def __init__(self):
        self.positions = {}
        self.history = []

    def place_order(self, *args, **kwargs):
        return False


def _warm_up_indicators(session, ticker, StrategyClass, sizer, strategy_state):
    """
    Replay the strategy across the backfilled bars so every bar gets its
    indicator columns, then persist those columns and the strategy's own
    instance state.

    Seeding raw OHLCV alone is not enough: strategies build their indicator
    columns inside on_bar, and several only create them in an `if i == 0`
    branch. Handing them a 120-bar frame they've never walked means that
    branch never runs (ema_scalp/macd then raise KeyError on df[i-1]), and
    for the rest only the newest row gets a value, so every df[i-1] lookup
    is NaN and no signal can ever fire.
    """
    bars = session["bars"].get(ticker) or []
    if not bars:
        return

    df = _resample_bars(bars, ticker, session.get("interval", "day"))
    if df.empty:
        return

    strategy = StrategyClass(_NullBroker(), position_sizer=sizer)
    try:
        for i in range(len(df)):
            strategy.on_bar(df, i)
    except Exception:
        logger.exception("Indicator warm-up failed for %s - continuing cold", ticker)
        return

    session["bars"][ticker] = records_to_native(df.to_dict(orient="records"))
    strategy_state[ticker] = {
        k: to_native(v) for k, v in vars(strategy).items() if k not in ("broker", "position_sizer")
    }


def _backfill_session(db, session, kite):
    """Backfill every ticker that has no history yet. Runs on the first tick
    after a session is created *and* after a backend restart, so a restart
    mid-session doesn't leave a permanent hole."""
    attempted = set(session.get("backfill_attempted", []))
    tickers = session.get("tickers") or []
    pending = [t for t in tickers if t not in attempted and not session.get("bars", {}).get(t)]
    if not pending:
        return

    logger.info(
        "Backfilling %s ticker(s) for session %s (interval=%s)",
        len(pending), session["_id"], session.get("interval", "day"),
    )
    StrategyClass = STRATEGIES[session["strategy"]]
    sizer = build_sizer(session.get("position_sizing"))
    strategy_state = session.setdefault("strategy_state", {})

    total = 0
    for ticker in pending:
        seeded = _backfill_ticker(db, session, ticker, kite)
        total += seeded
        if seeded:
            # Walk the strategy across the seeded history so its indicators
            # are actually computed, not just its raw bars present.
            _warm_up_indicators(session, ticker, StrategyClass, sizer, strategy_state)
        attempted.add(ticker)
        # Kite allows ~3 requests/sec; stay well under it. The scheduler
        # uses max_instances=1/coalesce=True so a slow first cycle just
        # delays the next one rather than piling up.
        if kite:
            time.sleep(0.35)

    # Recorded so a ticker with genuinely no history isn't re-requested on
    # every single tick forever.
    session["backfill_attempted"] = sorted(attempted)
    logger.info(
        "Backfill complete for session %s: %s bars seeded across %s ticker(s)",
        session["_id"], total, len(pending),
    )


def _tick_volume(session, ticker):
    """
    Volume traded since this session's previous tick.

    Kite's feed reports `volume_traded` as the day's running total, so the
    per-bar figure is the difference between consecutive readings. Live bars
    used to be hardcoded to Volume=0, which quietly disabled VWAP entirely:
    with no volume its weighted average collapses to the price itself, so
    its "price crossed above VWAP" test became `price > price` and could
    never fire.

    Returns 0 when no volume feed is available (no Kite / simulated feed),
    which keeps the previous behavior rather than inventing numbers.
    """
    from app.live.ticker import get_cumulative_volume

    cumulative = get_cumulative_volume(ticker)
    if cumulative is None:
        return 0

    seen = session.setdefault("cumulative_volume", {})
    previous = seen.get(ticker)
    seen[ticker] = cumulative
    if previous is None or cumulative < previous:
        # First reading of the session, or the exchange counter reset for a
        # new day - no meaningful delta to report yet.
        return 0
    return int(cumulative - previous)


def run_tick(db, session, kite):
    """
    Advance one session by one price tick, across every ticker it holds -
    same portfolio model as BacktestRunner: one shared broker/capital pool,
    one Strategy instance per ticker (own indicator state, same broker).
    Mutates and persists `session`.
    """
    risk.rollover_daily_pnl(session)

    provider = _price_provider_for_session(session, kite)
    if provider is None:
        # Live mode with no Kite connection - can't safely trade, wait for reconnect.
        return session

    # So the UI can show whether this session is actually trading on real
    # Zerodha data or the simulated fallback - previously invisible, you
    # had to read the backend logs to know which one was in play.
    session["data_source"] = provider.name

    tickers = session.get("tickers") or ([session["ticker"]] if "ticker" in session else [])
    bars_by_ticker = session.setdefault("bars", {t: [] for t in tickers})
    last_prices = session.setdefault("last_prices", {})

    _backfill_session(db, session, kite)
    bars_by_ticker = session["bars"]

    broker = _hydrate_broker(session, kite)
    StrategyClass = STRATEGIES[session["strategy"]]
    sizer = build_sizer(session.get("position_sizing"))
    strategy_state = session.get("strategy_state", {})

    trades_before = len(broker.history)
    dfs_by_ticker = {}

    for ticker in tickers:
        last_known = last_prices.get(ticker) or (bars_by_ticker[ticker][-1]["Value"] if bars_by_ticker.get(ticker) else None)
        price = provider.get_latest_price(ticker, last_known_price=last_known)
        if price is None:
            continue

        ticker_bars = bars_by_ticker.setdefault(ticker, [])
        ticker_bars.append({
            "scripName": ticker,
            # IST, not UTC: matches backtest data's convention (Kite returns
            # exchange-local time) and what ORB/VWAP's HH:MM string
            # comparisons against NSE session times assume.
            "priceDate": pd.Timestamp.now(tz="Asia/Kolkata").isoformat(),
            "Value": price,
            "Volume": _tick_volume(session, ticker),
            "Open": price,
            "High": price,
            "Low": price,
        })

        df = _resample_bars(ticker_bars, ticker, session.get("interval", "day"))
        dfs_by_ticker[ticker] = df
        last_prices[ticker] = price

        strategy = StrategyClass(broker, position_sizer=sizer)
        for k, v in strategy_state.get(ticker, {}).items():
            setattr(strategy, k, v)
        # Position state is the ground truth (safer than a possibly-stale flag).
        strategy.bought = ticker in broker.positions

        try:
            strategy.on_bar(df, len(df) - 1)
        except Exception:
            logger.exception("Strategy on_bar failed for session %s / %s", session["_id"], ticker)

        # Snapshot AFTER on_bar, not before: on_bar writes its indicator
        # columns onto df, and those have to be persisted alongside the
        # OHLCV bars. A backtest calls on_bar repeatedly against one
        # long-lived DataFrame, so indicators accumulate naturally there -
        # but live rebuilds the frame from stored bars every tick, so
        # anything not persisted here is gone by the next tick. Storing
        # pre-on_bar meant recursive indicators (EMA/MACD reading df[i-1])
        # raised KeyError the moment they needed a previous value, and
        # window indicators (RSI/VWAP) silently went NaN and never traded.
        bars_by_ticker[ticker] = records_to_native(df.to_dict(orient="records"))

        # Persist the current active bar to MongoDB so backfills are self-sustaining
        if provider.name != "dummy" and db is not None:
            try:
                latest_bar = bars_by_ticker[ticker][-1]
                sess_interval = session.get("interval", "day")
                db[Config.COLLECTION_HISTORICAL].update_one(
                    {
                        "scripName": ticker,
                        "interval": sess_interval,
                        "priceDate": latest_bar["priceDate"],
                    },
                    {
                        "$set": {
                            "scripName": ticker,
                            "interval": sess_interval,
                            "priceDate": latest_bar["priceDate"],
                            "Value": latest_bar["Value"],
                            "Volume": latest_bar.get("Volume", 0),
                            "Open": latest_bar["Open"],
                            "High": latest_bar["High"],
                            "Low": latest_bar["Low"],
                        }
                    },
                    upsert=True
                )
            except Exception:
                logger.exception("Failed to persist live bar to MongoDB for %s", ticker)

        strategy_state[ticker] = {
            k: to_native(v) for k, v in vars(strategy).items() if k not in ("broker", "position_sizer")
        }

    new_trades = broker.history[trades_before:]
    for t in new_trades:
        if t.get("type") == "SELL" and "pnl" in t:
            session["daily_realized_pnl"] = session.get("daily_realized_pnl", 0.0) + t["pnl"]
        # Every fill gets a line - this is the audit trail for "why did it
        # buy that?" and, in live mode, for real money moving.
        logger.info(
            "TRADE %s %s %s x%s @ %.2f%s | session=%s strategy=%s",
            session["mode"].upper(), t.get("type"), t.get("symbol"), t.get("qty"),
            t.get("price", 0),
            f" pnl={t['pnl']:+.2f}" if t.get("pnl") is not None else "",
            session["_id"], session["strategy"],
        )

    session["bars"] = bars_by_ticker
    session["last_prices"] = last_prices
    # position_sizer is rebuilt from session["position_sizing"] every tick
    # (not BSON-serializable, and it's config, not evolving strategy state).
    session["strategy_state"] = strategy_state
    session["cash"] = broker.capital
    session["positions"] = broker.positions
    session["history"] = broker.history
    session["realized_pnl"] = broker.realized_pnl
    session["total_taxes"] = broker.total_taxes
    session["tick_count"] = session.get("tick_count", 0) + 1

    # One portfolio-equity point per tick, so the UI can chart equity over
    # time the same way a backtest's equity_curve does - a live session
    # only ever exposed the *current* equity before this, nothing historical.
    open_value = sum(pos["qty"] * last_prices.get(sym, pos["avg_price"]) for sym, pos in broker.positions.items())
    equity_curve = session.setdefault("equity_curve", [])
    equity_curve.append({
        "time": pd.Timestamp.now(tz="Asia/Kolkata").isoformat(),
        "equity": round(broker.capital + open_value, 2),
        # Matches BacktestRunner's own equity_curve convention: one blended
        # "current price" per point, taken from whichever ticker ticked
        # last this cycle - meaningful for a single-ticker session, a loose
        # approximation for a portfolio one (same tradeoff backtests already make).
        "price": last_prices.get(tickers[-1]) if tickers else None,
    })

    logger.debug(
        "Tick #%s session=%s mode=%s source=%s tickers=%s priced=%s equity=%.2f new_trades=%s",
        session["tick_count"], session["_id"], session["mode"], provider.name,
        len(tickers), len(last_prices), broker.capital + open_value, len(new_trades),
    )

    breached, reason = risk.check_daily_loss_limit(session)
    if not breached:
        breached, reason = risk.check_capital_exhausted(session)
    if breached:
        session["status"] = "halted"
        session["halt_reason"] = reason
        logger.warning("Session %s HALTED: %s", session["_id"], reason)

    return session


def summarize_session(session):
    """Derived, display-ready fields on top of the raw persisted session doc."""
    last_prices = session.get("last_prices", {})
    positions = session.get("positions", {})
    open_value = sum(pos["qty"] * last_prices.get(sym, pos["avg_price"]) for sym, pos in positions.items())
    open_cost = sum(pos["qty"] * pos["avg_price"] for pos in positions.values())
    equity = session.get("cash", 0) + open_value
    roi = ((equity - session["capital"]) / session["capital"] * 100) if session["capital"] else 0

    # Per-ticker breakdown, mirroring BacktestRunner._finalize's ticker_stats -
    # lets the UI drill into one ticker's position/trades within the portfolio.
    tickers = session.get("tickers") or ([session["ticker"]] if "ticker" in session else [])
    ticker_stats = {}
    for ticker in tickers:
        sym_trades = [t for t in session.get("history", []) if t.get("symbol") == ticker]
        sym_sells = [t for t in sym_trades if t.get("type") == "SELL"]
        sym_wins = [t for t in sym_sells if t.get("pnl", 0) > 0]
        sym_realized_pnl = sum(t.get("pnl", 0) for t in sym_sells)
        sym_win_rate = (len(sym_wins) / len(sym_sells) * 100) if sym_sells else 0

        pos = positions.get(ticker)
        sym_last_price = last_prices.get(ticker)
        sym_open_value = pos["qty"] * (sym_last_price if sym_last_price is not None else pos["avg_price"]) if pos else 0
        sym_open_cost = pos["qty"] * pos["avg_price"] if pos else 0

        # {time, price} series for this ticker's own price chart - same
        # shape as BacktestRunner._finalize's per-ticker "prices" list, so
        # the frontend's EquityChart component works unmodified here too.
        sym_prices = [{"time": b["priceDate"], "price": b["Value"]} for b in session.get("bars", {}).get(ticker, [])]

        ticker_stats[ticker] = {
            "last_price": sym_last_price,
            "position_qty": pos["qty"] if pos else 0,
            "avg_price": pos["avg_price"] if pos else None,
            "trades_count": len(sym_trades),
            "realized_pnl": round(sym_realized_pnl, 2),
            "unrealized_pnl": round(sym_open_value - sym_open_cost, 2),
            "win_rate": round(sym_win_rate, 2),
            "prices": sym_prices,
        }

    summary = {
        **session,
        "open_position_value": round(open_value, 2),
        "unrealized_pnl": round(open_value - open_cost, 2),
        "equity": round(equity, 2),
        "roi": round(roi, 2),
        "ticker_stats": ticker_stats,
        # EquityChart reads `results.trades` - live sessions call the same
        # data `history`, so alias it rather than touch the shared component.
        "trades": session.get("history", []),
    }
    # `bars` is the engine's own working state (raw OHLCV + indicator
    # columns, up to MAX_BARS per ticker) and nothing in the UI reads it -
    # the chart uses ticker_stats[...]["prices"] instead. Shipping it would
    # put megabytes on the wire every 5 seconds, since the frontend polls
    # this endpoint for every session.
    summary.pop("bars", None)
    summary.pop("strategy_state", None)
    return summary


def _square_off_if_needed(db, session, kite):
    """
    Close any open position on an intraday session once the market has
    closed. `day`-interval sessions are left alone deliberately - those are
    the swing/delivery case (CNC), where holding overnight is the point.

    Returns True if anything was closed.
    """
    if session.get("interval", "day") == "day":
        return False
    positions = session.get("positions") or {}
    if not positions:
        return False

    broker = _hydrate_broker(session, kite)
    last_prices = session.get("last_prices", {})
    closed = 0

    for symbol, pos in list(positions.items()):
        qty = pos.get("qty", 0)
        price = last_prices.get(symbol) or pos.get("avg_price")
        if not qty or not price:
            continue
        # Long -> sell, short -> buy to cover.
        side = "SELL" if qty > 0 else "BUY"
        if broker.place_order(side, symbol, price, abs(qty), pd.Timestamp.now(tz="Asia/Kolkata").isoformat(), is_intraday=True):
            closed += 1
            logger.info(
                "SQUARE-OFF %s %s %s x%s @ %.2f | session=%s (market closed)",
                session["mode"].upper(), side, symbol, abs(qty), price, session["_id"],
            )

    if not closed:
        return False

    session["cash"] = broker.capital
    session["positions"] = broker.positions
    session["history"] = broker.history
    session["realized_pnl"] = broker.realized_pnl
    session["total_taxes"] = broker.total_taxes
    store.save_session(db, session)
    logger.info("Session %s squared off %s position(s) at market close", session["_id"], closed)
    return True


def _tick_all_sessions():
    db = get_db()
    if db is None:
        logger.warning("Tick cycle skipped - MongoDB unavailable")
        return

    kite = get_kite()
    ignore_hours = Config.LIVE_IGNORE_MARKET_HOURS

    active_symbols = set()
    running = store.list_sessions(db, status="running")
    ticked = skipped_closed = failed = squared_off = 0

    for session in running:
        uses_real_feed = session["mode"] == "live" or kite is not None
        if uses_real_feed and not ignore_hours and not is_market_open():
            # Square off BEFORE skipping. An intraday session that still
            # holds a position when the market closes would otherwise just
            # stop ticking and carry it overnight - which for a real MIS
            # position means the broker force-closes it at its own price,
            # outside anything this engine models.
            if _square_off_if_needed(db, session, kite):
                squared_off += 1
            skipped_closed += 1
            continue

        active_symbols.update(session.get("tickers") or ([session["ticker"]] if "ticker" in session else []))

        try:
            session = run_tick(db, session, kite)
            store.save_session(db, session)
            ticked += 1
        except Exception:
            failed += 1
            logger.exception("Tick failed for session %s", session.get("_id"))

    if running:
        # One line per cycle at INFO so "is it actually doing anything?" is
        # answerable from the log alone, without turning on DEBUG.
        logger.info(
            "Tick cycle: %s running | ticked=%s skipped_market_closed=%s squared_off=%s failed=%s | symbols=%s kite=%s",
            len(running), ticked, skipped_closed, squared_off, failed, len(active_symbols),
            "connected" if kite else "disconnected",
        )

    # Keep the WebSocket subscribed to all currently active symbols
    if active_symbols:
        from app.live.ticker import subscribe_symbols
        subscribe_symbols(list(active_symbols))


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

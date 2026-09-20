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
from app.engine.position_sizing import build_sizer
from app.live.broker import PaperBroker, KiteLiveBroker
from app.live import store, risk
from app.live.market_hours import is_market_open
from app.utils.serialization import records_to_native, to_native

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


def _resample_bars(bars, ticker, interval):
    """Same OHLCV resample BacktestRunner-adjacent code uses elsewhere -
    turns raw per-tick bars into interval-sized bars for a single ticker."""
    df = pd.DataFrame(bars)
    if df.empty or interval == "day":
        return df

    # pandas dropped the "T" minute alias in favor of "min" (this broke
    # silently after a pandas upgrade - every intraday interval resample
    # was raising until this was caught).
    freq_map = {"minute": "1min", "3minute": "3min", "5minute": "5min", "10minute": "10min", "15minute": "15min", "30minute": "30min", "60minute": "60min"}
    freq = freq_map.get(interval)
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
    df = df.resample(freq).agg({
        "scripName": "first",
        "Value": "last",
        "Volume": "sum",
        "Open": "first",
        "High": "max",
        "Low": "min"
    }).dropna().reset_index()
    df["priceDate"] = df["priceDate"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df


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

    tickers = session.get("tickers") or ([session["ticker"]] if "ticker" in session else [])
    bars_by_ticker = session.setdefault("bars", {t: [] for t in tickers})
    last_prices = session.setdefault("last_prices", {})

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
            "priceDate": pd.Timestamp.now("UTC").isoformat(),
            "Value": price,
            "Volume": 0,
            "Open": price,
            "High": price,
            "Low": price,
        })

        df = _resample_bars(ticker_bars, ticker, session.get("interval", "day"))
        dfs_by_ticker[ticker] = df
        bars_by_ticker[ticker] = records_to_native(df.to_dict(orient="records"))
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

        strategy_state[ticker] = {
            k: to_native(v) for k, v in vars(strategy).items() if k not in ("broker", "position_sizer")
        }

    new_trades = broker.history[trades_before:]
    for t in new_trades:
        if t.get("type") == "SELL" and "pnl" in t:
            session["daily_realized_pnl"] = session.get("daily_realized_pnl", 0.0) + t["pnl"]

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
        "time": pd.Timestamp.now("UTC").isoformat(),
        "equity": round(broker.capital + open_value, 2),
        # Matches BacktestRunner's own equity_curve convention: one blended
        # "current price" per point, taken from whichever ticker ticked
        # last this cycle - meaningful for a single-ticker session, a loose
        # approximation for a portfolio one (same tradeoff backtests already make).
        "price": last_prices.get(tickers[-1]) if tickers else None,
    })

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

    return {
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


def _tick_all_sessions():
    db = get_db()
    if db is None:
        return

    kite = get_kite()
    ignore_hours = Config.LIVE_IGNORE_MARKET_HOURS
    
    active_symbols = set()

    for session in store.list_sessions(db, status="running"):
        uses_real_feed = session["mode"] == "live" or kite is not None
        if uses_real_feed and not ignore_hours and not is_market_open():
            continue
            
        active_symbols.update(session.get("tickers") or ([session["ticker"]] if "ticker" in session else []))
        
        try:
            session = run_tick(db, session, kite)
            store.save_session(db, session)
        except Exception:
            logger.exception("Tick failed for session %s", session.get("_id"))
            
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

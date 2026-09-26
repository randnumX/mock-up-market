---
description: Provides the current architectural context and overview of the automated trading engine.
---
# Project Context: Mock-Up Market (Automated Trading Engine)

An automated algorithmic trading engine for the Indian stock market (NSE) with multi-ticker/intraday backtesting, tax-aware profit calculation (incl. shorts), real market data + a live WebSocket feed via Zerodha Kite Connect, unattended live trading, a signal scanner, and a premium real-time dashboard.

## Current Architecture (v3.0)

### Backend (`backend/`)
Flask REST API with Blueprints pattern. Dependencies managed with `uv` (`pyproject.toml` + committed `uv.lock` — no `requirements.txt`, no manual venv activation; `uv run <cmd>` / `uv sync` everywhere).

- **Entry Point**: `run.py` → loads `.env` via `python-dotenv`, creates Flask app via factory. On boot, `app/__init__.py` starts three background services (live scheduler, WebSocket ticker thread, scanner scheduler), each guarded against Flask's debug-reloader double-start via `WERKZEUG_RUN_MAIN`
- **Logging**: `app/logging_config.py` — `setup_logging()` (called first thing in `create_app`) attaches a rotating file handler (`LOG_DIR`, default `backend/logs/`, 10MB × 5) plus a stdout handler to the `mockupmarket` logger tree; modules call `get_logger("live.engine")` etc. rather than `logging.getLogger` directly so everything shares one configurable parent and app logs stay separable from library noise. **There was no logging config at all before this** — every logger fell through to Python's last-resort WARNING-to-stderr handler with nothing on disk, which is how a strategy crashing on literally every tick went unnoticed for a whole trading session
- **Config**: `app/config.py` — reads all settings from environment variables, incl. `KITE_ALLOW` (master kill-switch: gates all real Kite/WebSocket usage regardless of whether credentials are present) and `LIVE_POLL_INTERVAL_SECONDS`/`LIVE_IGNORE_MARKET_HOURS`
- **API Routes** (`app/routes/`):
  - `health.py` — `GET /api/health` (per-provider availability, version)
  - `tickers.py` — `GET /api/tickers` (merged across providers, resolves company names via Kite's instrument dump when connected); `GET /api/tickers/<symbol>/history` (up to 300 recent bars for the ticker detail modal)
  - `backtest.py` — `POST /api/backtest` / `GET /api/backtest/stream` (SSE): accepts a comma-separated `ticker` string or `tickers` array (multi-ticker portfolio backtests), `interval`, `position_sizing`, `max_capital_per_trade`, `daily_loss_limit`, `from_date`/`to_date`. `_prepare_run()` fetches every ticker's history in parallel (`ThreadPoolExecutor`) and loads them all into one `BacktestRunner`. Validation order matters: tickers/strategy → dates → capital, so a malformed-date request is rejected as a date error even without `capital` set. `GET /api/strategies`; `GET /api/position-sizing-modes`
  - `kite.py` — `/api/kite/*` (login-url, callback, status, disconnect, sync — sync runs in a background thread, progress broadcast over `/api/stream`)
  - `live.py` — `/api/live/*` (create/list/get/stop/**delete** session — delete requires the session to already be stopped/halted; kill-all; market-status)
  - `stream.py` — `GET /api/stream`: shared SSE endpoint (queue-per-client pub/sub) carrying both live WebSocket price ticks and Kite-sync progress events
  - `scanner.py` — `GET`/`POST /api/scanner`: configure/read the background signal scanner
  - `movers.py` — `GET /api/movers`: top gainers/losers/volume, computed from the two most recent daily-interval dates in Mongo
- **Engine** (`app/engine/`):
  - `strategy.py` — Base event-driven strategy class; `__init__(self, broker, position_sizer=None)` stores a `PositionSizer` (defaults to `FullCapitalSizer`), and `quantity_for(price, df, i)` is what subclasses call instead of computing share count inline
  - `macd.py`, `rsi.py`, `sma_crossover.py`, `bollinger.py`, `vwap.py`, `orb.py`, `rsi_scalp.py`, `ema_scalp.py` — eight pluggable strategy implementations, all registered in `registry.py`'s `STRATEGIES`/`STRATEGY_META`, all forward `position_sizer` to `super().__init__()`. `ORBStrategy` explicitly opens shorts on a breakdown below the opening range and covers them later — this only works because of the broker-level short support below
  - `position_sizing.py` — pluggable position sizing: `FullCapitalSizer` (default), `FixedFractionSizer(fraction)`, `VolatilityTargetSizer(risk_per_trade, lookback)`; `build_sizer(config)` constructs one from a `{"mode": ..., ...params}` dict, used identically by the backtest route and the live engine
  - `backtester.py` — `BacktestRunner(broker, strategy_class, position_sizer=None, daily_loss_limit=None)`. Takes a strategy **class**, not an instance — it instantiates one strategy per ticker internally (`_build_timeline`). `load_data(ticker, df)` is keyed by ticker; `_build_timeline()` merges every loaded ticker's bars into one chronological event list so a portfolio backtest processes cross-ticker signals in true time order. `_step()` implements the daily-loss circuit breaker via `start_of_day_equity` tracking. `_finalize()` builds both the portfolio-level result and a per-ticker `ticker_stats` breakdown (trade count, win rate, realized P&L, price series)
  - `broker.py` — `SimulatedBroker`: tax-aware trade execution, an optional `max_capital_per_trade` clamp on BUY orders, and **short-selling**: a `SELL` with no existing long position opens/grows a short (`_open_or_add_short`), and a subsequent `BUY` covers it tax-aware (`_cover_short`) via the same order-agnostic `calculate_taxes()`. `get_portfolio_value`/`_finalize`'s unrealized-PnL math work unmodified for negative (short) quantities
- **Utils** (`app/utils/`):
  - `taxes.py` — Indian equity tax calculator (STT, GST, SEBI, Stamp Duty); `calculate_taxes(buy_price, sell_price, quantity)` is order-agnostic, so it's reused as-is for covering a short (buy leg happens after the sell leg)
  - `dummy_data.py` — Generates realistic synthetic stock data via Geometric Brownian Motion
- **Data** (`app/data/`):
  - `db.py` — MongoDB connection helper with graceful fallback
  - `kite_client.py` — Kite Connect session lifecycle; `is_configured()` checks `KITE_ALLOW` first (kill-switch), then credentials
  - `kite_ingest.py` — Resolves NSE instrument tokens, fetches/upserts historical OHLCV candles (real Open/High/Low, not just close) into Mongo per ticker+interval, with "smart sync" (only fetches forward from the last stored date) and Kite's intraday history caps (100 days most intervals, 60 for `minute`)
  - `scripts/fetch_bse_data.py` — Alternative data loader with no broker account needed: pulls daily history from BSE's undocumented `StockReachGraph` endpoint for every ticker in `backend/Equity.csv`. Resumable. `flag=12M` enforced as the max
  - `providers/` — **the plug-and-switch data-source abstraction.** `base.py` defines `DataProvider` (`is_available`, `get_tickers`, `get_history(ticker, days, from_date, to_date, interval="day")`, `get_latest_price`) — **every provider must accept `interval`**, even `DummyProvider` (accepted, ignored — synthetic data is always daily). `kite_provider.py`, `mongo_provider.py`, `dummy_provider.py` implement it; `registry.py` builds the provider list and exposes `get_history_with_fallback()` / `get_provider()`, calling every provider's `get_history` with the same signature (no duck-typing/`inspect.signature` workaround — removed once all three providers matched the interface). `priceDate` is `"YYYY-MM-DD"` for daily bars, `"YYYY-MM-DD HH:MM:SS"` for intraday, consistently across ingest and every provider. `KiteProvider.get_history` returns real Open/High/Low (needed by VWAP/ORB) and honors `interval`, mirroring `kite_ingest`'s caps
- **Live Trading** (`app/live/`):
  - `broker.py` — `PaperBroker` (subclasses `SimulatedBroker` directly — virtual money, gets short-selling for free) and `KiteLiveBroker` (real orders via Kite's Order API, deliberately long-only: a SELL is clamped to existing position size, so a strategy's short signal safely no-ops in live mode instead of risking an unmodeled real short)
  - `engine.py` — `run_tick()` advances one session by one price tick; resamples ticks into OHLCV bars via pandas when `session["interval"] != "day"`. `start_scheduler()` runs an APScheduler job every `LIVE_POLL_INTERVAL_SECONDS` for every `status="running"` session; `_tick_all_sessions()` also subscribes the WebSocket ticker to every active session's symbol
  - `ticker.py` — background thread wrapping Kite's `KiteTicker` WebSocket (only runs when `is_configured()` and `KITE_ALLOW`); maintains an in-memory `PRICE_CACHE`, broadcasts ticks over the shared SSE pub/sub (`_clients`/`_broadcast`) also used for Kite-sync progress. `KiteProvider.get_latest_price` checks this cache before falling back to a Kite LTP REST call
  - `scanner.py` — separate `BackgroundScheduler` running a chosen strategy over a watchlist via a broker that never places real orders, purely to surface BUY signals (`routes/scanner.py`)
  - **Indicator columns are persisted with the bars.** `run_tick` snapshots `df` into `session["bars"]` *after* `on_bar`, not before: a backtest calls `on_bar` repeatedly against one long-lived DataFrame so indicators accumulate naturally, but live rebuilds the frame from stored bars each tick. Storing pre-`on_bar` meant recursive indicators (EMA/MACD, which read `df[i-1]`) raised `KeyError` as soon as they needed a previous value, and window indicators (RSI/VWAP) silently went NaN and never traded. `_resample_bars` likewise carries unknown (indicator) columns through its `agg` with `"last"`, and uses `dropna(subset=["Value"])` so warm-up NaNs don't delete whole rows
  - `store.py` — Mongo CRUD for the `LiveSessions` collection; `create_session(...)` takes `interval`; `delete_session(...)` permanently removes a session document (routes enforce it's already stopped/halted first — `stop_session`/`stop_all_sessions` only ever flip a status flag, they never delete)
  - `risk.py` — pure, DB-free risk checks the engine consults every tick
  - `market_hours.py` / `nse_holidays.py` — NSE hours + published-holiday gate, only enforced once a real Kite price feed is involved

### Frontend (`frontend/`)
Vite + React single-page application. View switcher: Backtest / Live Trading / Scanner / Movers, plus a global `TickerModal`.

- **Components**: `ConfigPanel` (multi-ticker free-text input, interval/position-sizing/risk-cap controls), `KiteConnect` (live sync log over SSE), `MetricsGrid`/`EquityChart`/`TradeLog` (all `drilldownTicker`-aware, switching between portfolio and single-ticker views), `LiveTrading`/`LiveSessionForm`/`LiveSessionsList`, `Scanner`, `Movers`, `TickerModal`, `ThemeToggle`
- **Hooks**: `useBacktest` (owns `resultsList` — every run's result *and* the `config` used to produce it, persisted to `localStorage`; `deleteResult`/`clearArchivedResults`; reconciles any `status: 'streaming'` entry found on load to an error state, since its `EventSource` doesn't survive a refresh), `useLive` (incl. `deleteSession`), `useTickers`, `useHealth`, `useStrategies`, `usePositionSizingModes`, `useKite`, `useTheme`
- **Design**: Light/dark toggle theme (4-color palette, `frontend/src/index.css` `:root` + `[data-theme="dark"]`), Inter font, CSS custom properties. `--positive`/`--negative` are true green/red, `--accent`/`--brand-blue` distinct from both
- **Dev Server**: Port 5173 with Vite proxy to Flask backend on port 5000

### Key Design Decisions
- **Zero-setup demo**: App works fully without MongoDB or a broker account using generated dummy data
- **Data source is dependency-injected**: `routes/*.py` depend only on the `DataProvider` interface via `providers/registry.py`
- **Tax-aware, both directions**: every simulated fill (long or short) deducts realistic Indian equity taxes
- **Event-driven strategy, class not instance**: `BacktestRunner` takes a strategy class and instantiates one per ticker, so the same run can process N tickers with independent strategy state
- **Config travels with the result**: a backtest run's frontend record stores the settings that produced it, not just the output, so past runs stay interpretable without re-deriving what was asked for
- **Real-money safety over feature completeness**: `KiteLiveBroker` stays long-only on purpose even though the simulated/paper broker supports shorting — an unmodeled real short is a bigger risk than a strategy's short signal silently no-op'ing live
- **Tested**: `backend/tests/` (pytest, run via `uv run pytest`) covers taxes, broker (incl. shorting), all eight strategies end-to-end, the multi-ticker backtester, streaming, date-range validation, provider availability/fallback, and the live engine/store

### Deployment
- `docker-compose.yml` — three coexisting modes via profiles: no profile starts only `mongo`; `profiles: ["full"]` (`backend`/`frontend`, ports 3000/5000) is a production-shaped build (gunicorn + nginx-static, no hot reload); `profiles: ["dev"]` (`backend-dev`/`frontend-dev`, ports 3001/5001) bind-mounts source for hot reload. **Warning**: `docker compose --profile <name> down -v` removes ALL volumes regardless of profile, including `mongo_data` — not profile-scoped, confirmed the hard way once already.
- `backend/Dockerfile` — multi-stage `uv` build (builder stage has `uv` + build tools, `uv sync --locked`; final stage copies only the synced `.venv` + app code). Runs `gunicorn --workers 1 --threads 4` — the single-worker count is load-bearing: `app/live/engine.py`'s scheduler is an in-process singleton, and >1 worker would multiply every live session's trades. `backend-dev` uses the combined `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` image (`uv sync && uv run python run.py`, no custom Dockerfile) with a named `backend_venv_dev` volume so the container's Linux-built venv never collides with a host macOS venv
- `frontend/Dockerfile` — multi-stage (Vite build → nginx); `frontend/nginx.conf` proxies `/api/*` with `proxy_buffering off` so SSE streams (`/api/backtest/stream`, `/api/stream`) actually stream through
- `scripts/setup.sh` — checks for `uv` as a hard prerequisite (alongside python3/node), runs `uv sync --locked` for the backend (no manual venv step)

### Legacy Code
`AlgoTrading/` (original scripts) and `api/` (original Flask stub) have been removed — both were explicitly superseded by `backend/`. If reference material from them is ever needed again, it's recoverable from git history prior to their removal.

### Known Gaps (as of this writing)
- `backend/app/routes/tickers.py`'s `/api/tickers/<symbol>/history` synthesizes O=H=L=C from a single `Value` field when the underlying data doesn't have real OHLC — a stopgap flagged inline in the route.
- Live-session bars are stored post-resample for intraday intervals (`MAX_BARS=600` in `store.py` bounds resampled, not raw-tick, bars) — a thin lookback window (~2 trading days) for `minute`-interval sessions relative to what a strategy like SMA-50 might want.
- Interval-resampling logic (pandas `.resample().agg()` + a `freq_map`) is duplicated between `live/engine.py` and `live/scanner.py`, using deprecated `1T`/`3T`-style pandas frequency aliases (works today, forward-compat wart).
- Archived backtest run history is client-side (`localStorage`) only — no server-side persistence, so it doesn't sync across devices/browsers.

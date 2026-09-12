---
description: Provides the current architectural context and overview of the automated trading engine.
---
# Project Context: Mock-Up Market (Automated Trading Engine)

An automated algorithmic trading engine for the Indian stock market (NSE) with backtesting, tax-aware profit calculation, real market data via Zerodha Kite Connect, and a premium real-time dashboard.

## Current Architecture (v2.1)

### Backend (`backend/`)
Flask REST API with Blueprints pattern.

- **Entry Point**: `run.py` → loads `.env` via `python-dotenv`, creates Flask app via factory
- **Config**: `app/config.py` — reads all settings from environment variables (incl. Kite Connect credentials)
- **API Routes** (`app/routes/`):
  - `health.py` — `GET /api/health` (per-provider availability, version)
  - `tickers.py` — `GET /api/tickers` (tickers merged across all available providers)
  - `backtest.py` — `POST /api/backtest` (runs engine, returns JSON results) and `GET /api/backtest/stream` (SSE version); both accept optional `from_date`/`to_date` (ISO, inclusive) to restrict the backtest window, validated in `_prepare_run()`; `GET /api/strategies`
  - `kite.py` — `/api/kite/*` (login-url, callback, status, disconnect, sync)
  - `live.py` — `/api/live/*` (create/list/get/stop session, kill-all, market-status)
- **Engine** (`app/engine/`):
  - `strategy.py` — Base event-driven strategy class
  - `macd.py`, `rsi.py`, `sma_crossover.py`, `bollinger.py` — four pluggable strategy implementations, all registered in `routes/backtest.py`'s `STRATEGIES` dict
  - `backtester.py` — BacktestRunner with equity curve, max drawdown, win rate
  - `broker.py` — SimulatedBroker with tax-aware trade execution
- **Utils** (`app/utils/`):
  - `taxes.py` — Indian equity tax calculator (STT, GST, SEBI, Stamp Duty)
  - `dummy_data.py` — Generates realistic synthetic stock data via Geometric Brownian Motion
- **Data** (`app/data/`):
  - `db.py` — MongoDB connection helper with graceful fallback
  - `kite_client.py` — Kite Connect session lifecycle (login URL, token exchange, daily session persisted to `backend/.kite_session.json`, gitignored)
  - `kite_ingest.py` — Resolves NSE instrument tokens and fetches/upserts historical candles into Mongo
  - `scripts/fetch_bse_data.py` — Alternative data loader with no broker account needed: pulls daily history from BSE's undocumented `StockReachGraph` endpoint for every ticker in `backend/Equity.csv` (the official active-equity list). Resumable (skips already-loaded tickers). `flag=12M` is enforced as the max - BSE silently returns intraday ticks instead of more history above that, confirmed by direct testing (see the script's docstring)
  - `providers/` — **the plug-and-switch data-source abstraction.** `base.py` defines `DataProvider` (`is_available`, `get_tickers`, `get_history` [accepts `from_date`/`to_date` ISO strings to restrict the range, in addition to `days`], `get_latest_price`); `kite_provider.py`, `mongo_provider.py`, `dummy_provider.py` implement it; `registry.py` builds the provider list and exposes `get_history_with_fallback()` / `get_provider()`. **Routes never import Mongo or Kite directly** — only the registry. Adding a new data source means writing one `DataProvider` subclass and adding it to `build_providers()`. `priceDate` is stored/returned as an ISO `"YYYY-MM-DD"` string by every provider (never a datetime object) so date-range filtering is a plain lexicographic comparison everywhere, including in Mongo queries.
- **Live Trading** (`app/live/`):
  - `broker.py` — `PaperBroker` (subclasses `SimulatedBroker`, virtual money) and `KiteLiveBroker` (real orders via Kite's Order API); both share the same `place_order(...)` signature the `Strategy` classes already call, and both accept an optional `max_capital_per_trade` cap
  - `engine.py` — `run_tick()` advances one session by one price tick (fetch latest price → append to persisted bar history → `strategy.on_bar()` → persist); `start_scheduler()` runs an APScheduler job every `LIVE_POLL_INTERVAL_SECONDS` calling this for every `status="running"` session. Strategy indicator state (EMA/RSI/SMA/Bollinger columns, and flags like `bought`) round-trips through Mongo every tick so a session resumes correctly after a restart
  - `store.py` — Mongo CRUD for the `LiveSessions` collection (session state must survive restarts - this is why live trading has no dummy-data-only mode, unlike backtesting)
  - `risk.py` — pure, DB-free risk checks (`check_daily_loss_limit`, `check_capital_exhausted`, `rollover_daily_pnl`) the engine consults every tick
  - `market_hours.py` — NSE hours gate (9:15-15:30 IST, Mon-Fri); only enforced once a real Kite price feed is involved, so a paper session on the simulated feed can demo continuously

### Frontend (`frontend/`)
Vite + React single-page application.

- **Components**: Header, StatusBadge, ConfigPanel, KiteConnect, MetricsGrid, EquityChart (TradingView lightweight-charts), TradeLog
- **Hooks**: `useBacktest`, `useTickers`, `useHealth`, `useStrategies`, `useKite`
- **Design**: Premium dark mode with glassmorphism, Inter font, CSS custom properties
- **Dev Server**: Port 5173 with Vite proxy to Flask backend on port 5000

### Key Design Decisions
- **Zero-setup demo**: App works fully without MongoDB or a broker account using generated dummy data
- **Data source is dependency-injected**: `routes/*.py` depend only on the `DataProvider` interface via `providers/registry.py`; Kite Connect was added as a new provider alongside Mongo/dummy, not a replacement or special-cased branch
- **Tax-aware**: Every simulated sell deducts realistic Indian equity taxes
- **TradingView charts**: Professional-grade financial charts via `lightweight-charts`
- **Event-driven strategy**: Base `Strategy` class allows pluggable algorithms; four are currently registered (MACD, RSI, SMA Crossover, Bollinger Bands)
- **Tested**: `backend/tests/` (pytest) covers taxes, broker, all four strategies end-to-end, and provider availability/fallback behavior

### Legacy Code
`AlgoTrading/` (original scripts) and `api/` (original Flask stub) have been removed — both were explicitly superseded by `backend/` and fully duplicated by `app/engine/` + the providers layer. If reference material from them is ever needed again, it's recoverable from git history prior to their removal.

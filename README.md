# 📈 Mock-Up Market

A production-grade algorithmic trading engine for the Indian stock market (NSE) with backtesting, tax-aware profit calculation, real market data via Zerodha Kite Connect, and a premium real-time dashboard.

## Features

- **Eight Pluggable Strategies** — MACD Crossover, RSI Mean Reversion, SMA Crossover, Bollinger Bands, VWAP, Opening Range Breakout (ORB), RSI Scalp, EMA Scalp, all built on one event-driven `Strategy` base class
- **Multi-Ticker Portfolio Backtests** — run a strategy across any number of tickers at once; results include a merged portfolio equity curve plus a per-ticker breakdown for drill-down charts
- **Intraday Intervals** — backtest and live-trade on `day` or intraday bars (`minute` through `60minute`), not just daily closes
- **Tax-Aware Backtesting** — Calculates Brokerage, STT, GST, SEBI charges, Stamp Duty for accurate net PnL, including on short positions (see [Short Selling](#short-selling))
- **TradingView Charts** — Professional-grade equity curves and price charts with trade signal markers
- **Pluggable Data Providers** — Zerodha Kite Connect (real, live), MongoDB (previously-synced), and a synthetic generator all implement the same `DataProvider` interface and are swapped in/out with zero route changes — see [Data Providers](#data-providers)
- **Zero-Setup Demo** — Works instantly with generated dummy data (no MongoDB or broker account required)
- **Connect Zerodha** — One click in the dashboard to log in via Kite Connect and sync real NSE history into MongoDB, with a live progress log over SSE
- **Live WebSocket Ticker** — a background thread wraps Kite's `KiteTicker` WebSocket for near-zero-latency prices, pushed to the frontend and to the live trading engine over the same SSE stream used for Kite-sync progress
- **Live Trading Engine** — Run any strategy unattended against live prices in Paper mode (virtual money) or Live mode (real Zerodha orders), with per-trade capital caps, a daily loss limit, and a kill switch — see [Live Trading](#live-trading)
- **Signal Scanner** — runs strategies over a watchlist in the background and surfaces BUY signals without opening a real trading session
- **Market Movers** — top gainers/losers/volume from the most recently synced trading day, computed straight from MongoDB
- **Archived Run History** — every backtest run (its result *and* the configuration used to produce it — capital, date range, interval, position sizing, risk caps) persists client-side across page reloads, with per-run and bulk delete

## Quick Start

**Prerequisites**: Python 3.12+, Node.js 20+, and [uv](https://docs.astral.sh/uv/getting-started/installation/) (required — `scripts/setup.sh` checks for it). Docker is optional but recommended (unlocks MongoDB, real ticker sync, and Live Trading — the app runs fully without it too, on synthetic data).

```bash
./scripts/setup.sh
```

Safe to re-run any time — every step skips or no-ops if it's already done, so it doubles as a "did I set everything up right?" check. It checks your prerequisites, creates `backend/.env` from `.env.example` if missing, syncs backend dependencies via `uv sync` (creates/updates `backend/.venv` automatically, no manual venv step), installs frontend dependencies, and (if Docker is available) starts MongoDB.

Then start the app:

```bash
# Terminal 1
cd backend && uv run python run.py

# Terminal 2
cd frontend && npm run dev
```

Open **http://localhost:5173** in your browser. (Or skip both terminals and run everything containerized — see [Full Docker Deployment](#full-docker-deployment-backend--frontend--mongo) below.)

## Local MongoDB (optional, required for Live Trading)

`scripts/setup.sh` already does this for you if Docker is installed. To manage it manually:

```bash
docker compose up -d      # starts MongoDB in the background
docker compose down       # stops it (add -v to also wipe stored data)
```

`backend/.env` already points at it (`MONGO_URI=mongodb://localhost:27017`) — no other config needed. Check `GET /api/health` for `"db_connected": true` once it's up.

## Full Docker Deployment (backend + frontend + Mongo)

To run the *entire* app containerized instead of `python run.py` / `npm run dev` natively, use the `full` profile — this builds a production image for each service (backend served via gunicorn, frontend built and served via nginx with `/api/*` proxied to the backend, mirroring the Vite dev proxy) instead of touching your local Python/Node setup at all:

```bash
docker compose --profile full up --build -d
# Dashboard: http://localhost:3000   API: http://localhost:5000
docker compose --profile full down     # stop everything (add -v to also wipe Mongo data)
```

Plain `docker compose up -d` (no `--profile full`) still only starts Mongo, unchanged — the two modes coexist, pick whichever fits what you're doing.

Two things worth knowing about the containerized backend:
- It runs with `gunicorn --workers 1` **deliberately, not as an oversight** — the live-trading scheduler (`app/live/engine.py`) is an in-process singleton; more than one worker would each run their own copy and tick every live session multiple times. `--threads 4` still gives it request concurrency without that problem. Scale horizontally (multiple containers behind a load balancer) rather than via `--workers` if you need more throughput.
- Kite Connect credentials, if you have them, pass through via host environment variables (`KITE_API_KEY`, `KITE_API_SECRET`, etc. — see `docker-compose.yml`); nothing is baked into the image.

This mode has **no hot reload** — both images are built once (frontend to static files, backend to a fixed code snapshot), so a code change needs `--build` again to show up. It's meant for verifying the app works the way it'll actually be deployed, not as an edit-save-refresh loop. For that, use native `python run.py` / `npm run dev`, or the `dev` profile below if you want the containers themselves to reload.

## Docker Dev Mode (hot reload)

A third mode, for when you want containers but still want to edit-save-see-it-update: `backend-dev`/`frontend-dev` bind-mount your source straight into plain `python`/`node` images (no custom Dockerfile, no rebuild step) and run the same dev servers the native workflow uses — Flask's debug reloader and Vite's HMR both work exactly as they do natively, just inside containers.

```bash
docker compose --profile dev up --build -d
# Dashboard: http://localhost:3001   API: http://localhost:5001
docker compose --profile dev down
```

Different host ports (3001/5001) than the `full` profile (3000/5000) on purpose, so `dev` and `full` can even run side by side if you want to compare them. `frontend-dev`'s `node_modules` and `backend-dev`'s `.venv` each live in a named Docker volume, not your host filesystem — keeps container-installed (Linux) native deps from colliding with whatever's already in your host `frontend/node_modules` / `backend/.venv` if you also run things natively. `backend-dev` uses the combined `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` image so `uv sync && uv run python run.py` works with no custom Dockerfile or rebuild step.

> **Warning**: `docker compose --profile <name> down -v` removes **all** declared volumes, not just that profile's — including `mongo_data`. If you've bulk-loaded real ticker history, don't pass `-v` unless you specifically mean to wipe it.

## Real Market Data (Zerodha Kite Connect)

1. Create an app at [developers.kite.trade](https://developers.kite.trade/apps) (₹2000/month subscription). Set its **Redirect URL** to `http://localhost:5000/api/kite/callback`.
2. Copy the API key/secret into `backend/.env`:
   ```
   KITE_API_KEY=your_key
   KITE_API_SECRET=your_secret
   ```
3. Restart the backend, then click **Connect Zerodha** in the dashboard sidebar and log in.
4. Click **Sync Real Data** to pull ~2 years of daily NSE history for the default watchlist into MongoDB.

Without steps 1-2, the app runs exactly as before on MongoDB / synthetic data — nothing else changes.

For headless/cron use there are CLI equivalents: `python scripts/kite_login.py` and `python scripts/fetch_data.py`.

## Real Market Data (BSE, no broker account needed)

`backend/scripts/fetch_bse_data.py` pulls daily history straight from BSE's public (undocumented) `StockReachGraph` endpoint into MongoDB — no Kite subscription required. Ticker → BSE scrip code comes from `backend/Equity.csv` (the official active-equity list exported from [bseindia.com/corporates/List_Scrips.aspx](https://www.bseindia.com/corporates/List_Scrips.aspx), T+1 segment).

```bash
cd backend && python scripts/fetch_bse_data.py                # all ~5000 active equities, resumable
cd backend && python scripts/fetch_bse_data.py SBIN RELIANCE   # just these tickers
cd backend && python scripts/fetch_bse_data.py --limit 50      # first 50 only, for testing
cd backend && python scripts/fetch_bse_data.py --force         # re-fetch even already-loaded tickers
```

Interrupting and re-running is safe — it skips tickers already in Mongo unless `--force` is passed. **`flag=12M` (~1 year of daily bars) is the real ceiling for this endpoint** — anything above that (`24M`, `2Y`, `5Y`, ...) silently returns intraday minute ticks for *today* instead of more history, confirmed by direct testing; the script enforces this and refuses larger flags. For more than ~1 year of history, use the Kite Connect path above instead.

Caveat: this is an undocumented BSE endpoint accessed via a spoofed browser User-Agent - it works today but could change or be rate-limited/blocked without notice. Fine for local development and demos; prefer Kite Connect for anything long-term.

## Live Trading

The **Live Trading** tab runs the same `Strategy` classes used for backtesting against a live price feed, one tick at a time, on an in-process scheduler (polls every `LIVE_POLL_INTERVAL_SECONDS`, default 30s). Requires MongoDB — a session's whole point is to keep running unattended, so its state (cash, positions, trade history, rolling indicator bars) is persisted after every tick and survives a backend restart. Sessions can run on `day` or any intraday interval; intraday sessions resample incoming ticks into OHLCV bars on the fly.

Two modes, same strategy code, different `Broker`:
- **Paper** — virtual money. Uses live Kite prices (via the WebSocket ticker below, falling back to REST) if connected, otherwise a simulated price feed, so paper trading works with zero setup just like backtesting. Zero financial risk. Shares `SimulatedBroker`'s tax-aware fill logic with backtesting, including short-selling.
- **Live** — places real orders on your connected Zerodha account via `KiteLiveBroker`. Requires an active Kite connection, an explicit `confirm: true`, and a mandatory `max_capital_per_trade` cap. Real capital, real risk — test in Paper mode first. Deliberately long-only (see [Short Selling](#short-selling)).

Risk controls apply to both modes:
- **Max capital per trade** clamps order size regardless of what the strategy's position sizing requests.
- **Daily loss limit** auto-halts a session once the day's realized losses reach the configured amount.
- **Kill switch** (`POST /api/live/kill-all`, or the button in the UI) immediately stops every running session, paper and live.

A stopped or halted session can be permanently deleted (`DELETE /api/live/sessions/<id>`, or the Delete button in the UI) once you no longer need its record — a running session must be stopped first.

Live sessions only tick during NSE market hours (9:15–15:30 IST, Mon–Fri, excluding published NSE trading holidays — `app/live/nse_holidays.py`) once real Kite prices are involved; a paper session on the simulated feed (no Kite connected) ticks continuously so the demo isn't gated on market hours.

### Live WebSocket Ticker

`app/live/ticker.py` runs a background thread wrapping Kite's `KiteTicker` WebSocket (only active when `KITE_ALLOW=true` and Kite is connected) that maintains an in-memory price cache and re-broadcasts every tick over Server-Sent Events at `GET /api/stream` — the same endpoint used for Kite-sync progress. `KiteProvider.get_latest_price` checks this cache first for near-zero-latency prices, falling back to a Kite LTP REST call if the socket hasn't ticked that symbol yet.

### Signal Scanner

The **Scanner** tab (`app/live/scanner.py` + `GET`/`POST /api/scanner`) runs a chosen strategy over a configurable watchlist on its own background scheduler, using a broker that never actually places orders — it exists purely to surface BUY signals for review, without the commitment of opening a paper or live session.

### Market Movers

The **Movers** tab (`GET /api/movers`) computes top gainers, losers, and by-volume tickers by comparing the two most recent daily-interval dates stored in MongoDB — requires at least two days of synced history to show % change.

### Short Selling

`SimulatedBroker` (shared by backtesting and Paper live sessions) supports opening and covering short positions: a `SELL` with no existing long position opens/grows a short instead of no-op'ing, and a subsequent `BUY` covers it, tax-aware in both directions. This is what makes the **ORB (Opening Range Breakout)** strategy's breakdown-short side actually function. `KiteLiveBroker` (real-money orders) stays deliberately long-only — NSE equity shorting has margin/product-type rules (MIS intraday only, no CNC overnight) this mirror doesn't model, so a short-side signal safely no-ops there instead of risking an unintended real order.

## Position Sizing

Every strategy previously bet 100% of available capital on every trade. `GET /api/position-sizing-modes` lists three pluggable modes (`app/engine/position_sizing.py`), selectable in both the Backtest and Live Trading forms:
- **Full Capital** (default) — original behavior, bets everything available.
- **Fixed Fraction** — bets a fixed `fraction` of capital per trade regardless of signal strength.
- **Volatility Target** — sizes so a ~1-standard-deviation move costs a fixed `risk_per_trade` of capital (computed from `lookback`-bar return volatility) — calmer stocks get bigger positions, choppier ones smaller.

Pass `{"position_sizing": {"mode": "fixed_fraction", "fraction": 0.2}}` (or `volatility_target` with `risk_per_trade`/`lookback`) to `POST /api/backtest` or `POST /api/live/sessions`; omit it for the original full-capital behavior.

## Data Providers

Routes never talk to Mongo or Kite directly — they ask `app/data/providers/registry.py` for "the active provider" or "fall through this chain until someone has data for this ticker." Each source (`KiteProvider`, `MongoProvider`, `DummyProvider`) implements the same `DataProvider` interface (`is_available`, `get_tickers`, `get_history`, `get_latest_price`), so adding a new source (e.g. another broker, a CSV import) means writing one class and adding it to `build_providers()` — no changes to `routes/backtest.py`, `routes/tickers.py`, or `routes/health.py`. Default precedence is Kite (live) → MongoDB (synced) → generated (synthetic, always available as the guaranteed fallback); `POST /api/backtest` also accepts an optional `source` field to force a specific provider. Every provider's `get_history` accepts an `interval` kwarg (`"day"`, `"minute"`, `"5minute"`, ...) — `DummyProvider` accepts it for interface parity but always generates daily bars, since synthetic data isn't modeled at intraday resolution.

## Multi-Ticker Backtests

`POST /api/backtest` and `GET /api/backtest/stream` both accept a comma-separated `ticker` string (or a `tickers` array) instead of a single symbol. Histories for all requested tickers are fetched in parallel and merged into one chronological timeline, so a portfolio-level equity curve reflects every ticker's trades in the order they actually happened. The result includes a `ticker_stats` breakdown per ticker (trade count, win rate, realized P&L, price series) for per-ticker drill-down in the UI, alongside the portfolio-level `equity_curve`.

## Archived Backtest Runs

The frontend persists every backtest run — its result *and* the exact configuration used to produce it (capital, date range, interval, position sizing, max capital per trade, daily loss limit) — to `localStorage`, so the run history and each run's settings survive a page reload. A run still mid-stream when the page is refreshed is reconciled to an "interrupted" error state on load rather than showing a permanently frozen progress bar, since its `EventSource` connection doesn't survive the refresh. Individual archived runs can be deleted, or all archived runs cleared at once, from the dashboard.

## Architecture

```
mock-up-market/
├── backend/                  # Flask REST API
│   ├── app/
│   │   ├── routes/           # API endpoints (backtest, tickers, health, kite, live, stream, scanner, movers)
│   │   ├── engine/           # Trading engine (strategy, broker, backtester, 8 strategies, position sizing)
│   │   ├── live/              # Live trading: engine, broker, store, risk, market hours, WebSocket ticker, scanner
│   │   ├── utils/             # Tax calculator, dummy data generator
│   │   └── data/
│   │       ├── db.py          # MongoDB connection helper
│   │       ├── kite_client.py     # Kite Connect session management
│   │       ├── kite_ingest.py     # Historical data fetch + Mongo upsert
│   │       └── providers/     # Pluggable DataProvider implementations + registry
│   ├── scripts/                # kite_login.py, fetch_data.py, fetch_bse_data.py (headless equivalents of the UI)
│   ├── tests/                  # pytest suite (taxes, broker, strategies, providers, backtester, live engine)
│   ├── pyproject.toml / uv.lock # Dependencies, managed with uv (no requirements.txt)
│   ├── .env                    # Configuration
│   └── run.py                  # Entry point
│
├── frontend/                  # Vite + React Dashboard
│   ├── src/
│   │   ├── components/        # UI components (Backtest dashboard, LiveTrading, Scanner, Movers, KiteConnect, ...)
│   │   └── hooks/              # API hooks (useBacktest, useLive, useKite, useStrategies, useTheme, ...)
│   └── vite.config.js         # Dev server with API proxy
│
└── scripts/
    └── setup.sh                # One-command project setup
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Server status + per-provider availability |
| GET | `/api/tickers` | Available stock tickers, merged across active providers |
| GET | `/api/tickers/<symbol>/history` | Up to 300 recent bars for one ticker (used by the ticker detail modal) |
| GET | `/api/strategies` | List of available strategies with descriptions |
| GET | `/api/position-sizing-modes` | List of available position sizing modes with descriptions/params |
| POST | `/api/backtest` | Run a backtest (body: `{ticker or tickers, capital, strategy, source?, from_date?, to_date?, interval?, position_sizing?, max_capital_per_trade?, daily_loss_limit?}`) |
| GET | `/api/backtest/stream` | Same backtest as an SSE stream (query params, same fields) - one `tick` event per bar, then a `done` event with the identical result shape |
| GET | `/api/kite/status` | Whether Kite Connect is configured/connected |
| GET | `/api/kite/login-url` | Zerodha hosted login URL |
| GET | `/api/kite/callback` | OAuth redirect target (exchanges request_token) |
| POST | `/api/kite/disconnect` | Forget the cached Kite session |
| POST | `/api/kite/sync` | Fetch real history for given tickers into MongoDB (runs in a background thread, progress over `/api/stream`) |
| GET | `/api/stream` | Shared SSE stream: live WebSocket ticks, Kite-sync progress |
| GET | `/api/live/market-status` | Whether NSE is currently open |
| GET | `/api/live/sessions` | List all live/paper trading sessions |
| POST | `/api/live/sessions` | Start a session (body: `{ticker, strategy, mode, capital, interval?, max_capital_per_trade?, daily_loss_limit?, position_sizing?, confirm?}`) |
| GET | `/api/live/sessions/<id>` | Get one session's current state |
| POST | `/api/live/sessions/<id>/stop` | Stop a running session |
| DELETE | `/api/live/sessions/<id>` | Permanently delete a stopped/halted session (must be stopped first) |
| POST | `/api/live/kill-all` | Kill switch: stop every running session |
| GET | `/api/scanner` | Current signal scanner state |
| POST | `/api/scanner` | Configure/activate the scanner (body: `{active, strategy, watchlist, interval}`) |
| GET | `/api/movers` | Top gainers/losers/volume from the most recent synced trading day |

## Testing

```bash
cd backend && uv run pytest
```

## License

GPL-3.0

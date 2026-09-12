# 📈 Mock-Up Market

A production-grade algorithmic trading engine for the Indian stock market (NSE) with backtesting, tax-aware profit calculation, real market data via Zerodha Kite Connect, and a premium real-time dashboard.

## Features

- **Four Pluggable Strategies** — MACD Crossover, RSI Mean Reversion, SMA Crossover, Bollinger Bands, all built on one event-driven `Strategy` base class
- **Tax-Aware Backtesting** — Calculates Brokerage, STT, GST, SEBI charges, Stamp Duty for accurate net PnL
- **TradingView Charts** — Professional-grade equity curves and price charts with trade signal markers
- **Pluggable Data Providers** — Zerodha Kite Connect (real, live), MongoDB (previously-synced), and a synthetic generator all implement the same `DataProvider` interface and are swapped in/out with zero route changes — see [Data Providers](#data-providers)
- **Zero-Setup Demo** — Works instantly with generated dummy data (no MongoDB or broker account required)
- **Connect Zerodha** — One click in the dashboard to log in via Kite Connect and sync real NSE history into MongoDB
- **Live Trading Engine** — Run any strategy unattended against live prices in Paper mode (virtual money) or Live mode (real Zerodha orders), with per-trade capital caps, a daily loss limit, and a kill switch — see [Live Trading](#live-trading)

## Quick Start

```bash
# One-command setup
chmod +x scripts/setup.sh && ./scripts/setup.sh

# Start Backend (Terminal 1)
cd backend
source .venv/bin/activate
python run.py

# Start Frontend (Terminal 2)
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

## Local MongoDB (optional, required for Live Trading)

The app works fully without MongoDB (synthetic data, backtesting only). To enable real ticker sync and the Live Trading engine, run Mongo locally via Docker instead of installing it as a native binary:

```bash
docker compose up -d      # starts MongoDB in the background
docker compose down       # stops it (add -v to also wipe stored data)
```

`backend/.env` already points at it (`MONGO_URI=mongodb://localhost:27017`) — no other config needed. Check `GET /api/health` for `"db_connected": true` once it's up.

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

## Live Trading

The **Live Trading** tab runs the same `Strategy` classes used for backtesting against a live price feed, one tick at a time, on an in-process scheduler (polls every `LIVE_POLL_INTERVAL_SECONDS`, default 30s). Requires MongoDB — a session's whole point is to keep running unattended, so its state (cash, positions, trade history, rolling indicator bars) is persisted after every tick and survives a backend restart.

Two modes, same strategy code, different `Broker`:
- **Paper** — virtual money. Uses live Kite prices if connected, otherwise a simulated price feed, so paper trading works with zero setup just like backtesting. Zero financial risk.
- **Live** — places real orders on your connected Zerodha account via `KiteLiveBroker`. Requires an active Kite connection, an explicit `confirm: true`, and a mandatory `max_capital_per_trade` cap. Real capital, real risk — test in Paper mode first.

Risk controls apply to both modes:
- **Max capital per trade** clamps order size regardless of what the strategy's position sizing requests.
- **Daily loss limit** auto-halts a session once the day's realized losses reach the configured amount.
- **Kill switch** (`POST /api/live/kill-all`, or the button in the UI) immediately stops every running session, paper and live.

Live sessions only tick during NSE market hours (9:15–15:30 IST, Mon–Fri) once real Kite prices are involved; a paper session on the simulated feed (no Kite connected) ticks continuously so the demo isn't gated on market hours.

## Data Providers

Routes never talk to Mongo or Kite directly — they ask `app/data/providers/registry.py` for "the active provider" or "fall through this chain until someone has data for this ticker." Each source (`KiteProvider`, `MongoProvider`, `DummyProvider`) implements the same three-method `DataProvider` interface (`is_available`, `get_tickers`, `get_history`), so adding a new source (e.g. another broker, a CSV import) means writing one class and adding it to `build_providers()` — no changes to `routes/backtest.py`, `routes/tickers.py`, or `routes/health.py`. Default precedence is Kite (live) → MongoDB (synced) → generated (synthetic, always available as the guaranteed fallback); `POST /api/backtest` also accepts an optional `source` field to force a specific provider.

## Architecture

```
mock-up-market/
├── backend/                  # Flask REST API
│   ├── app/
│   │   ├── routes/           # API endpoints (backtest, tickers, health, kite)
│   │   ├── engine/           # Trading engine (strategy, broker, backtester, 4 strategies)
│   │   ├── utils/            # Tax calculator, dummy data generator
│   │   └── data/
│   │       ├── db.py         # MongoDB connection helper
│   │       ├── kite_client.py    # Kite Connect session management
│   │       ├── kite_ingest.py    # Historical data fetch + Mongo upsert
│   │       └── providers/    # Pluggable DataProvider implementations + registry
│   ├── scripts/               # kite_login.py, fetch_data.py (headless equivalents of the UI)
│   ├── tests/                 # pytest suite (taxes, broker, strategies, providers)
│   ├── .env                   # Configuration
│   └── run.py                 # Entry point
│
├── frontend/                  # Vite + React Dashboard
│   ├── src/
│   │   ├── components/        # UI components (incl. KiteConnect)
│   │   └── hooks/              # API hooks (incl. useKite, useStrategies)
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
| GET | `/api/strategies` | List of available strategies with descriptions |
| POST | `/api/backtest` | Run a backtest (body: `{ticker, capital, strategy, source?}`) |
| GET | `/api/backtest/stream` | Same backtest as an SSE stream (query params) - one `tick` event per bar, then a `done` event with the identical result shape |
| GET | `/api/kite/status` | Whether Kite Connect is configured/connected |
| GET | `/api/kite/login-url` | Zerodha hosted login URL |
| GET | `/api/kite/callback` | OAuth redirect target (exchanges request_token) |
| POST | `/api/kite/disconnect` | Forget the cached Kite session |
| POST | `/api/kite/sync` | Fetch real history for given tickers into MongoDB |

## Testing

```bash
cd backend && source .venv/bin/activate && pytest
```

## License

GPL-3.0

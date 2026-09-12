# 📈 Mock-Up Market

A production-grade algorithmic trading engine for the Indian stock market (NSE) with backtesting, tax-aware profit calculation, real market data via Zerodha Kite Connect, and a premium real-time dashboard.

## Features

- **Four Pluggable Strategies** — MACD Crossover, RSI Mean Reversion, SMA Crossover, Bollinger Bands, all built on one event-driven `Strategy` base class
- **Tax-Aware Backtesting** — Calculates Brokerage, STT, GST, SEBI charges, Stamp Duty for accurate net PnL
- **TradingView Charts** — Professional-grade equity curves and price charts with trade signal markers
- **Pluggable Data Providers** — Zerodha Kite Connect (real, live), MongoDB (previously-synced), and a synthetic generator all implement the same `DataProvider` interface and are swapped in/out with zero route changes — see [Data Providers](#data-providers)
- **Zero-Setup Demo** — Works instantly with generated dummy data (no MongoDB or broker account required)
- **Connect Zerodha** — One click in the dashboard to log in via Kite Connect and sync real NSE history into MongoDB

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

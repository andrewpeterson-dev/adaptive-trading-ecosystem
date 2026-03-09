# Adaptive Trading Ecosystem

An AI-powered trading platform with a Next.js web dashboard, FastAPI backend, real-time market data, strategy builder, backtesting, and Webull/Alpaca broker integration.

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 14 (App Router, TypeScript) |
| Backend | FastAPI (Python, async SQLAlchemy) |
| Database | SQLite (dev) / PostgreSQL (Docker) |
| Cache / Streaming | Redis |
| Brokers | Webull OpenAPI v2, Alpaca |
| Market Data | yFinance, Alpaca, Finnhub (fallback chain) |

## Features

- **Strategy Builder** — build multi-condition trading strategies with 20+ technical indicators
- **Backtesting** — replay strategies against historical OHLCV data
- **Paper & Live Trading** — execute via Webull or Alpaca with confirmation gate
- **Real-time Prices** — WebSocket price streaming with Redis pub/sub
- **Risk Management** — portfolio exposure, drawdown limits, position sizing
- **Market Sentiment** — AI-powered news sentiment aggregated per ticker
- **API Connections** — manage multiple broker and market data keys per user

## Quick Start

### Local Development

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your broker API keys

# 2. Backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

# 3. Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Docker

```bash
docker-compose up -d
```

## Project Structure

```
adaptive-trading-ecosystem/
├── api/                # FastAPI backend
│   ├── main.py         # App entry, all routers registered
│   ├── routes/         # auth, trading, webull, market, ws, strategies
│   └── middleware/     # JWT auth
├── config/             # Pydantic settings + .env
├── db/                 # SQLAlchemy models, migrations, encryption
├── data/               # MarketDataService (yFinance/Alpaca/Finnhub)
├── frontend/           # Next.js app (the ONLY frontend)
│   └── src/
│       ├── app/        # Pages (dashboard, strategies, backtest, settings)
│       ├── components/ # Strategy builder, analytics, settings panels
│       ├── hooks/      # useAuth, usePriceStream, useTradingMode
│       └── lib/        # API client, indicator registry
├── risk/               # Risk calculation utilities
├── scripts/            # DB init, seed scripts
└── docker-compose.yml
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login, returns JWT |
| GET | `/api/auth/me` | Current user profile |
| GET | `/api/trading/account` | Broker account info |
| GET | `/api/trading/positions` | Open positions |
| GET | `/api/trading/risk-summary` | Portfolio risk |
| GET | `/api/market/quote/{symbol}` | Live quote |
| GET | `/api/market/bars/{symbol}` | OHLCV bars |
| POST | `/api/market/batch-quotes` | Batch quotes (up to 50) |
| WS | `/ws/market?token=<jwt>` | Real-time price stream |
| GET | `/api/strategies/list` | Saved strategies |
| POST | `/api/strategies/analyze` | Analyze strategy |
| POST | `/api/backtest/run` | Run backtest |
| GET | `/api/news/sentiment/report` | Market sentiment |

## Auth

JWT-based (7-day expiry). Token stored in `localStorage` + cookie. All API calls include `Authorization: Bearer <token>`. Broker credentials (app key/secret) are Fernet-encrypted at rest.

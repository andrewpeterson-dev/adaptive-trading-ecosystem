# Adaptive Trading Ecosystem

> An AI-powered algorithmic trading platform with autonomous bot execution, LLM-driven trade reasoning, multi-broker support, and a real-time Next.js dashboard.

![Next.js](https://img.shields.io/badge/Next.js-15-black?style=flat-square&logo=next.js)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=flat-square&logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red?style=flat-square)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-5.4-37814A?style=flat-square)

---

## Screenshot

> _Portfolio equity curve, AI reasoning panel, open positions, and live risk metrics_

![Dashboard](docs/screenshot-placeholder.png)

---

## Overview

The Adaptive Trading Ecosystem is a full-stack algorithmic trading platform supporting both paper and live execution. Two distinct trading paths are available:

- **Autonomous Bot Runner** — user-created strategy bots evaluate market conditions every 60 seconds and execute trades automatically. A `ReasoningEngine` filters every trade on risk before submission; a per-user kill switch halts all activity instantly.
- **Cerberus AI Chat** — an embedded assistant that drafts trade proposals on demand. Each proposal requires explicit user confirmation via a SHA-256 token before any order is placed.

The platform routes between multiple LLMs for trade reasoning and selects the best-performing model per bot automatically based on live win rate, Sharpe ratio, and drawdown metrics.

---

## Key Features

**Execution and Bots**
- Fully autonomous bot engine with configurable aggressiveness levels (1–4)
- Kelly criterion position sizing with sector concentration enforcement
- Stop-loss, take-profit, trailing stop, and time-based exits
- Paper and live modes isolated per user with independent P&L ledgers
- Per-user kill switch with tiered drawdown thresholds (reduce / halt / kill)

**AI and Reasoning**
- Multi-LLM auto-routing: best model selected per bot from a composite score (win rate, Sharpe, avg return, max drawdown)
- AI brain evaluates entry quality before every bot trade executes
- Cerberus chat assistant with 35 tools across portfolio, risk, market data, trading, analytics, and research categories
- FinGPT sentiment analysis with 15-minute Redis cache; falls back to GPT-based scoring
- Document ingestion pipeline (PDF, DOCX, XLSX) with pgvector semantic search

**Strategy Builder**
- Condition-based strategy editor with 20+ technical indicators and a template gallery
- AI chat mode for natural-language strategy generation
- Per-strategy backtesting with Sharpe, Sortino, win rate, max drawdown, and profit factor
- Strategy type scoring: platform learns which categories perform best per user and can block underperformers

**Risk Management**
- Configurable position size limits, portfolio exposure cap, and max drawdown circuit breaker
- Market regime detection across 5 states (low/high volatility bull/bear, sideways)
- Risk events logged for all limit breaches with full audit trail
- Options fallback routing via Tradier paper API

**Dashboard**
- Portfolio equity curve with drawdown overlay, 30-second auto-refresh
- AI reasoning panel, market scanner, and strategy status tabs
- Open positions, trade log, and market mood widget
- Live/paper mode toggle with visual status indicator

**Infrastructure**
- JWT authentication with email verification and password reset
- Broker credentials encrypted at rest with Fernet symmetric encryption
- WebSocket feed for real-time bot activity events
- Celery workers for async document ingestion and backtest jobs
- SQLite for local development; PostgreSQL + asyncpg for production
- Railway-compatible with auto-detected `DATABASE_URL` and `REDIS_URL`

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Next.js Frontend                    │
│   Dashboard · Strategy Builder · Cerberus Chat       │
│                  localhost:3000                       │
└──────────────────────┬──────────────────────────────┘
                       │  HTTP + WebSocket
┌──────────────────────▼──────────────────────────────┐
│                  FastAPI Backend                     │
│  /api/trading · /api/strategies · /api/ai/chat       │
│                  localhost:8000                       │
└──────┬──────────────────┬──────────────────┬─────────┘
       │                  │                  │
┌──────▼───────┐  ┌───────▼──────┐  ┌───────▼────────┐
│  Bot Engine  │  │   AI Brain   │  │ Reasoning Engine│
│  runner.py   │  │  auto_router │  │  risk filter    │
│  60s loop    │  │  + LLM eval  │  │  + Kelly sizing │
└──────┬───────┘  └──────────────┘  └────────────────┘
       │
┌──────▼──────────────────────────────────────────────┐
│                   Broker Layer                       │
│      Alpaca (paper + live)  ·  Webull (per-user)    │
└──────┬──────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────┐
│                    Data Layer                        │
│  PostgreSQL / SQLite  ·  Redis  ·  S3 / MinIO        │
│  yFinance · Polygon · Finnhub · Alpha Vantage        │
└─────────────────────────────────────────────────────┘
```

**Service layout:**

| Path | Purpose |
|---|---|
| `api/` | FastAPI routes — auth, trading, strategies, AI chat, WebSocket |
| `frontend/` | Next.js 15 app (the only frontend) |
| `services/bot_engine/` | Autonomous bot loop, condition evaluator, AI entry evaluator |
| `services/ai_brain/` | LLM trading engine, auto-router, per-bot performance tracker |
| `services/ai_core/` | Cerberus chat controller, model router, 35 tools, memory, safety guard |
| `services/reasoning_engine/` | Pre-trade risk filter, Kelly sizing, sector concentration checks |
| `db/` | SQLAlchemy models (30+ tables), Alembic migrations, Fernet encryption |
| `config/` | Pydantic settings — all configuration from environment variables |
| `data/` | Market data abstraction layer with provider fallback chain |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, TypeScript, Tailwind CSS, Lucide |
| Backend | FastAPI, Python 3.11+, Uvicorn, Pydantic v2 |
| Database | SQLAlchemy 2.0 async, Alembic, PostgreSQL / SQLite, pgvector |
| Caching | Redis asyncio, 15-minute sentiment TTL |
| Task Queue | Celery 5.4 — document ingestion and backtest workers |
| Brokers | Alpaca Markets API, Webull OpenAPI v2 SDK |
| Market Data | yFinance (free fallback), Polygon, Finnhub, Alpha Vantage, Tradier |
| LLM | OpenAI (GPT-5.4, GPT-4.1), Anthropic (Claude), Perplexity (Sonar), Ollama (local) |
| Backtesting | VectorBT, NumPy, Pandas, scikit-learn |
| Portfolio Opt | PyPortfolioOpt, CVXPY |
| Auth / Security | JWT (PyJWT), bcrypt, Fernet encryption |
| Storage | AWS S3 / MinIO for document pipeline |
| Logging | structlog, JSONL audit log |
| Deployment | Railway (backend), Vercel (frontend) |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Redis (local or managed)

### 1. Clone and configure

```bash
git clone <repo-url>
cd adaptive-trading-ecosystem

cp .env.example .env
```

Open `.env` and fill in the minimum required fields:

```bash
JWT_SECRET=        # python3 -c "import secrets; print(secrets.token_urlsafe(48))"
ENCRYPTION_KEY=    # python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
OPENAI_API_KEY=    # or ANTHROPIC_API_KEY for Cerberus AI
ALPACA_API_KEY=    # paper trading key from alpaca.markets
ALPACA_SECRET_KEY=
```

`USE_SQLITE=true` is the default — no PostgreSQL setup is required for local development.

### 2. Backend

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head

python3 -m uvicorn api.main:app --port 8000 --reload
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The frontend proxies all `/api/*` requests to the backend at port 8000.

Interactive API docs are available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 4. Background workers (optional)

Required for document ingestion and backtest jobs:

```bash
celery -A services.workers.celery_app worker -Q documents,backtests --loglevel=info
```

---

## Configuration Reference

All configuration is environment-variable driven. See `.env.example` for the complete reference.

| Variable | Default | Description |
|---|---|---|
| `TRADING_MODE` | `paper` | `paper` or `live` |
| `LIVE_TRADING_ENABLED` | `false` | Must be `true` for any live orders to execute |
| `USE_SQLITE` | `true` | Set `false` and provide `DATABASE_URL` for PostgreSQL |
| `DATABASE_URL` | — | PostgreSQL connection string (Railway / Neon / Supabase) |
| `REDIS_URL` | — | Redis connection string |
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | — | Alpaca paper or live credentials |
| `OPENAI_API_KEY` | — | Required for AI reasoning and Cerberus chat |
| `ANTHROPIC_API_KEY` | — | LLM fallback / research mode |
| `FEATURE_CERBERUS_ENABLED` | `true` | Toggle the AI chat assistant |
| `FEATURE_LIVE_TRADE_PROPOSALS_ENABLED` | `false` | Enable live trade proposals from chat |

---

## Safety

Live trading is disabled by default. Three independent conditions must all be satisfied before any live order executes:

1. `TRADING_MODE=live` and `LIVE_TRADING_ENABLED=true` in environment
2. User has confirmed live trading in account settings (`live_bot_trading_confirmed = true`)
3. User's kill switch is not active (`UserRiskLimits.kill_switch_active = false`)

The `ReasoningEngine` evaluates every bot trade before submission and can reject it based on drawdown limits, sector concentration, position size, and market regime. All risk events are persisted to the `risk_events` table for audit.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/login` | Login, returns JWT |
| GET | `/api/auth/me` | Current user profile |
| GET | `/api/trading/account` | Broker account info |
| GET | `/api/trading/positions` | Open positions |
| GET | `/api/trading/risk-summary` | Portfolio risk summary |
| GET | `/api/market/quote/{symbol}` | Live quote |
| GET | `/api/market/bars/{symbol}` | OHLCV bars |
| GET | `/api/strategies/list` | Saved strategies |
| POST | `/api/backtest/run` | Run a backtest |
| POST | `/api/ai/chat` | Send message to Cerberus (SSE streaming) |
| WS | `/ws/ai/chat?token=<jwt>` | WebSocket Cerberus chat |
| POST | `/api/ai/tools/confirm/{token}` | Confirm a trade proposal |
| POST | `/api/ai/documents/upload` | Upload document for RAG ingestion |

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Deployment

**Backend (Railway)**

Set `DATABASE_URL` and `REDIS_URL` as Railway environment variables. The application detects them automatically and switches from SQLite to PostgreSQL. Variables marked `[VERCEL-REQUIRED]` in `.env.example` are also needed here if the backend handles auth emails.

**Frontend (Vercel)**

Set `NEXT_PUBLIC_API_URL` (public backend URL) and `NEXT_PUBLIC_WS_URL` (WebSocket URL) in Vercel project settings. All other `[VERCEL-REQUIRED]` variables are documented in `.env.example`.

---

## License

MIT

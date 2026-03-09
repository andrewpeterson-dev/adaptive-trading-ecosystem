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
│   ├── routes/         # auth, trading, webull, market, ws, strategies, ai_chat, ai_tools, documents
│   └── middleware/     # JWT auth
├── config/             # Pydantic settings + .env
├── db/                 # SQLAlchemy models, migrations, encryption
│   └── copilot_models.py  # 18 copilot-specific models
├── data/               # MarketDataService (yFinance/Alpaca/Finnhub)
├── services/
│   ├── ai_core/        # AI Copilot engine
│   │   ├── chat_controller.py  # Main orchestration pipeline
│   │   ├── model_router.py     # LLM selection logic
│   │   ├── safety_guard.py     # Output sanitization + feature flags
│   │   ├── tools/              # 35 tools (portfolio, risk, market, trading, analytics, research)
│   │   ├── proposals/          # Trade proposal + confirmation flow
│   │   ├── memory/             # Short-term, operational, semantic memory
│   │   └── documents/          # Document ingestion pipeline
│   └── workers/        # Celery workers (documents, backtests, analytics)
├── frontend/           # Next.js app (the ONLY frontend)
│   └── src/
│       ├── app/        # Pages (dashboard, strategies, backtest, settings)
│       ├── components/ # Strategy builder, analytics, settings panels
│       │   └── copilot/  # 13 copilot UI components (widget, chat, tabs)
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
| POST | `/api/ai/chat` | Send message to copilot (SSE streaming response) |
| WS | `/ws/ai/chat?token=<jwt>` | WebSocket copilot chat |
| GET | `/api/ai/conversations` | List user's conversations |
| POST | `/api/ai/tools/confirm/{token}` | Confirm a trade proposal |
| POST | `/api/ai/documents/upload` | Upload document for RAG ingestion |
| GET | `/api/ai/documents/search` | Semantic search across documents |

## AI Copilot

An AI-powered assistant embedded in the trading dashboard. The copilot can analyze portfolios, explain risk, draft trade proposals, run backtests, and answer research questions — but **never executes trades autonomously**. Every trade requires explicit user confirmation.

### Architecture

```
User message
  → ChatController (services/ai_core/chat_controller.py)
    → ModelRouter selects LLM based on intent complexity
    → ContextBuilder assembles conversation history + memory + portfolio state
    → PromptManager renders system/user prompts
    → LLM generates response (streaming via SSE)
    → ToolExecutor runs any tool calls (35 tools across 6 categories)
    → SafetyGuard sanitizes output (PII redaction, feature flag enforcement)
  → Response streamed to frontend widget
```

**Model Routing** — deterministic routing based on query complexity:
| Model | Role | When Used |
|-------|------|-----------|
| gpt-5.4 | Primary | Complex analysis, multi-step reasoning, trade proposals |
| gpt-4.1 | Fast | Simple queries, quick lookups, formatting |
| claude-sonnet-4-6 | Fallback/Research | Deep research, long-context analysis, OpenAI downtime |
| Perplexity | Search | Questions requiring real-time web/news data |

**Tool System** — 35 tools across 6 categories:
- **Portfolio** (6): get_positions, get_balances, portfolio_summary, allocation_analysis, performance_history, tax_lots
- **Risk** (6): risk_assessment, exposure_analysis, drawdown_check, var_calculation, correlation_matrix, stress_test
- **Market** (6): get_quote, get_bars, batch_quotes, market_overview, sector_performance, earnings_calendar
- **Trading** (6): draft_trade, preview_order, confirm_trade, cancel_proposal, order_status, trade_history
- **Analytics** (6): run_backtest, strategy_analysis, indicator_scan, compare_strategies, optimize_params, performance_attribution
- **Research** (5): search_news, sentiment_analysis, company_profile, financial_statements, analyst_ratings

**Memory Layers**:
- **Short-term**: Redis-backed conversation context (last N messages per session)
- **Operational**: PostgreSQL — user preferences, trade history summaries, learned patterns
- **Semantic**: pgvector embeddings for document search and long-term knowledge retrieval

**Trade Safety Flow**:
1. AI drafts a trade proposal (never executes directly)
2. Risk checks run automatically (position size, exposure, drawdown limits)
3. User reviews and clicks "Confirm" in the UI
4. SHA-256 confirmation token is validated server-side
5. Pre-execution risk re-check runs
6. Order is placed via broker API
7. Full audit trail logged (proposal → confirmation → execution → fill)

### Copilot Environment Variables

Add these to your `.env` file:

```bash
# AI / LLM
OPENAI_API_KEY=sk-...              # Required for gpt-5.4 and gpt-4.1
ANTHROPIC_API_KEY=sk-ant-...       # Required for Claude fallback
PERPLEXITY_API_KEY=pplx-...        # Required for real-time search tool

# Document Storage (S3-compatible)
S3_BUCKET_NAME=trading-docs
S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# Feature Flags
FEATURE_COPILOT_ENABLED=true       # Master switch for copilot subsystem
FEATURE_COPILOT_TOOLS=true         # Enable tool execution (portfolio, risk, etc.)
FEATURE_COPILOT_TRADING=false      # Enable trade proposal/confirmation flow
FEATURE_COPILOT_DOCUMENTS=false    # Enable document upload and RAG search
FEATURE_COPILOT_MEMORY=true        # Enable persistent memory across sessions
```

### Running Workers

Copilot uses Celery workers for background tasks (document ingestion, backtests, analytics):

```bash
# Document ingestion worker
celery -A services.workers.celery_app worker -Q documents --concurrency=2

# Backtest worker
celery -A services.workers.celery_app worker -Q backtests --concurrency=1

# All queues (dev convenience)
celery -A services.workers.celery_app worker -Q documents,backtests,analytics --concurrency=4
```

Requires Redis as the broker (`CELERY_BROKER_URL` in `.env`, defaults to `redis://localhost:6379/1`).

### Feature Flags

| Flag | Default | Description |
|------|---------|-------------|
| `FEATURE_COPILOT_ENABLED` | `true` | Master switch — disables all copilot routes and the frontend widget |
| `FEATURE_COPILOT_TOOLS` | `true` | Allows the LLM to call portfolio, risk, market, and analytics tools |
| `FEATURE_COPILOT_TRADING` | `false` | Enables trade proposal drafting and confirmation flow |
| `FEATURE_COPILOT_DOCUMENTS` | `false` | Enables document upload, parsing, chunking, and RAG search |
| `FEATURE_COPILOT_MEMORY` | `true` | Enables persistent memory (operational + semantic layers) across sessions |

Flags are checked at the route level (`SafetyGuard`) and in the frontend (widget visibility). Progressive rollout: enable `TOOLS` first, then `MEMORY`, then `DOCUMENTS`, then `TRADING` last.

## Auth

JWT-based (7-day expiry). Token stored in `localStorage` + cookie. All API calls include `Authorization: Bearer <token>`. Broker credentials (app key/secret) are Fernet-encrypted at rest.

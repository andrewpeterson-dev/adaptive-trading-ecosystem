# Adaptive Trading Ecosystem

## Architecture
- **ONE frontend only**: Next.js at `localhost:3000` (`frontend/`)
- **Backend**: FastAPI at `localhost:8000` (`api/`)
- **Database**: SQLite (`trading_ecosystem.db`) with async SQLAlchemy
- **Broker**: Webull OpenAPI v2 SDK (per-user encrypted credentials in DB)

## Critical Rules
- **DO NOT create or run Streamlit dashboards** — Streamlit was removed. The `dashboard/` directory no longer exists.
- **DO NOT recreate `dashboard/` or any Streamlit files.**
- **Webull is per-user** — credentials are encrypted in `broker_credentials` table. Only users with stored credentials can access broker data. The primary account has Webull access configured.
- **Two trading paths exist:**
  - **Bot Runner (autonomous):** User creates and starts a bot (via Cerberus chat `createBot` tool or UI). `BotRunner` (`services/bot_engine/runner.py`) evaluates running bots every 60s and executes trades automatically — no per-trade confirmation. `ReasoningEngine` acts as a risk filter. Kill switch: `UserRiskLimits.kill_switch_active` halts all bot trading for a user.
  - **Cerberus Chat (one-off proposals):** AI drafts a trade proposal, user confirms with SHA-256 token. `user_confirmed=True` safety gate applies here only.

## Key Files
| File | Purpose |
|------|---------|
| `api/main.py` | FastAPI app entry point, all routes registered here |
| `api/routes/auth.py` | Login, register, /me, broker credentials |
| `api/routes/webull.py` | Per-user Webull broker routes |
| `api/routes/trading.py` | Trading routes — delegates to Webull or Alpaca |
| `api/middleware/auth.py` | JWT authentication middleware |
| `config/settings.py` | All settings via pydantic-settings + .env |
| `db/models.py` | SQLAlchemy models (User, BrokerCredential, Trade, etc.) |
| `db/encryption.py` | Fernet encryption for broker API keys |
| `data/webull_client.py` | Webull SDK wrapper (paper + live clients) |
| `frontend/` | Next.js app (the ONLY frontend) |
| `db/cerberus_models.py` | 18 Cerberus SQLAlchemy models (conversations, memory, documents, proposals, audit) |
| `services/bot_engine/runner.py` | BotRunner — autonomous bot loop, evaluates every 60s, executes trades |
| `services/bot_engine/evaluator.py` | Condition evaluation against market data |
| `services/bot_engine/ai_evaluator.py` | AI-powered entry evaluation for bots |
| `services/reasoning_engine/engine.py` | ReasoningEngine — risk filter for bot trades |
| `services/ai_core/chat_controller.py` | Main AI orchestration — context → route → prompt → model → tools → stream |
| `services/ai_core/model_router.py` | Deterministic LLM routing (gpt-5.4, gpt-4.1, claude-sonnet-4-6, Perplexity) |
| `services/ai_core/tools/` | 35 Cerberus tools across 6 categories (portfolio, risk, market, trading, analytics, research) |
| `services/ai_core/safety_guard.py` | Output sanitization, PII redaction, feature flag enforcement |
| `services/ai_core/proposals/` | Trade proposal + confirmation flow with SHA-256 tokens |
| `services/ai_core/memory/` | Memory service (short-term, operational, semantic/pgvector) |
| `services/ai_core/documents/` | Document ingestion pipeline (upload → parse → chunk → embed) |
| `api/routes/ai_chat.py` | REST + WebSocket API for Cerberus chat |
| `api/routes/ai_tools.py` | Trade confirmation/execution endpoints |
| `api/routes/documents.py` | Document upload, ingestion, search endpoints |
| `frontend/src/components/cerberus/` | Cerberus UI widget (13 React components) |
| `services/workers/` | Celery workers for document ingestion, backtests, analytics |

## Running
```bash
# Backend
cd ~/adaptive-trading-ecosystem && python3 -m uvicorn api.main:app --port 8000

# Frontend
cd ~/adaptive-trading-ecosystem/frontend && npm run dev
```

## Auth Flow
1. Frontend calls `POST /api/auth/login` with email + password
2. Backend returns JWT token (7-day expiry)
3. Frontend stores token in cookie + localStorage
4. All subsequent API calls include `Authorization: Bearer <token>`
5. JWT middleware decodes token and sets `request.state.user_id`

## Webull Integration
- Uses `webullsdkcore` + `webullsdktrade` (official OpenAPI v2 SDK)
- Account discovery: `get_app_subscriptions()` (NOT `get_account_list()`)
- Balance requires currency arg: `get_account_balance(acct, "USD")`
- Positions response uses `"holdings"` key
- App key/secret stored encrypted in DB, decrypted per-request

## Cerberus AI
- **Two trading paths:** (1) Bot Runner — autonomous execution every 60s for user-created bots, ReasoningEngine as risk filter. (2) Chat proposals — AI drafts, user confirms via SHA-256 token.
- Model routing: gpt-5.4 (primary), gpt-4.1 (simple), claude-sonnet-4-6 (fallback/research), Perplexity (search)
- Bots support paper/live mode (from `UserTradingSession`), kill switch via `UserRiskLimits.kill_switch_active`
- Feature flags control progressive rollout (FEATURE_CERBERUS_ENABLED, etc.)
- Workers: `celery -A services.workers.celery_app worker -Q documents` / `-Q backtests`
- Frontend widget: floating bubble → 420px slide-out panel with 5 tabs (Chat, Strategy, Portfolio, Bots, Research)

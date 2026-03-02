# Adaptive Trading Ecosystem

## Architecture
- **ONE frontend only**: Next.js at `localhost:3000` (`frontend/`)
- **Backend**: FastAPI at `localhost:8000` (`api/`)
- **Database**: SQLite (`trading_ecosystem.db`) with async SQLAlchemy
- **Broker**: Webull OpenAPI v2 SDK (per-user encrypted credentials in DB)

## Critical Rules
- **DO NOT create or run Streamlit dashboards** — Streamlit was removed. The `dashboard/` directory no longer exists.
- **DO NOT recreate `dashboard/` or any Streamlit files.**
- **Webull is per-user** — credentials are encrypted in `broker_credentials` table. Only users with stored credentials can access broker data. Andrew's account (user_id=2) is the only one with Webull access.
- **Trades require explicit confirmation** — `user_confirmed=True` must be passed to place any order. The UI submit button is the ONLY place this is set.

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

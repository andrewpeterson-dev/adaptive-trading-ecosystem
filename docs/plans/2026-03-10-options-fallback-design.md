# Options Fallback Design
**Date:** 2026-03-10
**Status:** Approved

## Problem
Webull paper trading does not support options via API. When a user wants to simulate options strategies alongside their Webull equity account, the platform must detect the gap, offer a clean fallback (Tradier paper), and keep all metrics consistent — no mixed stats, no double-counting.

---

## Section 1: Capability Registry

Extend `ApiProvider` with three new boolean columns:
- `supports_stocks` — can trade equities
- `supports_order_placement` — API supports placing/cancelling orders (vs read-only)
- `supports_positions_streaming` — supports real-time position updates via WebSocket/push

Existing columns retained: `supports_trading`, `supports_paper`, `supports_market_data`, `supports_options`, `supports_crypto`.

**Webull (paper):** `supports_stocks=True, supports_options=False, supports_paper=True, supports_order_placement=True, supports_positions_streaming=False`
**Tradier:** `supports_stocks=True, supports_options=True, supports_paper=True, supports_order_placement=True, supports_positions_streaming=False`

Capabilities are **static metadata** seeded in `scripts/seed_providers.py` — no live probing. All 22 providers updated.

---

## Section 2: Detection + Consent

### Trigger
Detection fires at:
1. Options order placement (`instrument_type="option"`)
2. Strategy deploy when `strategy.uses_options=True` (new bool field on `StrategySchema`)

### Backend Error Response (HTTP 422)
```json
{
  "code": "OPTIONS_NOT_SUPPORTED",
  "active_broker": "Webull (Paper)",
  "available_options_providers": [
    {"id": 3, "name": "Tradier", "slug": "tradier", "is_connected": false}
  ]
}
```

### Consent Storage
Two new columns on `UserApiSettings`:
- `options_fallback_enabled: bool = False`
- `options_provider_connection_id: int | null` — FK to `user_api_connections`

**Endpoint:** `POST /api/v2/api-settings/options-fallback`
Body: `{"enabled": true, "provider_connection_id": 7}`
Validation: target connection's provider must have `supports_options=True` and `supports_paper=True`.

### Frontend Modal (`OptionsFallbackModal`)
Triggered when any API call returns `OPTIONS_NOT_SUPPORTED`. Shows:
- **What changes:** Options orders routed to Tradier paper
- **What doesn't change:** Webull equity, cash, stock positions unaffected
- Provider selector (connected options providers only, or inline connect flow)
- Explicit "Enable Options Fallback" confirm button

Consent stored server-side only — not localStorage.

---

## Section 3: Separate Ledgers

### Sources
- `ledgerBroker` — active broker (Webull) paper account balance + positions value (live)
- `ledgerOptionsSim` — P&L derived from `options_sim_trades` table (our records of Tradier paper orders we placed), cross-referenced against Tradier paper API for current marks

### New Table: `options_sim_trades`
| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| user_id | int FK users | |
| connection_id | int FK user_api_connections | Tradier connection |
| tradier_order_id | str | For status/fill lookup |
| symbol | str | Underlying |
| option_type | str | call / put |
| strike | float | |
| expiry | date | |
| qty | int | |
| fill_price | float | |
| realized_pnl | float nullable | Null until closed |
| status | str | open / closed / cancelled |
| opened_at | datetime | |
| closed_at | datetime nullable | |

### Endpoint: `GET /api/v2/ledger/combined`
```json
{
  "broker_equity": 1000000.00,
  "broker_label": "Webull Paper",
  "options_sim_pnl": 1250.00,
  "options_label": "Tradier Paper (Options Sim)",
  "total_simulated_equity": 1001250.00,
  "open_options_positions": [...],
  "metrics": {
    "returns_pct": 0.125,
    "drawdown_pct": 0.003,
    "sharpe": 1.42
  }
}
```

### Rules
- `total_simulated_equity = broker_equity + options_sim_pnl`
- All metrics computed from `total_simulated_equity` baseline
- `ledgerOptionsSim` tracks **P&L only** — never cash (no Tradier cash double-counting)
- If `options_fallback_enabled=False`: `options_sim_pnl=0`, `total=broker_equity`

---

## Section 4: Execution Routing

### Order Schema Extension
Every order gains:
- `instrument_type: str = "stock"` — `"stock"` | `"option"`
- `option_type: str | null` — `"call"` | `"put"`
- `strike: float | null`
- `expiry: date | null`

### Router (`services/order_router.py`)
```
if instrument_type == "option":
    if active_broker.supports_options        → route to active broker
    elif options_fallback_enabled            → route to options_provider_connection
                                               insert into options_sim_trades
    else                                     → raise OPTIONS_NOT_SUPPORTED (422)
else:
    → always route to active broker
```

All routing logic lives in `services/order_router.py` — called by both paper trading and direct trade routes.

**Rejection message:** `"Options trading is not supported by Webull paper. Enable options fallback in Settings → API Connections to proceed."`

---

## Section 5: Tests

### `tests/test_options_routing.py` (unit, mocked)
- Webull active + options order + fallback disabled → 422, order not placed
- Webull active + options order + fallback enabled → routes to Tradier, `options_sim_trades` row inserted
- Webull active + stock order → routes to Webull regardless of fallback flag
- Saving fallback with non-options provider → validation error

### `tests/test_ledger_aggregator.py` (unit, mocked)
- `total = broker_equity + options_sim_pnl` exactly
- `options_sim_pnl` = realized P&L from closed trades + MTM on open positions
- Metrics use `total_simulated_equity` as baseline
- No fallback enabled → `options_pnl=0`, `total=broker_equity`

### `tests/test_capability_flags.py` (unit)
- Webull `supports_options=False` after seed
- Tradier `supports_options=True` after seed
- All 22 providers have no null capability flags
- Invalid fallback provider → rejected at settings save

---

## Files Affected

| File | Action |
|------|--------|
| `db/models.py` | Add 3 cols to `ApiProvider`, 2 cols to `UserApiSettings`, new `OptionSimTrade` model |
| `scripts/seed_providers.py` | Update all 22 providers with new capability flags |
| `services/order_router.py` | New — routing logic |
| `services/ledger_aggregator.py` | New — combined ledger computation |
| `api/routes/api_connections.py` | Add `POST /api/v2/api-settings/options-fallback` |
| `api/routes/trading.py` | Extend order schema, call order_router |
| `api/routes/paper_trading.py` | Extend order schema, call order_router |
| `api/routes/ledger.py` | New — `GET /api/v2/ledger/combined` |
| `api/main.py` | Register ledger router |
| `frontend/src/components/settings/OptionsFallbackModal.tsx` | New — consent modal |
| `frontend/src/components/ledger/CombinedLedgerCard.tsx` | New — dashboard widget |
| `tests/test_options_routing.py` | New |
| `tests/test_ledger_aggregator.py` | New |
| `tests/test_capability_flags.py` | New |

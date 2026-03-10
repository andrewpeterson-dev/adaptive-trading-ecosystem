# Design: Global Paper/Live Mode Separation

**Date:** 2026-03-10
**Status:** Approved

## Problem

The paper/live toggle exists in the frontend but is cosmetic — backend ignores it. Dashboard stats, strategies, bots, and portfolio data are not filtered by mode. Users cannot trust that paper and live environments are truly isolated.

## Core Principle

Paper and live are **two completely independent trading environments** sharing one set of Webull credentials. The backend is the single source of truth for which mode is active. Every query, every trade, every stat is scoped to the active mode.

---

## 1. Server-Side Mode Authority

**The backend owns the mode, not the frontend.**

### New Model: `UserTradingSession`

```python
class UserTradingSession(Base):
    __tablename__ = "user_trading_sessions"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    active_mode = Column(Enum(TradingModeEnum), nullable=False, default=TradingModeEnum.PAPER)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### New Endpoint

```
POST /api/user/set-mode
Body: { "mode": "paper" | "live" }
Response: { "mode": "paper", "switched_at": "..." }
```

- Stores mode in `user_trading_sessions` table
- Returns the confirmed mode
- Logs a `mode_switch` system event (see section 6)

### Mode Middleware

New middleware reads `user_trading_sessions` on every authenticated request and sets `request.state.trading_mode`. No header or query param needed — the mode is always server-authoritative.

```python
# Pseudocode — runs after auth middleware
session = await get_user_trading_session(request.state.user_id)
request.state.trading_mode = session.active_mode  # "paper" or "live"
```

**Every endpoint** that touches trading data reads from `request.state.trading_mode`.

### Frontend Changes

- `useTradingMode.setMode()` calls `POST /api/user/set-mode` first
- Only updates local state + theme after backend confirms
- On page load, `GET /api/user/mode` fetches the server-side mode (source of truth)
- localStorage is a cache, not authority

---

## 2. Frontend Cache Invalidation

When mode switches, **all cached data must be purged** so paper data never appears in live mode.

### Implementation

```typescript
// In useTradingMode.ts
const queryClient = useQueryClient();

const setMode = async (next: TradingMode) => {
  await api.post("/api/user/set-mode", { mode: next });
  queryClient.clear();           // Nuke entire React Query cache
  setModeState(next);
  localStorage.setItem(STORAGE_KEY, next);
  applyTheme(next);
  // All components re-fetch automatically since cache is empty
};
```

- `queryClient.clear()` — not `invalidateQueries()`, which might serve stale data during refetch
- Every `useQuery` hook already has `mode` in the query key for future cache separation, but `clear()` is the safety net

---

## 3. Template-Based Strategy Architecture

Strategies use a **template → instance** model. The template defines the logic; instances run it in a specific mode with mode-appropriate parameters.

### New Models

```python
class StrategyTemplate(Base):
    """Reusable strategy logic definition. Mode-agnostic."""
    __tablename__ = "strategy_templates"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    conditions = Column(JSON, nullable=False)       # Entry/exit rules
    action = Column(String(16), default="BUY")
    stop_loss_pct = Column(Float, default=0.02)
    take_profit_pct = Column(Float, default=0.05)
    timeframe = Column(String(16), default="1D")
    diagnostics = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    instances = relationship("StrategyInstance", back_populates="template")


class StrategyInstance(Base):
    """A running instance of a template in a specific mode."""
    __tablename__ = "strategy_instances"

    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("strategy_templates.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mode = Column(Enum(TradingModeEnum), nullable=False)
    is_active = Column(Boolean, default=True)
    position_size_pct = Column(Float, default=0.1)  # Mode-specific sizing
    max_position_value = Column(Float, nullable=True)
    nickname = Column(String(100), nullable=True)    # e.g. "SPY Momentum — Live"
    created_at = Column(DateTime, default=datetime.utcnow)
    promoted_from_id = Column(Integer, ForeignKey("strategy_instances.id"), nullable=True)

    template = relationship("StrategyTemplate", back_populates="instances")
```

### Migration Path

Existing `strategies` table rows become `strategy_templates`. A migration creates one `strategy_instance` per existing strategy in paper mode.

### Promote to Live Flow

1. User clicks "Promote to Live" on a paper strategy instance
2. Dialog shows template config + editable overrides (position_size_pct, max_position_value)
3. Backend creates new `StrategyInstance` with `mode=live`, `promoted_from_id` pointing to paper instance
4. Paper instance unchanged
5. `strategy_promoted` event logged

### Query Scoping

- `GET /api/strategies` → returns instances for current mode only
- Template details available via `GET /api/strategies/{id}/template`
- Each instance has its own trade history, P&L, performance tracked via `Trade.strategy_instance_id`

---

## 4. Explicit Webull Account Mapping

Store discovered account IDs per user so we never guess which account to route to.

### New Model: `UserBrokerAccount`

```python
class UserBrokerAccount(Base):
    __tablename__ = "user_broker_accounts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    connection_id = Column(Integer, ForeignKey("user_api_connections.id"), nullable=False)
    broker_account_id = Column(String(128), nullable=False)  # Webull's account ID
    account_type = Column(String(32), nullable=False)        # "paper" or "live"
    nickname = Column(String(100), nullable=True)
    discovered_at = Column(DateTime, default=datetime.utcnow)
```

### Account Discovery Flow

On API connection (or re-test):
1. Webull SDK calls `get_app_subscriptions()` + `get_account_profile()` per account
2. Classify each as paper or live
3. Store in `user_broker_accounts` with explicit `account_type`
4. Log `account_sync` event

### Routing Guarantee

```python
def get_account_for_mode(user_id: int, mode: TradingModeEnum) -> str:
    """Returns the stored account ID for this user + mode. Raises if not found."""
    account = db.query(UserBrokerAccount).filter_by(
        user_id=user_id,
        account_type=mode.value,
    ).first()
    if not account:
        raise HTTPException(404, f"No {mode.value} account mapped for user")
    return account.broker_account_id
```

The trading engine calls this before every order — never relies on SDK auto-selection.

---

## 5. Live Trading Execution Safety

### New Model: `UserRiskLimits`

```python
class UserRiskLimits(Base):
    __tablename__ = "user_risk_limits"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    mode = Column(Enum(TradingModeEnum), primary_key=True)

    daily_loss_limit = Column(Float, nullable=True)        # Max $ loss per day before halt
    max_position_size_pct = Column(Float, default=0.25)    # Max % of equity per position
    max_open_positions = Column(Integer, default=10)
    kill_switch_active = Column(Boolean, default=False)    # Manual emergency halt
    live_bot_trading_confirmed = Column(Boolean, default=False)  # Must be True for live bots
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Enforcement Points

Every order goes through these checks before execution:

1. **Kill switch** — if `kill_switch_active=True`, reject immediately, log `risk_limit_triggered`
2. **Daily loss limit** — sum today's realized P&L; if limit exceeded, reject
3. **Max position size** — calculate position value as % of equity; reject if over limit
4. **Max open positions** — count open positions; reject if at limit
5. **Live bot confirmation** — if order comes from a bot and mode is live, `live_bot_trading_confirmed` must be True

### Kill Switch

- `POST /api/risk/kill-switch` — toggle on/off
- When activated: cancels all open orders, halts all bots, logs event
- Frontend shows prominent red kill switch in live mode header

### Live Bot Confirmation

First time enabling a bot in live mode shows a confirmation dialog:
> "You are about to enable automated trading with real money. This bot will place orders using your live Webull account. Are you sure?"

Sets `live_bot_trading_confirmed=True` for this user+mode after confirmation.

---

## 6. System Event Log

### New Model: `SystemEvent`

```python
class SystemEventType(str, enum.Enum):
    MODE_SWITCH = "mode_switch"
    STRATEGY_PROMOTED = "strategy_promoted"
    TRADE_EXECUTED = "trade_executed"
    TRADE_FAILED = "trade_failed"
    ACCOUNT_SYNC = "account_sync"
    RISK_LIMIT_TRIGGERED = "risk_limit_triggered"
    KILL_SWITCH_TOGGLED = "kill_switch_toggled"
    BOT_ENABLED = "bot_enabled"
    BOT_DISABLED = "bot_disabled"


class SystemEvent(Base):
    __tablename__ = "system_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_type = Column(Enum(SystemEventType), nullable=False)
    mode = Column(Enum(TradingModeEnum), nullable=False)
    severity = Column(String(16), default="info")     # info, warning, critical
    description = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### Logging Helper

```python
async def log_event(
    user_id: int,
    event_type: SystemEventType,
    mode: TradingModeEnum,
    description: str = "",
    severity: str = "info",
    metadata: dict = None,
):
    async with get_session() as db:
        db.add(SystemEvent(
            user_id=user_id,
            event_type=event_type,
            mode=mode,
            severity=severity,
            description=description,
            metadata_json=metadata or {},
        ))
        await db.commit()
```

### Event Triggers

| Event | When | Severity |
|-------|------|----------|
| `mode_switch` | User toggles paper/live | info |
| `strategy_promoted` | Strategy instance created in live from paper | info |
| `trade_executed` | Order filled successfully | info |
| `trade_failed` | Order rejected/failed | warning |
| `account_sync` | Webull account data pulled | info |
| `risk_limit_triggered` | Any risk limit blocks an action | warning |
| `kill_switch_toggled` | Kill switch on/off | critical |
| `bot_enabled` | Bot activated (especially live) | info |
| `bot_disabled` | Bot deactivated | info |

### Frontend

- Event log visible in Settings or a dedicated Activity page
- Critical events show as toast notifications
- Live mode events have a visual indicator (red dot)

---

## 7. Strict Mode Filtering on All Queries

**Every data endpoint filters by `request.state.trading_mode`.** No exceptions.

### Database Schema Changes

Add `mode` column to models that lack it:

| Model | Change |
|-------|--------|
| `CapitalAllocation` | Add `mode = Column(Enum(TradingModeEnum), nullable=False)` |
| `RiskEvent` | Add `mode = Column(Enum(TradingModeEnum), nullable=False)` |
| `TradingModel` | Add `mode = Column(Enum(TradingModeEnum), nullable=False)` |
| `PortfolioSnapshot` | Already has `mode` — just filter on it |
| `Trade` | Already has `mode` — just filter on it |
| `ModelPerformance` | Already has `mode` — just filter on it |
| `Strategy` | Replaced by `StrategyTemplate` + `StrategyInstance` |

`MarketRegimeRecord` stays mode-agnostic — market conditions are the same regardless of trading mode.

### Query Pattern

Every data query follows this pattern:

```python
@router.get("/equity-curve")
async def get_equity_curve(request: Request):
    mode = request.state.trading_mode  # Set by middleware, from DB

    async with get_session() as db:
        result = await db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.mode == mode)
            .order_by(PortfolioSnapshot.timestamp.asc())
            .limit(500)
        )
        snapshots = result.scalars().all()
    ...
```

### Endpoints That Need Mode Filtering

| Endpoint | Current | Fix |
|----------|---------|-----|
| `GET /api/dashboard/equity-curve` | No filter | Add `.where(mode == ...)` |
| `GET /api/models/list` | No filter | Add `.where(mode == ...)` |
| `GET /api/models/allocation` | No filter | Add `.where(mode == ...)` |
| `GET /api/models/performance/{name}` | No filter | Add `.where(mode == ...)` |
| `GET /api/trading/account` | Routes by client | Route by stored account mapping |
| `GET /api/trading/positions` | Routes by client | Route by stored account mapping |
| `GET /api/trading/orders` | Routes by client | Route by stored account mapping |
| `GET /api/strategies` | No filter | Query `strategy_instances` by mode |
| `GET /api/risk/events` | No filter | Add `.where(mode == ...)` |

---

## 8. Data Sync on API Connection

When Webull credentials are saved or updated:

1. **Discover accounts** — call `get_app_subscriptions()` + `get_account_profile()`
2. **Store account mapping** — save paper and live account IDs to `user_broker_accounts`
3. **Sync per mode** — for each discovered account:
   - Pull balance/equity/buying power
   - Pull open positions
   - Pull recent trade history (last 90 days)
   - Create initial `PortfolioSnapshot`
4. **Log `account_sync` event** for each mode synced
5. **Frontend progress indicator** — show sync status

Re-sync on demand via `POST /api/broker/sync`.

---

## Data Flow Summary

```
User clicks Paper/Live toggle
  → Frontend calls POST /api/user/set-mode
    → Backend stores mode in user_trading_sessions
    → Backend logs mode_switch event
    → Returns confirmed mode
  → Frontend receives confirmation
    → queryClient.clear() — purge all cached data
    → Update local state + theme
    → All components re-mount and re-fetch
      → Every GET endpoint reads request.state.trading_mode
        → Queries filter by mode
          → Webull routes to correct stored account ID
            → User sees only data for active mode
```

---

## New Database Tables Summary

| Table | Purpose |
|-------|---------|
| `user_trading_sessions` | Server-side active mode per user |
| `strategy_templates` | Mode-agnostic strategy logic definitions |
| `strategy_instances` | Mode-specific running instances of templates |
| `user_broker_accounts` | Explicitly mapped Webull paper/live account IDs |
| `user_risk_limits` | Per-user per-mode risk limits and kill switch |
| `system_events` | Audit log for all critical actions |

## Modified Tables

| Table | Change |
|-------|--------|
| `capital_allocations` | Add `mode` column |
| `risk_events` | Add `mode` column |
| `trading_models` | Add `mode` column |
| `strategies` | Migrate to `strategy_templates` + `strategy_instances` |

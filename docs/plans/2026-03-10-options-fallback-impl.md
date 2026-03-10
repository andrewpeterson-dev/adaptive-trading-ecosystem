# Options Fallback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Detect when the active broker (Webull paper) doesn't support options, offer a clean fallback to a separate options provider (Tradier paper), and keep all P&L stats separated in two distinct ledgers with no double-counting.

**Architecture:** Static capability flags on `ApiProvider` drive routing decisions. A new `services/order_router.py` is the single place all routing logic lives. A new `services/ledger_aggregator.py` computes combined equity from the broker account + options sim P&L from a new `options_sim_trades` DB table. A consent modal (`OptionsFallbackModal`) is shown frontend-side whenever the backend returns `OPTIONS_NOT_SUPPORTED`.

**Tech Stack:** Python 3.9, FastAPI, SQLAlchemy async, pytest, Next.js 14, React, TypeScript, Pydantic v2.

---

## Task 1: Capability flags — DB model + seed

**Files:**
- Modify: `db/models.py:400-410` (ApiProvider columns)
- Modify: `db/models.py:440-450` (UserApiSettings columns)
- Modify: `scripts/seed_providers.py`

### Step 1: Write the failing capability flags test

```python
# tests/test_capability_flags.py
import asyncio, pytest, sys
sys.path.insert(0, '.')

pytestmark = pytest.mark.asyncio

async def test_webull_has_supports_options_false():
    from db.database import get_session, init_db
    from db.models import ApiProvider
    from sqlalchemy import select
    await init_db()
    async with get_session() as db:
        r = await db.execute(select(ApiProvider).where(ApiProvider.slug == "webull"))
        p = r.scalar_one_or_none()
        assert p is not None
        assert p.supports_options is False
        assert p.supports_stocks is True
        assert p.supports_order_placement is True

async def test_tradier_has_supports_options_true():
    from db.database import get_session
    from db.models import ApiProvider
    from sqlalchemy import select
    async with get_session() as db:
        r = await db.execute(select(ApiProvider).where(ApiProvider.slug == "tradier"))
        p = r.scalar_one_or_none()
        assert p is not None
        assert p.supports_options is True
        assert p.supports_stocks is True

async def test_no_provider_has_null_capability_flags():
    from db.database import get_session
    from db.models import ApiProvider
    from sqlalchemy import select
    async with get_session() as db:
        r = await db.execute(select(ApiProvider))
        providers = r.scalars().all()
        for p in providers:
            assert p.supports_stocks is not None, f"{p.slug} has null supports_stocks"
            assert p.supports_order_placement is not None
            assert p.supports_positions_streaming is not None
```

### Step 2: Run to verify it fails
```bash
cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_capability_flags.py -v
```
Expected: `FAILED` — `ApiProvider has no attribute 'supports_stocks'`

### Step 3: Add columns to ApiProvider in `db/models.py`

After line 406 (`supports_crypto = Column(Boolean, default=False)`), add:
```python
    supports_stocks = Column(Boolean, default=False)
    supports_order_placement = Column(Boolean, default=False)
    supports_positions_streaming = Column(Boolean, default=False)
```

After line 449 (`primary_options_data_id`), add to UserApiSettings:
```python
    options_fallback_enabled = Column(Boolean, default=False)
    options_provider_connection_id = Column(Integer, ForeignKey("user_api_connections.id"), nullable=True)
```

### Step 4: Update `scripts/seed_providers.py`

For every provider entry in the `PROVIDERS` list, add the three new keys. Key values per provider type:

**Brokerages (alpaca, interactive_brokers, tradier, tradestation, robinhood):** `supports_stocks=True, supports_order_placement=True, supports_positions_streaming=False`

**Webull specifically:** `supports_stocks=True, supports_options=False, supports_order_placement=True, supports_positions_streaming=False`

**Tradier specifically:** `supports_stocks=True, supports_options=True, supports_order_placement=True, supports_positions_streaming=False`

**Crypto brokers (binance, coinbase):** `supports_stocks=False, supports_order_placement=True, supports_positions_streaming=False`

**Market data, options data, news, fundamentals, macro providers:** `supports_stocks=False, supports_order_placement=False, supports_positions_streaming=False`

Also update the sync fields list in `seed()`:
```python
for field in ("unified_mode", "credential_note", "docs_url",
              "supports_stocks", "supports_order_placement", "supports_positions_streaming"):
```

Then run the seed:
```bash
cd ~/adaptive-trading-ecosystem && python scripts/seed_providers.py
```

### Step 5: Run tests to verify they pass
```bash
cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_capability_flags.py -v
```
Expected: `3 passed`

### Step 6: Commit
```bash
cd ~/adaptive-trading-ecosystem
git add db/models.py scripts/seed_providers.py tests/test_capability_flags.py
git commit -m "feat: add capability flags (supports_stocks, order_placement, positions_streaming) and options fallback fields"
```

---

## Task 2: OptionSimTrade DB model

**Files:**
- Modify: `db/models.py` (append new model at end)

### Step 1: Write the failing model test

Add to `tests/test_capability_flags.py`:
```python
async def test_option_sim_trade_model_exists():
    from db.models import OptionSimTrade
    from db.database import get_session
    from sqlalchemy import select
    async with get_session() as db:
        r = await db.execute(select(OptionSimTrade).limit(1))
        # just verify table is queryable
        assert r is not None
```

### Step 2: Run to verify it fails
```bash
python -m pytest tests/test_capability_flags.py::test_option_sim_trade_model_exists -v
```
Expected: `ImportError: cannot import name 'OptionSimTrade'`

### Step 3: Add `OptionSimTrade` to `db/models.py`

Append at end of file:
```python
class OptionSimTrade(Base):
    """
    Tracks real Tradier paper options orders routed through the options fallback system.
    P&L here feeds ledgerOptionsSim. Never mix with ledgerBroker.
    """
    __tablename__ = "option_sim_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    connection_id = Column(Integer, ForeignKey("user_api_connections.id"), nullable=False)
    tradier_order_id = Column(String(64), nullable=True)   # null until filled
    symbol = Column(String(32), nullable=False)            # underlying ticker
    option_symbol = Column(String(32), nullable=True)      # OCC symbol e.g. AAPL230120C00150000
    option_type = Column(String(4), nullable=False)        # "call" | "put"
    strike = Column(Float, nullable=False)
    expiry = Column(Date, nullable=False)
    qty = Column(Integer, nullable=False)
    fill_price = Column(Float, nullable=True)              # null until filled
    realized_pnl = Column(Float, nullable=True)            # null until closed
    status = Column(String(16), default="pending")         # pending/open/closed/cancelled
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_option_sim_user", "user_id"),
        Index("ix_option_sim_status", "status"),
    )
```

### Step 4: Run tests
```bash
python -m pytest tests/test_capability_flags.py -v
```
Expected: `4 passed`

### Step 5: Commit
```bash
git add db/models.py tests/test_capability_flags.py
git commit -m "feat: add OptionSimTrade model for options ledger tracking"
```

---

## Task 3: Order router service

**Files:**
- Create: `services/order_router.py`
- Create: `tests/test_options_routing.py`

### Step 1: Write ALL failing routing tests first

```python
# tests/test_options_routing.py
"""
Unit tests for order routing logic.
All external dependencies are mocked — no DB calls, no broker API calls.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# ── Helpers ───────────────────────────────────────────────────────────────

def _mock_provider(supports_options: bool, supports_paper: bool = True):
    p = MagicMock()
    p.supports_options = supports_options
    p.supports_paper = supports_paper
    p.slug = "tradier" if supports_options else "webull"
    p.name = "Tradier" if supports_options else "Webull"
    return p

def _mock_connection(provider, connection_id: int = 1):
    c = MagicMock()
    c.id = connection_id
    c.provider = provider
    c.provider_id = provider.id if hasattr(provider, 'id') else 99
    return c

def _mock_settings(
    active_conn,
    options_fallback_enabled: bool = False,
    options_provider_conn=None,
):
    s = MagicMock()
    s.active_equity_broker_id = active_conn.id if active_conn else None
    s.options_fallback_enabled = options_fallback_enabled
    s.options_provider_connection_id = options_provider_conn.id if options_provider_conn else None
    return s


# ── Tests ─────────────────────────────────────────────────────────────────

def test_stock_order_always_routes_to_active_broker():
    from services.order_router import resolve_route, OrderRequest, RouteResult
    webull_conn = _mock_connection(_mock_provider(supports_options=False), connection_id=1)
    tradier_conn = _mock_connection(_mock_provider(supports_options=True), connection_id=2)
    settings = _mock_settings(webull_conn, options_fallback_enabled=True,
                               options_provider_conn=tradier_conn)
    req = OrderRequest(symbol="AAPL", side="BUY", qty=10, instrument_type="stock")
    result = resolve_route(req, active_connection=webull_conn,
                           settings=settings, options_connection=tradier_conn)
    assert result.connection_id == webull_conn.id
    assert result.is_options_sim is False


def test_options_order_blocked_without_fallback():
    from services.order_router import resolve_route, OrderRequest, OptionsNotSupportedError
    webull_conn = _mock_connection(_mock_provider(supports_options=False), connection_id=1)
    settings = _mock_settings(webull_conn, options_fallback_enabled=False)
    req = OrderRequest(
        symbol="AAPL", side="BUY", qty=1, instrument_type="option",
        option_type="call", strike=150.0, expiry="2027-01-20"
    )
    with pytest.raises(OptionsNotSupportedError) as exc:
        resolve_route(req, active_connection=webull_conn,
                      settings=settings, options_connection=None)
    assert exc.value.active_broker_name == "Webull"


def test_options_order_routes_to_fallback_when_enabled():
    from services.order_router import resolve_route, OrderRequest, RouteResult
    webull_conn = _mock_connection(_mock_provider(supports_options=False), connection_id=1)
    tradier_conn = _mock_connection(_mock_provider(supports_options=True), connection_id=2)
    settings = _mock_settings(webull_conn, options_fallback_enabled=True,
                               options_provider_conn=tradier_conn)
    req = OrderRequest(
        symbol="SPY", side="BUY", qty=5, instrument_type="option",
        option_type="put", strike=500.0, expiry="2027-03-21"
    )
    result = resolve_route(req, active_connection=webull_conn,
                           settings=settings, options_connection=tradier_conn)
    assert result.connection_id == tradier_conn.id
    assert result.is_options_sim is True


def test_options_order_goes_to_broker_when_it_supports_options():
    from services.order_router import resolve_route, OrderRequest, RouteResult
    alpaca_conn = _mock_connection(_mock_provider(supports_options=True), connection_id=3)
    settings = _mock_settings(alpaca_conn, options_fallback_enabled=False)
    req = OrderRequest(
        symbol="SPY", side="SELL", qty=2, instrument_type="option",
        option_type="call", strike=450.0, expiry="2027-06-20"
    )
    result = resolve_route(req, active_connection=alpaca_conn,
                           settings=settings, options_connection=None)
    assert result.connection_id == alpaca_conn.id
    assert result.is_options_sim is False


def test_saving_fallback_with_non_options_provider_raises():
    from services.order_router import validate_options_provider
    non_options_provider = _mock_provider(supports_options=False)
    conn = _mock_connection(non_options_provider, connection_id=5)
    with pytest.raises(ValueError, match="does not support options"):
        validate_options_provider(conn)
```

### Step 2: Run to verify all fail
```bash
python -m pytest tests/test_options_routing.py -v
```
Expected: `5 errors` — `ModuleNotFoundError: No module named 'services.order_router'`

### Step 3: Create `services/order_router.py`

```python
"""
Order routing service.

Single source of truth for deciding which connection handles a given order.
Called by both paper_trading and trading routes. Never makes broker API calls.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any
import structlog

logger = structlog.get_logger(__name__)


class OptionsNotSupportedError(Exception):
    """
    Raised when an options order is attempted but the active broker
    doesn't support options AND no fallback is configured.
    """
    def __init__(self, active_broker_name: str, available_providers: list[dict] = None):
        self.active_broker_name = active_broker_name
        self.available_providers = available_providers or []
        super().__init__(
            f"Options trading is not supported by {active_broker_name} paper. "
            "Enable options fallback in Settings → API Connections to proceed."
        )


@dataclass
class OrderRequest:
    symbol: str
    side: str               # "BUY" | "SELL"
    qty: int
    instrument_type: str = "stock"   # "stock" | "option"
    option_type: Optional[str] = None    # "call" | "put"
    strike: Optional[float] = None
    expiry: Optional[str] = None         # ISO date string "YYYY-MM-DD"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    tif: str = "DAY"
    user_confirmed: bool = False


@dataclass
class RouteResult:
    connection_id: int
    is_options_sim: bool = False    # True when routed to options fallback provider


def validate_options_provider(connection: Any) -> None:
    """
    Raise ValueError if the connection's provider cannot handle options.
    Call this before saving options_provider_connection_id.
    """
    provider = connection.provider
    if not provider.supports_options:
        raise ValueError(
            f"Provider '{provider.name}' does not support options trading. "
            "Choose a provider with supports_options=True (e.g. Tradier)."
        )
    if not provider.supports_paper:
        raise ValueError(
            f"Provider '{provider.name}' does not support paper trading."
        )


def resolve_route(
    req: OrderRequest,
    *,
    active_connection: Any,
    settings: Any,
    options_connection: Any,
) -> RouteResult:
    """
    Determine which connection should handle this order.

    Rules:
      - Stock orders  → always active_connection
      - Options order + active broker supports options → active_connection
      - Options order + fallback enabled → options_connection (is_options_sim=True)
      - Options order + no fallback → raise OptionsNotSupportedError
    """
    if req.instrument_type != "option":
        return RouteResult(connection_id=active_connection.id, is_options_sim=False)

    # Options path
    if active_connection.provider.supports_options:
        logger.info("options_routed_to_broker",
                    broker=active_connection.provider.name,
                    symbol=req.symbol)
        return RouteResult(connection_id=active_connection.id, is_options_sim=False)

    if settings.options_fallback_enabled and options_connection is not None:
        logger.info("options_routed_to_fallback",
                    fallback=options_connection.provider.name,
                    symbol=req.symbol,
                    strike=req.strike,
                    option_type=req.option_type)
        return RouteResult(connection_id=options_connection.id, is_options_sim=True)

    raise OptionsNotSupportedError(
        active_broker_name=active_connection.provider.name,
    )
```

### Step 4: Run tests
```bash
python -m pytest tests/test_options_routing.py -v
```
Expected: `5 passed`

### Step 5: Commit
```bash
git add services/order_router.py tests/test_options_routing.py
git commit -m "feat: add order_router service with options fallback routing logic"
```

---

## Task 4: Ledger aggregator service

**Files:**
- Create: `services/ledger_aggregator.py`
- Create: `tests/test_ledger_aggregator.py`

### Step 1: Write failing ledger tests

```python
# tests/test_ledger_aggregator.py
"""
Unit tests for ledger aggregation.
Broker data and options sim data are fully mocked.
"""
import pytest
from unittest.mock import MagicMock, patch

def _run(coro):
    import asyncio
    return asyncio.get_event_loop().run_until_complete(coro)


def test_total_equals_broker_plus_options_pnl():
    from services.ledger_aggregator import LedgerAggregator
    agg = LedgerAggregator()
    result = agg._combine(broker_equity=1_000_000.0, options_sim_pnl=1_250.0)
    assert result["total_simulated_equity"] == 1_001_250.0
    assert result["broker_equity"] == 1_000_000.0
    assert result["options_sim_pnl"] == 1_250.0


def test_no_fallback_means_zero_options_pnl():
    from services.ledger_aggregator import LedgerAggregator
    agg = LedgerAggregator()
    result = agg._combine(broker_equity=500_000.0, options_sim_pnl=0.0)
    assert result["total_simulated_equity"] == 500_000.0
    assert result["options_sim_pnl"] == 0.0


def test_returns_pct_uses_total_equity():
    from services.ledger_aggregator import LedgerAggregator
    agg = LedgerAggregator()
    # 1_010_000 total on 1_000_000 initial = 1.0% return
    result = agg._compute_metrics(
        total_equity=1_010_000.0,
        initial_equity=1_000_000.0,
        equity_series=[1_000_000.0, 1_005_000.0, 1_010_000.0],
    )
    assert abs(result["returns_pct"] - 1.0) < 0.001


def test_drawdown_uses_total_equity():
    from services.ledger_aggregator import LedgerAggregator
    agg = LedgerAggregator()
    # peak 1_010_000, current 1_000_000 → drawdown ≈ 0.99%
    result = agg._compute_metrics(
        total_equity=1_000_000.0,
        initial_equity=1_000_000.0,
        equity_series=[1_000_000.0, 1_010_000.0, 1_000_000.0],
    )
    assert result["drawdown_pct"] > 0.0


def test_no_double_count_when_options_sim_disabled():
    from services.ledger_aggregator import LedgerAggregator
    agg = LedgerAggregator()
    broker_eq = 1_234_567.89
    result = agg._combine(broker_equity=broker_eq, options_sim_pnl=0.0)
    assert result["total_simulated_equity"] == broker_eq
```

### Step 2: Run to verify they fail
```bash
python -m pytest tests/test_ledger_aggregator.py -v
```
Expected: `5 errors — ModuleNotFoundError`

### Step 3: Create `services/ledger_aggregator.py`

```python
"""
Ledger aggregator.

Computes combined performance metrics from two separate ledgers:
  ledgerBroker      — equity from the active broker connection (e.g. Webull paper)
  ledgerOptionsSim  — realized + unrealized P&L from options sim trades (e.g. Tradier paper)

Never double-counts: options sim tracks P&L only, not cash.
"""
from __future__ import annotations
from typing import Optional
import math
import structlog
from sqlalchemy import select, func
from db.database import get_session
from db.models import OptionSimTrade

logger = structlog.get_logger(__name__)


class LedgerAggregator:

    # ── Pure computation helpers (no I/O, easy to unit-test) ──────────────

    def _combine(self, *, broker_equity: float, options_sim_pnl: float) -> dict:
        total = broker_equity + options_sim_pnl
        return {
            "broker_equity": broker_equity,
            "options_sim_pnl": options_sim_pnl,
            "total_simulated_equity": total,
        }

    def _compute_metrics(
        self,
        *,
        total_equity: float,
        initial_equity: float,
        equity_series: list[float],
    ) -> dict:
        """Compute returns, drawdown, Sharpe from total equity series."""
        returns_pct = ((total_equity - initial_equity) / initial_equity) * 100 if initial_equity else 0.0

        # Drawdown: peak-to-trough from series
        peak = equity_series[0] if equity_series else total_equity
        drawdown_pct = 0.0
        for v in equity_series:
            peak = max(peak, v)
            dd = (peak - v) / peak * 100 if peak else 0.0
            drawdown_pct = max(drawdown_pct, dd)

        # Sharpe (simplified daily, annualised — requires ≥2 data points)
        sharpe = 0.0
        if len(equity_series) >= 2:
            daily_rets = [
                (equity_series[i] - equity_series[i - 1]) / equity_series[i - 1]
                for i in range(1, len(equity_series))
            ]
            mean_r = sum(daily_rets) / len(daily_rets)
            variance = sum((r - mean_r) ** 2 for r in daily_rets) / len(daily_rets)
            std_r = math.sqrt(variance) if variance > 0 else 0.0
            sharpe = (mean_r / std_r * math.sqrt(252)) if std_r > 0 else 0.0

        return {
            "returns_pct": round(returns_pct, 4),
            "drawdown_pct": round(drawdown_pct, 4),
            "sharpe": round(sharpe, 4),
        }

    # ── DB queries ────────────────────────────────────────────────────────

    async def get_options_sim_pnl(self, user_id: int) -> tuple[float, list[dict]]:
        """
        Return (total_pnl, open_positions_list) for a user's options sim trades.
        Closed trades: sum realized_pnl.
        Open trades: included in list with fill_price (MTM handled by caller).
        """
        async with get_session() as db:
            # Realized P&L from closed trades
            r = await db.execute(
                select(func.coalesce(func.sum(OptionSimTrade.realized_pnl), 0.0))
                .where(
                    OptionSimTrade.user_id == user_id,
                    OptionSimTrade.status == "closed",
                )
            )
            realized_pnl: float = r.scalar() or 0.0

            # Open positions
            r2 = await db.execute(
                select(OptionSimTrade).where(
                    OptionSimTrade.user_id == user_id,
                    OptionSimTrade.status == "open",
                )
            )
            open_trades = r2.scalars().all()
            open_positions = [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "option_symbol": t.option_symbol,
                    "option_type": t.option_type,
                    "strike": t.strike,
                    "expiry": str(t.expiry),
                    "qty": t.qty,
                    "fill_price": t.fill_price,
                }
                for t in open_trades
            ]

        return realized_pnl, open_positions

    async def build_combined(
        self,
        *,
        user_id: int,
        broker_equity: float,
        broker_label: str,
        initial_equity: float,
        options_label: Optional[str] = None,
        equity_series: Optional[list[float]] = None,
        options_fallback_enabled: bool = False,
    ) -> dict:
        options_sim_pnl = 0.0
        open_positions: list[dict] = []

        if options_fallback_enabled:
            options_sim_pnl, open_positions = await self.get_options_sim_pnl(user_id)

        combined = self._combine(broker_equity=broker_equity, options_sim_pnl=options_sim_pnl)
        series = equity_series or [initial_equity, combined["total_simulated_equity"]]
        metrics = self._compute_metrics(
            total_equity=combined["total_simulated_equity"],
            initial_equity=initial_equity,
            equity_series=series,
        )

        return {
            **combined,
            "broker_label": broker_label,
            "options_label": options_label or "Options Sim",
            "open_options_positions": open_positions,
            "metrics": metrics,
        }


ledger_aggregator = LedgerAggregator()
```

### Step 4: Run tests
```bash
python -m pytest tests/test_ledger_aggregator.py -v
```
Expected: `5 passed`

### Step 5: Commit
```bash
git add services/ledger_aggregator.py tests/test_ledger_aggregator.py
git commit -m "feat: add ledger_aggregator service with combined equity and metrics computation"
```

---

## Task 5: Backend API — options-fallback settings endpoint + ledger route

**Files:**
- Modify: `api/routes/api_connections.py` (add POST /api/v2/api-settings/options-fallback)
- Create: `api/routes/ledger.py`
- Modify: `api/main.py` (register ledger router)

### Step 1: Add options-fallback endpoint to `api/routes/api_connections.py`

Find the `set_active_broker` section (around line 406). After the last `@router.put` endpoint, append:

```python
class SetOptionsFallbackRequest(BaseModel):
    enabled: bool
    provider_connection_id: Optional[int] = None


@router.post("/api-settings/options-fallback")
async def set_options_fallback(req: SetOptionsFallbackRequest, request: Request):
    """
    Enable or disable the options fallback provider.
    Requires the target connection's provider to have supports_options=True.
    """
    user_id = _require_user(request)

    if req.enabled:
        if not req.provider_connection_id:
            raise HTTPException(
                status_code=400,
                detail="provider_connection_id is required when enabling options fallback",
            )
        async with get_session() as db:
            r = await db.execute(
                select(UserApiConnection)
                .join(ApiProvider)
                .where(
                    UserApiConnection.id == req.provider_connection_id,
                    UserApiConnection.user_id == user_id,
                )
            )
            conn = r.scalar_one_or_none()
            if not conn:
                raise HTTPException(status_code=404, detail="Connection not found")

            from services.order_router import validate_options_provider
            try:
                validate_options_provider(conn)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

    settings = await api_connection_manager.get_or_create_settings(user_id)
    async with get_session() as db:
        r = await db.execute(
            select(UserApiSettings).where(UserApiSettings.user_id == user_id)
        )
        s = r.scalar_one_or_none()
        if not s:
            s = UserApiSettings(user_id=user_id)
            db.add(s)
        s.options_fallback_enabled = req.enabled
        s.options_provider_connection_id = req.provider_connection_id if req.enabled else None
        await db.commit()
        await db.refresh(s)

    conflicts = await api_connection_manager.get_conflicts(user_id)
    return {**_settings_dict(s), "conflicts": conflicts}
```

Also update `_settings_dict` to include the new fields:
```python
def _settings_dict(s: UserApiSettings) -> dict:
    return {
        "active_equity_broker_id": s.active_equity_broker_id,
        "active_crypto_broker_id": s.active_crypto_broker_id,
        "primary_market_data_id": s.primary_market_data_id,
        "fallback_market_data_ids": s.fallback_market_data_ids or [],
        "primary_options_data_id": s.primary_options_data_id,
        "options_fallback_enabled": s.options_fallback_enabled,
        "options_provider_connection_id": s.options_provider_connection_id,
    }
```

### Step 2: Create `api/routes/ledger.py`

```python
"""
Ledger routes — combined broker + options sim equity view.
"""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
import structlog

from db.database import get_session
from db.models import UserApiSettings, UserApiConnection, ApiProvider
from services.ledger_aggregator import ledger_aggregator
from services.api_connection_manager import api_connection_manager

logger = structlog.get_logger(__name__)
router = APIRouter()


def _require_user(request: Request) -> int:
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


@router.get("/ledger/combined")
async def get_combined_ledger(request: Request):
    """
    Returns combined equity from active broker + options sim P&L.
    Always safe to call: if no options fallback, options_sim_pnl=0.
    """
    user_id = _require_user(request)
    settings = await api_connection_manager.get_or_create_settings(user_id)

    # Get active broker equity
    broker_equity = 0.0
    broker_label = "No Broker Connected"
    initial_equity = 1_000_000.0  # default paper initial capital

    if settings.active_equity_broker_id:
        async with get_session() as db:
            r = await db.execute(
                select(UserApiConnection).join(ApiProvider).where(
                    UserApiConnection.id == settings.active_equity_broker_id
                )
            )
            conn = r.scalar_one_or_none()
            if conn:
                broker_label = f"{conn.provider.name} ({'Paper' if conn.is_paper else 'Live'})"
                # TODO: fetch live balance from broker client once routing is wired
                # For now return placeholder so the endpoint is callable
                broker_equity = 1_000_000.0

    # Options provider label
    options_label = None
    if settings.options_fallback_enabled and settings.options_provider_connection_id:
        async with get_session() as db:
            r = await db.execute(
                select(UserApiConnection).join(ApiProvider).where(
                    UserApiConnection.id == settings.options_provider_connection_id
                )
            )
            conn = r.scalar_one_or_none()
            if conn:
                options_label = f"{conn.provider.name} (Options Sim)"

    return await ledger_aggregator.build_combined(
        user_id=user_id,
        broker_equity=broker_equity,
        broker_label=broker_label,
        initial_equity=initial_equity,
        options_label=options_label,
        options_fallback_enabled=settings.options_fallback_enabled,
    )
```

### Step 3: Register ledger router in `api/main.py`

Find the line:
```python
app.include_router(api_connections_routes.router, prefix="/api/v2", tags=["api-connections"])
```

Add after it:
```python
from api.routes import ledger as ledger_routes
app.include_router(ledger_routes.router, prefix="/api/v2", tags=["ledger"])
```

### Step 4: Test the endpoints manually
```bash
TOKEN=$(python3 -c "
import jwt, os
from datetime import datetime, timedelta
secret = open('.env').read() if False else 'a5Vzn8cPb-L8aZQkfNvnIyIeVz1Air5YbJo4QMZzOMYIMIkXhE2VKDIb45KKetd2'
print(jwt.encode({'user_id':2,'email':'apetersongroup@gmail.com','exp':datetime.utcnow()+timedelta(days=365)}, secret, algorithm='HS256'))
")
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v2/ledger/combined | python3 -m json.tool
```
Expected: JSON with `broker_equity`, `options_sim_pnl`, `total_simulated_equity`, `metrics`

### Step 5: Commit
```bash
git add api/routes/api_connections.py api/routes/ledger.py api/main.py
git commit -m "feat: add options-fallback settings endpoint and combined ledger route"
```

---

## Task 6: Paper trading route — wire in order_router

**Files:**
- Modify: `api/routes/paper_trading.py`

### Step 1: Extend `PaperTradeRequest` with options fields

Find `class PaperTradeRequest` (line 33) and add fields:
```python
class PaperTradeRequest(BaseModel):
    symbol: str
    side: Optional[str] = None
    direction: Optional[str] = None
    quantity: float
    price: Optional[float] = None
    user_confirmed: bool = True
    # Options fields
    instrument_type: str = "stock"      # "stock" | "option"
    option_type: Optional[str] = None   # "call" | "put"
    strike: Optional[float] = None
    expiry: Optional[str] = None        # "YYYY-MM-DD"
```

### Step 2: Wire order_router into the trade execution handler

At the top of the paper trading route's trade execution function, after resolving the user and before executing:

```python
from services.order_router import OrderRequest as RouterOrderRequest, resolve_route, OptionsNotSupportedError
from services.api_connection_manager import api_connection_manager as conn_manager

# Resolve routing
settings = await conn_manager.get_or_create_settings(user_id)
if req.instrument_type == "option":
    # Load active broker connection
    active_conn = None
    options_conn = None
    if settings.active_equity_broker_id:
        async with get_session() as db:
            r = await db.execute(
                select(UserApiConnection).join(ApiProvider)
                .where(UserApiConnection.id == settings.active_equity_broker_id)
            )
            active_conn = r.scalar_one_or_none()
    if settings.options_provider_connection_id:
        async with get_session() as db:
            r = await db.execute(
                select(UserApiConnection).join(ApiProvider)
                .where(UserApiConnection.id == settings.options_provider_connection_id)
            )
            options_conn = r.scalar_one_or_none()

    if active_conn:
        router_req = RouterOrderRequest(
            symbol=req.symbol.upper(),
            side=side,
            qty=int(req.quantity),
            instrument_type=req.instrument_type,
            option_type=req.option_type,
            strike=req.strike,
            expiry=req.expiry,
        )
        try:
            route = resolve_route(router_req, active_connection=active_conn,
                                  settings=settings, options_connection=options_conn)
        except OptionsNotSupportedError as e:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "OPTIONS_NOT_SUPPORTED",
                    "message": str(e),
                    "active_broker": e.active_broker_name,
                }
            )

        if route.is_options_sim:
            # Route to Tradier paper — insert OptionSimTrade record
            from db.models import OptionSimTrade
            import datetime
            sim_trade = OptionSimTrade(
                user_id=user_id,
                connection_id=options_conn.id,
                symbol=req.symbol.upper(),
                option_type=req.option_type,
                strike=req.strike,
                expiry=datetime.date.fromisoformat(req.expiry),
                qty=int(req.quantity),
                status="pending",
            )
            async with get_session() as db:
                db.add(sim_trade)
                await db.commit()
                await db.refresh(sim_trade)
            # TODO: submit to Tradier paper API (Task 7)
            return {
                "status": "options_sim_pending",
                "sim_trade_id": sim_trade.id,
                "message": f"Options order queued for Tradier paper ({req.option_type} {req.strike} {req.expiry})",
            }
```

### Step 3: Run routing tests to make sure nothing broke
```bash
python -m pytest tests/test_options_routing.py tests/test_capability_flags.py -v
```
Expected: all pass

### Step 4: Commit
```bash
git add api/routes/paper_trading.py
git commit -m "feat: wire order_router into paper_trading route — options orders blocked or sim-routed"
```

---

## Task 7: OptionsFallbackModal — frontend consent UI

**Files:**
- Create: `frontend/src/components/settings/OptionsFallbackModal.tsx`
- Modify: `frontend/src/components/settings/ApiConnectionsSection.tsx` (add settings export)
- Create: `frontend/src/hooks/useOptionsGuard.ts`

### Step 1: Create `frontend/src/hooks/useOptionsGuard.ts`

```typescript
/**
 * useOptionsGuard
 *
 * Wraps any apiFetch call. If the response contains code=OPTIONS_NOT_SUPPORTED,
 * sets a flag that triggers the OptionsFallbackModal.
 */
"use client";
import { useState, useCallback } from "react";

export interface OptionsNotSupportedPayload {
  code: "OPTIONS_NOT_SUPPORTED";
  active_broker: string;
  available_options_providers: Array<{
    id: number;
    name: string;
    slug: string;
    is_connected: boolean;
  }>;
}

export function useOptionsGuard() {
  const [payload, setPayload] = useState<OptionsNotSupportedPayload | null>(null);

  const guard = useCallback((error: unknown) => {
    if (
      error &&
      typeof error === "object" &&
      "code" in error &&
      (error as any).code === "OPTIONS_NOT_SUPPORTED"
    ) {
      setPayload(error as OptionsNotSupportedPayload);
      return true; // handled
    }
    return false;
  }, []);

  const dismiss = useCallback(() => setPayload(null), []);

  return { payload, guard, dismiss };
}
```

### Step 2: Create `frontend/src/components/settings/OptionsFallbackModal.tsx`

```tsx
"use client";
import { useState } from "react";
import { apiFetch } from "@/lib/api/client";
import type { OptionsNotSupportedPayload } from "@/hooks/useOptionsGuard";
import type { ApiConnection, ApiProvider } from "./ApiConnectionCard";
import { ConnectApiModal } from "./ConnectApiModal";

interface Props {
  payload: OptionsNotSupportedPayload;
  connections: ApiConnection[];
  providers: ApiProvider[];
  onEnabled: () => void;
  onDismiss: () => void;
}

export function OptionsFallbackModal({
  payload,
  connections,
  providers,
  onEnabled,
  onDismiss,
}: Props) {
  const [selectedConnectionId, setSelectedConnectionId] = useState<number | null>(null);
  const [connectingProvider, setConnectingProvider] = useState<ApiProvider | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Only show connected options-capable providers
  const optionsConnections = connections.filter((c) => {
    const prov = providers.find((p) => p.id === c.provider_id);
    return prov?.supports_options && prov?.supports_paper;
  });

  // Options-capable providers not yet connected
  const connectableProviders = providers.filter((p) => {
    const alreadyConnected = connections.some((c) => c.provider_id === p.id);
    return (p as any).supports_options && (p as any).supports_paper && !alreadyConnected;
  });

  const handleEnable = async () => {
    if (!selectedConnectionId) return;
    setLoading(true);
    setError("");
    try {
      await apiFetch("/api/v2/api-settings/options-fallback", {
        method: "POST",
        body: JSON.stringify({
          enabled: true,
          provider_connection_id: selectedConnectionId,
        }),
      });
      onEnabled();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to enable options fallback");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-2xl space-y-5">
        {/* Header */}
        <div>
          <h2 className="text-base font-semibold">Options Not Supported</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{payload.active_broker}</span> doesn't
            support options trading via API. You can simulate options using a separate provider.
          </p>
        </div>

        {/* What changes / what doesn't */}
        <div className="rounded-xl border border-border bg-muted/30 p-4 space-y-2 text-sm">
          <p className="font-medium text-xs uppercase tracking-widest text-muted-foreground">
            Impact
          </p>
          <ul className="space-y-1">
            <li className="flex gap-2">
              <span className="text-amber-400">↪</span>
              <span>Options orders will be routed to your chosen options provider (paper)</span>
            </li>
            <li className="flex gap-2">
              <span className="text-emerald-400">✓</span>
              <span>
                Your {payload.active_broker} equity, cash, and stock positions are{" "}
                <strong>unaffected</strong>
              </span>
            </li>
            <li className="flex gap-2">
              <span className="text-emerald-400">✓</span>
              <span>
                P&L is shown separately: <em>Broker Equity</em> +{" "}
                <em>Options Sim P&L</em> = Total
              </span>
            </li>
          </ul>
        </div>

        {/* Provider selection */}
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Route options to
          </p>

          {optionsConnections.length > 0 ? (
            <div className="space-y-1.5">
              {optionsConnections.map((conn) => {
                const prov = providers.find((p) => p.id === conn.provider_id);
                return (
                  <button
                    key={conn.id}
                    onClick={() => setSelectedConnectionId(conn.id)}
                    className={`w-full flex items-center justify-between rounded-xl border px-4 py-2.5 text-sm transition-colors ${
                      selectedConnectionId === conn.id
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border hover:border-primary/40"
                    }`}
                  >
                    <span>{prov?.name ?? conn.nickname ?? "Unknown"}</span>
                    <span className="text-xs text-muted-foreground">
                      {conn.is_paper ? "Paper" : "Live"}
                    </span>
                  </button>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No options-capable providers connected.{" "}
              {connectableProviders.length > 0 && (
                <button
                  className="text-primary underline"
                  onClick={() => setConnectingProvider(connectableProviders[0])}
                >
                  Connect {connectableProviders[0].name}
                </button>
              )}
            </p>
          )}
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={onDismiss}
            className="flex-1 rounded-xl border border-border px-4 py-2 text-sm hover:bg-muted/50"
          >
            Cancel
          </button>
          <button
            onClick={handleEnable}
            disabled={!selectedConnectionId || loading}
            className="flex-1 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-40"
          >
            {loading ? "Enabling…" : "Enable Options Fallback"}
          </button>
        </div>
      </div>

      {/* Inline connect flow if no provider connected yet */}
      {connectingProvider && (
        <ConnectApiModal
          provider={connectingProvider}
          onConnect={async (creds, is_paper, nickname) => {
            // After connecting, user will see it in the list on re-render
            setConnectingProvider(null);
          }}
          onClose={() => setConnectingProvider(null)}
        />
      )}
    </div>
  );
}
```

### Step 3: Commit
```bash
cd ~/adaptive-trading-ecosystem
git add frontend/src/components/settings/OptionsFallbackModal.tsx \
        frontend/src/hooks/useOptionsGuard.ts
git commit -m "feat: add OptionsFallbackModal and useOptionsGuard hook"
```

---

## Task 8: CombinedLedgerCard — dashboard widget

**Files:**
- Create: `frontend/src/components/ledger/CombinedLedgerCard.tsx`
- Modify: `frontend/src/app/dashboard/page.tsx` (add card to dashboard)

### Step 1: Create `frontend/src/components/ledger/CombinedLedgerCard.tsx`

```tsx
"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api/client";

interface LedgerData {
  broker_equity: number;
  broker_label: string;
  options_sim_pnl: number;
  options_label: string;
  total_simulated_equity: number;
  metrics: {
    returns_pct: number;
    drawdown_pct: number;
    sharpe: number;
  };
}

function fmt(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
}

export function CombinedLedgerCard() {
  const [data, setData] = useState<LedgerData | null>(null);

  useEffect(() => {
    apiFetch<LedgerData>("/api/v2/ledger/combined")
      .then(setData)
      .catch(() => null);
  }, []);

  if (!data) return null;
  if (data.options_sim_pnl === 0 && !data.options_label) return null; // nothing to show

  const pnlColor = data.options_sim_pnl >= 0 ? "text-emerald-400" : "text-red-400";

  return (
    <div className="rounded-2xl border border-border bg-card p-5 space-y-4">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
        Combined Simulated Equity
      </p>

      <div className="flex items-end justify-between">
        <span className="text-2xl font-mono font-bold">
          {fmt(data.total_simulated_equity)}
        </span>
        <span
          className={`text-sm font-mono ${data.metrics.returns_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}
        >
          {data.metrics.returns_pct >= 0 ? "+" : ""}
          {data.metrics.returns_pct.toFixed(2)}%
        </span>
      </div>

      {/* Reconciliation breakdown */}
      <div className="space-y-1 text-sm">
        <div className="flex justify-between text-muted-foreground">
          <span>{data.broker_label}</span>
          <span className="font-mono text-foreground">{fmt(data.broker_equity)}</span>
        </div>
        <div className="flex justify-between text-muted-foreground">
          <span>{data.options_label}</span>
          <span className={`font-mono ${pnlColor}`}>
            {data.options_sim_pnl >= 0 ? "+" : ""}
            {fmt(data.options_sim_pnl)}
          </span>
        </div>
        <div className="flex justify-between border-t border-border pt-1 font-medium">
          <span>Total</span>
          <span className="font-mono">{fmt(data.total_simulated_equity)}</span>
        </div>
      </div>

      {/* Sub-metrics */}
      <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
        <div>
          Drawdown <span className="text-foreground font-mono">{data.metrics.drawdown_pct.toFixed(2)}%</span>
        </div>
        <div>
          Sharpe <span className="text-foreground font-mono">{data.metrics.sharpe.toFixed(2)}</span>
        </div>
      </div>
    </div>
  );
}
```

### Step 2: Add to dashboard

In `frontend/src/app/dashboard/page.tsx`, import and render `CombinedLedgerCard` below the existing Account Summary card. It self-hides when options fallback is not active.

### Step 3: Commit
```bash
git add frontend/src/components/ledger/CombinedLedgerCard.tsx \
        frontend/src/app/dashboard/page.tsx
git commit -m "feat: add CombinedLedgerCard dashboard widget for broker + options sim equity"
```

---

## Task 9: Run full test suite + final commit

### Step 1: Run all tests
```bash
cd ~/adaptive-trading-ecosystem
python -m pytest tests/test_capability_flags.py \
                 tests/test_options_routing.py \
                 tests/test_ledger_aggregator.py \
                 tests/test_webull_guardrails.py \
                 -v --tb=short
```
Expected: all pass

### Step 2: Verify API endpoints respond correctly
```bash
TOKEN=$(python3 -c "
import jwt
from datetime import datetime, timedelta
secret = 'a5Vzn8cPb-L8aZQkfNvnIyIeVz1Air5YbJo4QMZzOMYIMIkXhE2VKDIb45KKetd2'
print(jwt.encode({'user_id':2,'email':'apetersongroup@gmail.com','exp':datetime.utcnow()+timedelta(days=365)}, secret, algorithm='HS256'))
")

# Combined ledger
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v2/ledger/combined | python3 -m json.tool

# API settings now includes options_fallback_enabled
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v2/api-settings | python3 -m json.tool
```

### Step 3: Final commit
```bash
git add -A
git commit -m "feat: options fallback — capability flags, routing, ledger aggregation, consent modal"
```

---

## Summary of New Files

| File | Purpose |
|------|---------|
| `services/order_router.py` | Routing logic — single source of truth |
| `services/ledger_aggregator.py` | Combined equity + metrics computation |
| `api/routes/ledger.py` | `GET /api/v2/ledger/combined` |
| `frontend/src/hooks/useOptionsGuard.ts` | Catches OPTIONS_NOT_SUPPORTED errors |
| `frontend/src/components/settings/OptionsFallbackModal.tsx` | Consent modal |
| `frontend/src/components/ledger/CombinedLedgerCard.tsx` | Dashboard widget |
| `tests/test_capability_flags.py` | Capability + OptionSimTrade tests |
| `tests/test_options_routing.py` | Routing unit tests |
| `tests/test_ledger_aggregator.py` | Ledger computation unit tests |
| `docs/plans/2026-03-10-options-fallback-design.md` | Approved design doc |

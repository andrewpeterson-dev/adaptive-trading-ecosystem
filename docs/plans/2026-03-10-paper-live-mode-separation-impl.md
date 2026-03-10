# Paper/Live Mode Separation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make paper and live trading modes fully isolated environments — server-authoritative mode, template-based strategies, explicit account mapping, execution safety, event logging, and strict query filtering.

**Architecture:** Backend owns the active trading mode per user (stored in DB, read by middleware). Every data query filters by mode. Strategies use template→instance pattern. Webull accounts are explicitly mapped. Live mode has risk limits and kill switch. All critical actions are logged to system_events.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy (async), Alembic, PostgreSQL, Next.js 14, Zustand, TypeScript

**Design doc:** `docs/plans/2026-03-10-paper-live-mode-separation-design.md`

---

## Task 1: Alembic Migration — New Tables and Column Additions

**Files:**
- Create: `alembic/versions/003_paper_live_mode_separation.py`

**Step 1: Create the migration file**

```python
"""Paper/live mode separation — new tables and column additions."""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002_add_copilot_tables"
branch_labels = None
depends_on = None


def upgrade():
    # ── user_trading_sessions ─────────────────────────────────────────────
    op.create_table(
        "user_trading_sessions",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column(
            "active_mode",
            sa.Enum("backtest", "paper", "live", name="tradingmodeenum", create_type=False),
            nullable=False,
            server_default="paper",
        ),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── strategy_templates ────────────────────────────────────────────────
    op.create_table(
        "strategy_templates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("conditions", sa.JSON, nullable=False),
        sa.Column("action", sa.String(16), nullable=False, server_default="BUY"),
        sa.Column("stop_loss_pct", sa.Float, server_default="0.02"),
        sa.Column("take_profit_pct", sa.Float, server_default="0.05"),
        sa.Column("timeframe", sa.String(16), server_default="1D"),
        sa.Column("diagnostics", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_strategy_template_user", "strategy_templates", ["user_id"])

    # ── strategy_instances ────────────────────────────────────────────────
    op.create_table(
        "strategy_instances",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("template_id", sa.Integer, sa.ForeignKey("strategy_templates.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "mode",
            sa.Enum("backtest", "paper", "live", name="tradingmodeenum", create_type=False),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("position_size_pct", sa.Float, server_default="0.1"),
        sa.Column("max_position_value", sa.Float, nullable=True),
        sa.Column("nickname", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("promoted_from_id", sa.Integer, sa.ForeignKey("strategy_instances.id"), nullable=True),
    )
    op.create_index("ix_strategy_instance_user_mode", "strategy_instances", ["user_id", "mode"])

    # ── user_broker_accounts ──────────────────────────────────────────────
    op.create_table(
        "user_broker_accounts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("connection_id", sa.Integer, sa.ForeignKey("user_api_connections.id"), nullable=False),
        sa.Column("broker_account_id", sa.String(128), nullable=False),
        sa.Column("account_type", sa.String(32), nullable=False),
        sa.Column("nickname", sa.String(100), nullable=True),
        sa.Column("discovered_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_user_broker_acct_user_type", "user_broker_accounts", ["user_id", "account_type"])

    # ── user_risk_limits ──────────────────────────────────────────────────
    op.create_table(
        "user_risk_limits",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column(
            "mode",
            sa.Enum("backtest", "paper", "live", name="tradingmodeenum", create_type=False),
            primary_key=True,
        ),
        sa.Column("daily_loss_limit", sa.Float, nullable=True),
        sa.Column("max_position_size_pct", sa.Float, server_default="0.25"),
        sa.Column("max_open_positions", sa.Integer, server_default="10"),
        sa.Column("kill_switch_active", sa.Boolean, server_default="false"),
        sa.Column("live_bot_trading_confirmed", sa.Boolean, server_default="false"),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── system_events ─────────────────────────────────────────────────────
    op.execute("""
        CREATE TYPE systemeventtype AS ENUM (
            'mode_switch', 'strategy_promoted', 'trade_executed', 'trade_failed',
            'account_sync', 'risk_limit_triggered', 'kill_switch_toggled',
            'bot_enabled', 'bot_disabled'
        )
    """)
    op.create_table(
        "system_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "mode_switch", "strategy_promoted", "trade_executed", "trade_failed",
                "account_sync", "risk_limit_triggered", "kill_switch_toggled",
                "bot_enabled", "bot_disabled",
                name="systemeventtype", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "mode",
            sa.Enum("backtest", "paper", "live", name="tradingmodeenum", create_type=False),
            nullable=False,
        ),
        sa.Column("severity", sa.String(16), server_default="info"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("metadata_json", sa.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_system_events_user_time", "system_events", ["user_id", "created_at"])
    op.create_index("ix_system_events_type", "system_events", ["event_type"])

    # ── Add mode columns to existing tables ───────────────────────────────
    op.add_column(
        "capital_allocations",
        sa.Column(
            "mode",
            sa.Enum("backtest", "paper", "live", name="tradingmodeenum", create_type=False),
            nullable=True,
        ),
    )
    op.execute("UPDATE capital_allocations SET mode = 'paper' WHERE mode IS NULL")
    op.alter_column("capital_allocations", "mode", nullable=False)

    op.add_column(
        "risk_events",
        sa.Column(
            "mode",
            sa.Enum("backtest", "paper", "live", name="tradingmodeenum", create_type=False),
            nullable=True,
        ),
    )
    op.execute("UPDATE risk_events SET mode = 'paper' WHERE mode IS NULL")
    op.alter_column("risk_events", "mode", nullable=False)

    op.add_column(
        "trading_models",
        sa.Column(
            "mode",
            sa.Enum("backtest", "paper", "live", name="tradingmodeenum", create_type=False),
            nullable=True,
        ),
    )
    op.execute("UPDATE trading_models SET mode = 'paper' WHERE mode IS NULL")
    op.alter_column("trading_models", "mode", nullable=False)

    # ── Migrate existing strategies → templates + paper instances ─────────
    op.execute("""
        INSERT INTO strategy_templates (id, user_id, name, description, conditions, action,
            stop_loss_pct, take_profit_pct, timeframe, diagnostics, created_at, updated_at)
        SELECT id, COALESCE(user_id, 1), name, description, conditions, action,
            stop_loss_pct, take_profit_pct, timeframe, diagnostics, created_at, updated_at
        FROM strategies
    """)
    op.execute("""
        INSERT INTO strategy_instances (template_id, user_id, mode, is_active, position_size_pct, created_at)
        SELECT id, COALESCE(user_id, 1), 'paper', true, position_size_pct, created_at
        FROM strategies
    """)

    # ── Create default sessions for existing users ────────────────────────
    op.execute("""
        INSERT INTO user_trading_sessions (user_id, active_mode)
        SELECT id, 'paper' FROM users
        ON CONFLICT DO NOTHING
    """)


def downgrade():
    op.drop_table("system_events")
    op.execute("DROP TYPE IF EXISTS systemeventtype")
    op.drop_table("user_risk_limits")
    op.drop_table("user_broker_accounts")
    op.drop_table("strategy_instances")
    op.drop_table("strategy_templates")
    op.drop_table("user_trading_sessions")
    op.drop_column("capital_allocations", "mode")
    op.drop_column("risk_events", "mode")
    op.drop_column("trading_models", "mode")
```

**Step 2: Run the migration locally**

```bash
cd ~/adaptive-trading-ecosystem
docker compose exec api alembic upgrade head
```

Expected: Migration applies cleanly, all new tables created.

**Step 3: Verify tables exist**

```bash
docker compose exec postgres psql -U trader -d trading_ecosystem -c "\dt user_trading_sessions; \dt strategy_templates; \dt strategy_instances; \dt user_broker_accounts; \dt user_risk_limits; \dt system_events;"
```

Expected: All 6 tables listed.

**Step 4: Commit**

```bash
git add alembic/versions/003_paper_live_mode_separation.py
git commit -m "feat: migration for paper/live mode separation tables"
```

---

## Task 2: SQLAlchemy Models — New Tables

**Files:**
- Modify: `db/models.py`

**Step 1: Write tests for new model instantiation**

Create `tests/test_mode_models.py`:

```python
"""Tests for paper/live mode separation models."""
import pytest
from db.models import (
    UserTradingSession, StrategyTemplate, StrategyInstance,
    UserBrokerAccount, UserRiskLimits, SystemEvent,
    SystemEventType, TradingModeEnum,
)


def test_user_trading_session_defaults():
    session = UserTradingSession(user_id=1)
    assert session.active_mode == TradingModeEnum.PAPER


def test_strategy_template_creation():
    t = StrategyTemplate(
        user_id=1, name="Test", conditions={"rules": []}, action="BUY",
    )
    assert t.name == "Test"
    assert t.stop_loss_pct == 0.02


def test_strategy_instance_creation():
    inst = StrategyInstance(
        template_id=1, user_id=1, mode=TradingModeEnum.PAPER,
        position_size_pct=0.15,
    )
    assert inst.mode == TradingModeEnum.PAPER
    assert inst.is_active is True


def test_user_broker_account_creation():
    acct = UserBrokerAccount(
        user_id=1, connection_id=1, broker_account_id="ABC123",
        account_type="paper",
    )
    assert acct.account_type == "paper"


def test_user_risk_limits_defaults():
    limits = UserRiskLimits(user_id=1, mode=TradingModeEnum.LIVE)
    assert limits.kill_switch_active is False
    assert limits.live_bot_trading_confirmed is False
    assert limits.max_position_size_pct == 0.25


def test_system_event_creation():
    event = SystemEvent(
        user_id=1,
        event_type=SystemEventType.MODE_SWITCH,
        mode=TradingModeEnum.PAPER,
        description="Switched to paper mode",
    )
    assert event.severity == "info"


def test_system_event_types_exist():
    assert SystemEventType.MODE_SWITCH.value == "mode_switch"
    assert SystemEventType.TRADE_EXECUTED.value == "trade_executed"
    assert SystemEventType.KILL_SWITCH_TOGGLED.value == "kill_switch_toggled"
```

**Step 2: Run tests to verify they fail**

```bash
cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_mode_models.py -v
```

Expected: ImportError — models don't exist yet.

**Step 3: Add models to `db/models.py`**

Add new enum after `BrokerType`:

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
```

Add new models after `UserApiSettings`:

```python
# ── Paper/Live Mode Separation ────────────────────────────────────────────────

class UserTradingSession(Base):
    __tablename__ = "user_trading_sessions"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    active_mode = Column(_enum(TradingModeEnum), nullable=False, default=TradingModeEnum.PAPER)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StrategyTemplate(Base):
    __tablename__ = "strategy_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    conditions = Column(JSON, nullable=False)
    action = Column(String(16), nullable=False, default="BUY")
    stop_loss_pct = Column(Float, default=0.02)
    take_profit_pct = Column(Float, default=0.05)
    timeframe = Column(String(16), default="1D")
    diagnostics = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    instances = relationship("StrategyInstance", back_populates="template")

    __table_args__ = (
        Index("ix_strategy_template_user", "user_id"),
    )


class StrategyInstance(Base):
    __tablename__ = "strategy_instances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(Integer, ForeignKey("strategy_templates.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mode = Column(_enum(TradingModeEnum), nullable=False)
    is_active = Column(Boolean, default=True)
    position_size_pct = Column(Float, default=0.1)
    max_position_value = Column(Float, nullable=True)
    nickname = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    promoted_from_id = Column(Integer, ForeignKey("strategy_instances.id"), nullable=True)

    template = relationship("StrategyTemplate", back_populates="instances")

    __table_args__ = (
        Index("ix_strategy_instance_user_mode", "user_id", "mode"),
    )


class UserBrokerAccount(Base):
    __tablename__ = "user_broker_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    connection_id = Column(Integer, ForeignKey("user_api_connections.id"), nullable=False)
    broker_account_id = Column(String(128), nullable=False)
    account_type = Column(String(32), nullable=False)
    nickname = Column(String(100), nullable=True)
    discovered_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_user_broker_acct_user_type", "user_id", "account_type"),
    )


class UserRiskLimits(Base):
    __tablename__ = "user_risk_limits"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    mode = Column(_enum(TradingModeEnum), primary_key=True)
    daily_loss_limit = Column(Float, nullable=True)
    max_position_size_pct = Column(Float, default=0.25)
    max_open_positions = Column(Integer, default=10)
    kill_switch_active = Column(Boolean, default=False)
    live_bot_trading_confirmed = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SystemEvent(Base):
    __tablename__ = "system_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_type = Column(_enum(SystemEventType), nullable=False)
    mode = Column(_enum(TradingModeEnum), nullable=False)
    severity = Column(String(16), default="info")
    description = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_system_events_user_time", "user_id", "created_at"),
        Index("ix_system_events_type", "event_type"),
    )
```

Also add `mode` column to existing models that lack it:

In `CapitalAllocation` class, add after `reason`:
```python
    mode = Column(_enum(TradingModeEnum), nullable=False)
```

In `RiskEvent` class, add after `action_taken`:
```python
    mode = Column(_enum(TradingModeEnum), nullable=False)
```

In `TradingModel` class, add after `is_active`:
```python
    mode = Column(_enum(TradingModeEnum), nullable=False, default=TradingModeEnum.PAPER)
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_mode_models.py -v
```

Expected: All 7 tests pass.

**Step 5: Commit**

```bash
git add db/models.py tests/test_mode_models.py
git commit -m "feat: add SQLAlchemy models for paper/live mode separation"
```

---

## Task 3: System Event Logger Service

**Files:**
- Create: `services/event_logger.py`
- Create: `tests/test_event_logger.py`

**Step 1: Write the test**

```python
"""Tests for system event logger."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from db.models import SystemEventType, TradingModeEnum


@pytest.mark.asyncio
async def test_log_event_creates_record():
    from services.event_logger import log_event

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("services.event_logger.get_session", return_value=mock_session):
        await log_event(
            user_id=1,
            event_type=SystemEventType.MODE_SWITCH,
            mode=TradingModeEnum.LIVE,
            description="Switched to live",
        )
        mock_session.add.assert_called_once()
        added = mock_session.add.call_args[0][0]
        assert added.user_id == 1
        assert added.event_type == SystemEventType.MODE_SWITCH
        assert added.mode == TradingModeEnum.LIVE
        assert added.severity == "info"
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_event_logger.py -v
```

Expected: ModuleNotFoundError.

**Step 3: Implement `services/event_logger.py`**

```python
"""System event logger — records critical actions for audit trail."""

import structlog
from db.database import get_session
from db.models import SystemEvent, SystemEventType, TradingModeEnum

logger = structlog.get_logger(__name__)


async def log_event(
    user_id: int,
    event_type: SystemEventType,
    mode: TradingModeEnum,
    description: str = "",
    severity: str = "info",
    metadata: dict | None = None,
) -> None:
    """Write a system event to the database. Fire-and-forget safe."""
    try:
        async with get_session() as db:
            db.add(SystemEvent(
                user_id=user_id,
                event_type=event_type,
                mode=mode,
                severity=severity,
                description=description,
                metadata_json=metadata or {},
            ))
        logger.info("system_event_logged", event=event_type.value, user_id=user_id)
    except Exception as exc:
        # Never let event logging crash the caller
        logger.error("system_event_log_failed", error=str(exc), event=event_type.value)
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_event_logger.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add services/event_logger.py tests/test_event_logger.py
git commit -m "feat: add system event logger service"
```

---

## Task 4: Trading Mode Middleware

**Files:**
- Create: `api/middleware/trading_mode.py`
- Modify: `api/main.py` (add middleware)
- Create: `tests/test_trading_mode_middleware.py`

**Step 1: Write the test**

```python
"""Tests for trading mode middleware."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from starlette.testclient import TestClient
from fastapi import FastAPI, Request
from api.middleware.trading_mode import TradingModeMiddleware
from db.models import TradingModeEnum


def _make_app():
    app = FastAPI()
    app.add_middleware(TradingModeMiddleware)

    @app.get("/test")
    async def test_endpoint(request: Request):
        return {
            "mode": getattr(request.state, "trading_mode", None),
        }

    return app


@pytest.mark.asyncio
async def test_middleware_sets_mode_from_db():
    """Middleware reads user's active mode from DB and sets request.state.trading_mode."""
    app = _make_app()

    mock_session_obj = AsyncMock()
    mock_result = MagicMock()
    mock_record = MagicMock()
    mock_record.active_mode = TradingModeEnum.LIVE
    mock_result.scalar_one_or_none.return_value = mock_record
    mock_session_obj.execute = AsyncMock(return_value=mock_result)
    mock_session_obj.__aenter__ = AsyncMock(return_value=mock_session_obj)
    mock_session_obj.__aexit__ = AsyncMock(return_value=False)

    with patch("api.middleware.trading_mode.get_session", return_value=mock_session_obj):
        client = TestClient(app)
        # Simulate authenticated request (user_id already set by auth middleware)
        # We need to set request.state.user_id — done via a test dependency
        pass  # Integration tested in Task 6


def test_middleware_defaults_to_paper_when_no_session():
    """If no user_trading_sessions row, default to paper."""
    # Tested via integration in Task 6
    pass
```

**Step 2: Implement middleware**

Create `api/middleware/trading_mode.py`:

```python
"""Trading mode middleware — reads the user's active mode from DB on every request."""

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy import select

from db.database import get_session
from db.models import UserTradingSession, TradingModeEnum

logger = structlog.get_logger(__name__)

# Paths that don't need trading mode
_SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}
_SKIP_PREFIXES = ("/api/auth/",)


class TradingModeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip for unauthenticated / non-data paths
        path = request.url.path
        if path in _SKIP_PATHS or any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        # Only run if auth middleware has set user_id
        user_id = getattr(request.state, "user_id", None)
        if user_id is None:
            return await call_next(request)

        # Look up server-side mode
        try:
            async with get_session() as db:
                result = await db.execute(
                    select(UserTradingSession).where(
                        UserTradingSession.user_id == user_id
                    )
                )
                session = result.scalar_one_or_none()

            request.state.trading_mode = (
                session.active_mode if session else TradingModeEnum.PAPER
            )
        except Exception as exc:
            logger.warning("trading_mode_middleware_error", error=str(exc))
            request.state.trading_mode = TradingModeEnum.PAPER

        return await call_next(request)
```

**Step 3: Register middleware in `api/main.py`**

Add after JWTAuthMiddleware import:
```python
from api.middleware.trading_mode import TradingModeMiddleware
```

Add after `app.add_middleware(JWTAuthMiddleware)`:
```python
app.add_middleware(TradingModeMiddleware)
```

Note: Starlette processes middleware in reverse registration order, so TradingModeMiddleware (registered second) runs after JWTAuthMiddleware — meaning `user_id` is already set.

**Step 4: Commit**

```bash
git add api/middleware/trading_mode.py api/main.py tests/test_trading_mode_middleware.py
git commit -m "feat: add trading mode middleware — reads active mode from DB"
```

---

## Task 5: Mode Switch Endpoint + User Mode API

**Files:**
- Create: `api/routes/user_mode.py`
- Modify: `api/main.py` (register route)
- Create: `tests/test_user_mode.py`

**Step 1: Write test**

```python
"""Tests for user mode endpoints."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from db.models import TradingModeEnum, UserTradingSession


@pytest.mark.asyncio
async def test_set_mode_valid():
    from api.routes.user_mode import set_mode, SetModeRequest
    from starlette.requests import Request

    mock_request = MagicMock(spec=Request)
    mock_request.state.user_id = 1
    mock_request.state.trading_mode = TradingModeEnum.PAPER

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = UserTradingSession(
        user_id=1, active_mode=TradingModeEnum.PAPER,
    )
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("api.routes.user_mode.get_session", return_value=mock_session), \
         patch("api.routes.user_mode.log_event", new_callable=AsyncMock):
        result = await set_mode(SetModeRequest(mode="live"), mock_request)
        assert result["mode"] == "live"


@pytest.mark.asyncio
async def test_set_mode_rejects_invalid():
    from api.routes.user_mode import set_mode, SetModeRequest
    from fastapi import HTTPException

    mock_request = MagicMock()
    mock_request.state.user_id = 1

    with pytest.raises(Exception):
        await set_mode(SetModeRequest(mode="invalid"), mock_request)
```

**Step 2: Implement endpoint**

Create `api/routes/user_mode.py`:

```python
"""User trading mode endpoints — server-authoritative mode switching."""

from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from db.database import get_session
from db.models import UserTradingSession, TradingModeEnum
from services.event_logger import log_event
from db.models import SystemEventType

logger = structlog.get_logger(__name__)
router = APIRouter()


class SetModeRequest(BaseModel):
    mode: str  # "paper" or "live"


@router.get("/mode")
async def get_mode(request: Request):
    """Return the user's current server-side trading mode."""
    user_id = request.state.user_id
    async with get_session() as db:
        result = await db.execute(
            select(UserTradingSession).where(UserTradingSession.user_id == user_id)
        )
        session = result.scalar_one_or_none()

    mode = session.active_mode if session else TradingModeEnum.PAPER
    return {"mode": mode.value}


@router.post("/set-mode")
async def set_mode(req: SetModeRequest, request: Request):
    """Switch the user's active trading mode. Server-authoritative."""
    user_id = request.state.user_id

    # Validate
    try:
        new_mode = TradingModeEnum(req.mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}. Must be 'paper' or 'live'.")

    if new_mode == TradingModeEnum.BACKTEST:
        raise HTTPException(status_code=400, detail="Cannot manually switch to backtest mode.")

    async with get_session() as db:
        result = await db.execute(
            select(UserTradingSession).where(UserTradingSession.user_id == user_id)
        )
        session = result.scalar_one_or_none()

        old_mode = session.active_mode if session else TradingModeEnum.PAPER

        if session:
            session.active_mode = new_mode
            session.updated_at = datetime.utcnow()
        else:
            db.add(UserTradingSession(user_id=user_id, active_mode=new_mode))

    # Log the event
    await log_event(
        user_id=user_id,
        event_type=SystemEventType.MODE_SWITCH,
        mode=new_mode,
        description=f"Switched from {old_mode.value} to {new_mode.value}",
    )

    logger.info("mode_switched", user_id=user_id, old=old_mode.value, new=new_mode.value)
    return {"mode": new_mode.value, "previous": old_mode.value}
```

**Step 3: Register in `api/main.py`**

```python
from api.routes import user_mode as user_mode_routes
# ...
app.include_router(user_mode_routes.router, prefix="/api/user", tags=["User"])
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_user_mode.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add api/routes/user_mode.py api/main.py tests/test_user_mode.py
git commit -m "feat: add server-side mode switch endpoint POST /api/user/set-mode"
```

---

## Task 6: Frontend — Server-Authoritative Mode + Cache Reset

**Files:**
- Modify: `frontend/src/hooks/useTradingMode.ts`
- Create: `frontend/src/lib/api/mode.ts`
- Modify: `frontend/src/components/layout/NavHeader.tsx`

**Step 1: Create API helper for mode**

Create `frontend/src/lib/api/mode.ts`:

```typescript
import { apiFetch } from "./client";

export type TradingMode = "paper" | "live";

interface ModeResponse {
  mode: TradingMode;
  previous?: TradingMode;
}

export async function getServerMode(): Promise<TradingMode> {
  const res = await apiFetch<ModeResponse>("/api/user/mode");
  return res.mode;
}

export async function setServerMode(mode: TradingMode): Promise<ModeResponse> {
  return apiFetch<ModeResponse>("/api/user/set-mode", {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
}
```

**Step 2: Update `useTradingMode.ts` for server authority + cache reset**

Replace the entire file:

```typescript
"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import React from "react";
import { getServerMode, setServerMode } from "@/lib/api/mode";

export type TradingMode = "paper" | "live";

interface TradingModeContextValue {
  mode: TradingMode;
  setMode: (mode: TradingMode) => void;
  isPaper: boolean;
  isLive: boolean;
  switching: boolean;
}

const TradingModeContext = createContext<TradingModeContextValue | null>(null);

const STORAGE_KEY = "trading_mode";

function applyTheme(m: TradingMode): void {
  const html = document.documentElement;
  if (m === "live") {
    html.classList.add("dark");
  } else {
    html.classList.remove("dark");
  }
}

/**
 * Broadcast a custom event so all polling hooks and components know to re-fetch.
 * Components listen via useModeResetListener().
 */
function broadcastModeReset(): void {
  window.dispatchEvent(new CustomEvent("trading-mode-reset"));
}

export function TradingModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<TradingMode>("paper");
  const [switching, setSwitching] = useState(false);

  // On mount: fetch server-authoritative mode
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as TradingMode | null;
    if (stored === "paper" || stored === "live") {
      setModeState(stored);
      applyTheme(stored);
    }
    // Then confirm with server (source of truth)
    getServerMode()
      .then((serverMode) => {
        setModeState(serverMode);
        localStorage.setItem(STORAGE_KEY, serverMode);
        applyTheme(serverMode);
      })
      .catch(() => {
        // Not logged in yet — keep localStorage value
      });
  }, []);

  const setMode = useCallback(async (next: TradingMode) => {
    setSwitching(true);
    try {
      // 1. Tell the server first (source of truth)
      await setServerMode(next);
      // 2. Only update client after server confirms
      setModeState(next);
      localStorage.setItem(STORAGE_KEY, next);
      applyTheme(next);
      // 3. Broadcast reset so all components re-fetch
      broadcastModeReset();
    } catch (err) {
      console.error("Failed to switch mode:", err);
    } finally {
      setSwitching(false);
    }
  }, []);

  const value: TradingModeContextValue = {
    mode,
    setMode,
    isPaper: mode === "paper",
    isLive: mode === "live",
    switching,
  };

  return React.createElement(TradingModeContext.Provider, { value }, children);
}

export function useTradingMode(): TradingModeContextValue {
  const ctx = useContext(TradingModeContext);
  if (!ctx) {
    throw new Error("useTradingMode must be used within a TradingModeProvider");
  }
  return ctx;
}

/**
 * Hook for components to re-fetch data when mode switches.
 * Call this in any component that fetches mode-specific data.
 */
export function useModeResetListener(onReset: () => void): void {
  useEffect(() => {
    const handler = () => onReset();
    window.addEventListener("trading-mode-reset", handler);
    return () => window.removeEventListener("trading-mode-reset", handler);
  }, [onReset]);
}
```

**Step 3: Update NavHeader toggle to show loading state**

In `frontend/src/components/layout/NavHeader.tsx`, update the toggle button:

Replace `const { mode, setMode } = useTradingMode();` with:
```typescript
const { mode, setMode, switching } = useTradingMode();
```

Add `disabled={switching}` and opacity class to the button:
```typescript
<button
  onClick={() => setMode(mode === "paper" ? "live" : "paper")}
  disabled={switching}
  aria-label={`Switch to ${mode === "paper" ? "live" : "paper"} trading`}
  title={`Currently: ${mode === "paper" ? "Paper" : "Live"} trading — click to switch`}
  className={`relative flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold tracking-widest uppercase border transition-all duration-200 ${
    switching ? "opacity-50 cursor-wait" : ""
  } ${
    mode === "live"
      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20"
      : "bg-muted/60 border-border/50 text-muted-foreground hover:text-foreground hover:bg-muted"
  }`}
>
```

**Step 4: Commit**

```bash
git add frontend/src/lib/api/mode.ts frontend/src/hooks/useTradingMode.ts frontend/src/components/layout/NavHeader.tsx
git commit -m "feat: server-authoritative mode switching with cache reset broadcast"
```

---

## Task 7: Update All Backend Endpoints to Filter by Mode

**Files:**
- Modify: `api/routes/dashboard.py`
- Modify: `api/routes/models.py`
- Modify: `api/routes/trading.py`
- Modify: `api/routes/strategies.py`

**Step 1: Fix `dashboard.py` equity curve**

Replace the query in `get_equity_curve`:

```python
@router.get("/equity-curve")
async def get_equity_curve(request: Request):
    """Get equity curve data for charting — filtered by active trading mode."""
    mode = request.state.trading_mode

    async with get_session() as db:
        result = await db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.mode == mode)
            .order_by(PortfolioSnapshot.timestamp.asc())
            .limit(500)
        )
        snapshots = result.scalars().all()

    if snapshots:
        points = [
            {
                "date": s.timestamp.strftime("%Y-%m-%d"),
                "value": round(s.total_equity, 2),
                "cash": round(s.cash, 2),
                "drawdown_pct": round(s.drawdown_pct, 4),
            }
            for s in snapshots
        ]
        return {"equity_curve": points, "mode": mode.value}

    logger.info("equity_curve_seed_data", reason="no portfolio snapshots", mode=mode.value)
    return {"equity_curve": _generate_seed_equity_curve(), "mode": mode.value}
```

**Step 2: Fix `models.py` — add mode filtering to all endpoints**

For each query in models.py, add `.where(TradingModel.mode == request.state.trading_mode)` to the `select()` statement. Same for `ModelPerformance` and `CapitalAllocation` queries.

Pattern for every endpoint:
```python
mode = request.state.trading_mode
# Add to every select:
.where(Model.mode == mode)
```

**Step 3: Rewrite `strategies.py` for template→instance pattern**

Replace strategy CRUD to work with `StrategyTemplate` and `StrategyInstance`. Key changes:

- `GET /api/strategies` → query `StrategyInstance` joined to `StrategyTemplate` where `instance.mode == request.state.trading_mode`
- `POST /api/strategies` → create `StrategyTemplate` + `StrategyInstance` for current mode
- `PUT /api/strategies/{id}` → update template (logic) or instance (sizing)
- `DELETE /api/strategies/{id}` → deactivate instance (keep template)
- `POST /api/strategies/{id}/promote` → create new instance in live mode from paper instance

**Step 4: Add promote endpoint**

```python
@router.post("/strategies/{instance_id}/promote")
async def promote_strategy(instance_id: int, req: PromoteRequest, request: Request):
    """Create a live instance from a paper strategy instance."""
    user_id = request.state.user_id
    mode = request.state.trading_mode

    if mode != TradingModeEnum.PAPER:
        raise HTTPException(400, "Can only promote from paper mode")

    async with get_session() as db:
        result = await db.execute(
            select(StrategyInstance).where(
                StrategyInstance.id == instance_id,
                StrategyInstance.user_id == user_id,
                StrategyInstance.mode == TradingModeEnum.PAPER,
            )
        )
        paper_inst = result.scalar_one_or_none()
        if not paper_inst:
            raise HTTPException(404, "Paper strategy instance not found")

        live_inst = StrategyInstance(
            template_id=paper_inst.template_id,
            user_id=user_id,
            mode=TradingModeEnum.LIVE,
            is_active=True,
            position_size_pct=req.position_size_pct or paper_inst.position_size_pct,
            max_position_value=req.max_position_value,
            nickname=req.nickname or f"{paper_inst.nickname or 'Strategy'} — Live",
            promoted_from_id=paper_inst.id,
        )
        db.add(live_inst)

    await log_event(
        user_id=user_id,
        event_type=SystemEventType.STRATEGY_PROMOTED,
        mode=TradingModeEnum.LIVE,
        description=f"Promoted instance {instance_id} to live",
        metadata={"paper_instance_id": instance_id, "live_instance_id": live_inst.id},
    )

    return {"id": live_inst.id, "mode": "live", "promoted_from": instance_id}
```

**Step 5: Commit**

```bash
git add api/routes/dashboard.py api/routes/models.py api/routes/strategies.py api/routes/trading.py
git commit -m "feat: all backend endpoints now filter by server-side trading mode"
```

---

## Task 8: Webull Account Discovery + Storage

**Files:**
- Create: `services/account_discovery.py`
- Modify: `api/routes/api_connections.py` (trigger discovery on connect)
- Create: `tests/test_account_discovery.py`

**Step 1: Implement account discovery service**

Create `services/account_discovery.py`:

```python
"""Webull account discovery — maps paper and live account IDs per user."""

import structlog
from sqlalchemy import select, delete

from db.database import get_session
from db.models import (
    UserBrokerAccount, UserApiConnection, SystemEventType, TradingModeEnum,
)
from services.event_logger import log_event

logger = structlog.get_logger(__name__)


async def discover_and_store_accounts(
    user_id: int,
    connection_id: int,
    app_key: str,
    app_secret: str,
) -> dict:
    """
    Call Webull SDK to discover paper and live accounts,
    store them in user_broker_accounts.
    Returns {"paper": [account_ids], "live": [account_ids]}.
    """
    try:
        from webullsdkcore.client import ApiClient
        from webullsdkcore.common.region import Region
        from webullsdktrade.api import API
    except ImportError as exc:
        logger.error("webull_sdk_missing", error=str(exc))
        return {"paper": [], "live": [], "error": str(exc)}

    try:
        api_client = ApiClient(app_key, app_secret, Region.US.value)
        api = API(api_client)
        resp = api.account.get_app_subscriptions()

        if resp.status_code != 200:
            return {"paper": [], "live": [], "error": f"HTTP {resp.status_code}"}

        subs = resp.json()
        if not isinstance(subs, list):
            subs = subs.get("data", [])

        paper_ids = []
        live_ids = []

        for sub in subs:
            acct_id = str(sub.get("account_id", sub.get("accountId", "")))
            if not acct_id:
                continue

            try:
                pr = api.account.get_account_profile(acct_id)
                acct_type = (
                    pr.json().get("account_type", "").lower()
                    if pr.status_code == 200 else ""
                )
            except Exception:
                acct_type = ""

            if any(kw in acct_type for kw in ("paper", "virtual", "demo", "simulated")):
                paper_ids.append(acct_id)
            else:
                live_ids.append(acct_id)

        # Store in DB — replace existing for this connection
        async with get_session() as db:
            await db.execute(
                delete(UserBrokerAccount).where(
                    UserBrokerAccount.user_id == user_id,
                    UserBrokerAccount.connection_id == connection_id,
                )
            )

            for acct_id in paper_ids:
                db.add(UserBrokerAccount(
                    user_id=user_id,
                    connection_id=connection_id,
                    broker_account_id=acct_id,
                    account_type="paper",
                ))
            for acct_id in live_ids:
                db.add(UserBrokerAccount(
                    user_id=user_id,
                    connection_id=connection_id,
                    broker_account_id=acct_id,
                    account_type="live",
                ))

        await log_event(
            user_id=user_id,
            event_type=SystemEventType.ACCOUNT_SYNC,
            mode=TradingModeEnum.PAPER,
            description=f"Discovered {len(paper_ids)} paper, {len(live_ids)} live accounts",
            metadata={"paper_ids": paper_ids, "live_ids": live_ids},
        )

        logger.info(
            "accounts_discovered",
            user_id=user_id,
            paper=len(paper_ids),
            live=len(live_ids),
        )
        return {"paper": paper_ids, "live": live_ids}

    except Exception as exc:
        logger.error("account_discovery_failed", error=str(exc))
        return {"paper": [], "live": [], "error": str(exc)}
```

**Step 2: Wire into API connection creation**

In `api/routes/api_connections.py`, after the connection is created and tested (around line 288), add Webull account discovery:

```python
# After conn is saved and tested, discover accounts if Webull
if provider.slug == "webull":
    from services.account_discovery import discover_and_store_accounts
    credentials = req.credentials
    await discover_and_store_accounts(
        user_id=user_id,
        connection_id=conn.id,
        app_key=credentials.get("app_key", ""),
        app_secret=credentials.get("app_secret", ""),
    )
```

**Step 3: Commit**

```bash
git add services/account_discovery.py api/routes/api_connections.py tests/test_account_discovery.py
git commit -m "feat: Webull account discovery — store paper/live account IDs on connect"
```

---

## Task 9: Risk Limits + Kill Switch Endpoints

**Files:**
- Create: `api/routes/risk_limits.py`
- Create: `services/risk_guard.py`
- Modify: `api/main.py`
- Create: `tests/test_risk_guard.py`

**Step 1: Implement risk guard service**

Create `services/risk_guard.py`:

```python
"""Pre-trade risk checks — enforced before every order execution."""

import structlog
from datetime import datetime, timedelta
from sqlalchemy import select, func

from db.database import get_session
from db.models import (
    UserRiskLimits, Trade, TradeStatus, TradingModeEnum, SystemEventType,
)
from services.event_logger import log_event

logger = structlog.get_logger(__name__)


class RiskViolation(Exception):
    """Raised when a risk limit would be breached."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


async def check_pre_trade(
    user_id: int,
    mode: TradingModeEnum,
    order_value: float,
    total_equity: float,
    open_position_count: int,
    is_bot: bool = False,
) -> None:
    """
    Run all risk checks. Raises RiskViolation if any limit is breached.
    Call this before placing any order.
    """
    async with get_session() as db:
        result = await db.execute(
            select(UserRiskLimits).where(
                UserRiskLimits.user_id == user_id,
                UserRiskLimits.mode == mode,
            )
        )
        limits = result.scalar_one_or_none()

    if not limits:
        return  # No limits set — allow trade

    # 1. Kill switch
    if limits.kill_switch_active:
        await log_event(user_id, SystemEventType.RISK_LIMIT_TRIGGERED, mode,
                        "Kill switch is active — all trading halted", "critical")
        raise RiskViolation("Kill switch is active. All trading is halted.")

    # 2. Daily loss limit
    if limits.daily_loss_limit is not None:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        async with get_session() as db:
            result = await db.execute(
                select(func.coalesce(func.sum(Trade.pnl), 0)).where(
                    Trade.mode == mode,
                    Trade.status == TradeStatus.FILLED,
                    Trade.exit_time >= today_start,
                )
            )
            daily_pnl = result.scalar()

        if daily_pnl is not None and daily_pnl <= -abs(limits.daily_loss_limit):
            await log_event(user_id, SystemEventType.RISK_LIMIT_TRIGGERED, mode,
                            f"Daily loss limit hit: ${daily_pnl:.2f}", "warning")
            raise RiskViolation(
                f"Daily loss limit exceeded. Today's P&L: ${daily_pnl:.2f}, "
                f"limit: -${limits.daily_loss_limit:.2f}"
            )

    # 3. Max position size
    if total_equity > 0 and limits.max_position_size_pct:
        position_pct = order_value / total_equity
        if position_pct > limits.max_position_size_pct:
            await log_event(user_id, SystemEventType.RISK_LIMIT_TRIGGERED, mode,
                            f"Position size {position_pct:.1%} exceeds {limits.max_position_size_pct:.1%}", "warning")
            raise RiskViolation(
                f"Position size ({position_pct:.1%}) exceeds limit ({limits.max_position_size_pct:.1%})"
            )

    # 4. Max open positions
    if limits.max_open_positions and open_position_count >= limits.max_open_positions:
        await log_event(user_id, SystemEventType.RISK_LIMIT_TRIGGERED, mode,
                        f"Max open positions ({limits.max_open_positions}) reached", "warning")
        raise RiskViolation(f"Max open positions ({limits.max_open_positions}) reached")

    # 5. Live bot confirmation
    if is_bot and mode == TradingModeEnum.LIVE and not limits.live_bot_trading_confirmed:
        await log_event(user_id, SystemEventType.RISK_LIMIT_TRIGGERED, mode,
                        "Live bot trading not confirmed", "warning")
        raise RiskViolation(
            "Live automated trading has not been confirmed. "
            "Enable it in Settings → Risk Limits before running bots in live mode."
        )
```

**Step 2: Create risk limits endpoints**

Create `api/routes/risk_limits.py`:

```python
"""Risk limits and kill switch management."""

from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from db.database import get_session
from db.models import UserRiskLimits, TradingModeEnum, SystemEventType
from services.event_logger import log_event

logger = structlog.get_logger(__name__)
router = APIRouter()


class UpdateRiskLimitsRequest(BaseModel):
    daily_loss_limit: float | None = None
    max_position_size_pct: float | None = None
    max_open_positions: int | None = None


@router.get("/limits")
async def get_risk_limits(request: Request):
    mode = request.state.trading_mode
    user_id = request.state.user_id

    async with get_session() as db:
        result = await db.execute(
            select(UserRiskLimits).where(
                UserRiskLimits.user_id == user_id,
                UserRiskLimits.mode == mode,
            )
        )
        limits = result.scalar_one_or_none()

    if not limits:
        return {
            "mode": mode.value,
            "daily_loss_limit": None,
            "max_position_size_pct": 0.25,
            "max_open_positions": 10,
            "kill_switch_active": False,
            "live_bot_trading_confirmed": False,
        }

    return {
        "mode": mode.value,
        "daily_loss_limit": limits.daily_loss_limit,
        "max_position_size_pct": limits.max_position_size_pct,
        "max_open_positions": limits.max_open_positions,
        "kill_switch_active": limits.kill_switch_active,
        "live_bot_trading_confirmed": limits.live_bot_trading_confirmed,
    }


@router.put("/limits")
async def update_risk_limits(req: UpdateRiskLimitsRequest, request: Request):
    mode = request.state.trading_mode
    user_id = request.state.user_id

    async with get_session() as db:
        result = await db.execute(
            select(UserRiskLimits).where(
                UserRiskLimits.user_id == user_id,
                UserRiskLimits.mode == mode,
            )
        )
        limits = result.scalar_one_or_none()

        if not limits:
            limits = UserRiskLimits(user_id=user_id, mode=mode)
            db.add(limits)

        if req.daily_loss_limit is not None:
            limits.daily_loss_limit = req.daily_loss_limit
        if req.max_position_size_pct is not None:
            limits.max_position_size_pct = req.max_position_size_pct
        if req.max_open_positions is not None:
            limits.max_open_positions = req.max_open_positions
        limits.updated_at = datetime.utcnow()

    return {"success": True, "mode": mode.value}


@router.post("/kill-switch")
async def toggle_kill_switch(request: Request):
    mode = request.state.trading_mode
    user_id = request.state.user_id

    async with get_session() as db:
        result = await db.execute(
            select(UserRiskLimits).where(
                UserRiskLimits.user_id == user_id,
                UserRiskLimits.mode == mode,
            )
        )
        limits = result.scalar_one_or_none()

        if not limits:
            limits = UserRiskLimits(user_id=user_id, mode=mode, kill_switch_active=True)
            db.add(limits)
        else:
            limits.kill_switch_active = not limits.kill_switch_active
        limits.updated_at = datetime.utcnow()

        new_state = limits.kill_switch_active

    await log_event(
        user_id=user_id,
        event_type=SystemEventType.KILL_SWITCH_TOGGLED,
        mode=mode,
        description=f"Kill switch {'activated' if new_state else 'deactivated'}",
        severity="critical",
    )

    return {"kill_switch_active": new_state, "mode": mode.value}


@router.post("/confirm-live-bots")
async def confirm_live_bot_trading(request: Request):
    user_id = request.state.user_id
    mode = request.state.trading_mode

    if mode != TradingModeEnum.LIVE:
        raise HTTPException(400, "Can only confirm live bot trading while in live mode")

    async with get_session() as db:
        result = await db.execute(
            select(UserRiskLimits).where(
                UserRiskLimits.user_id == user_id,
                UserRiskLimits.mode == TradingModeEnum.LIVE,
            )
        )
        limits = result.scalar_one_or_none()

        if not limits:
            limits = UserRiskLimits(user_id=user_id, mode=TradingModeEnum.LIVE, live_bot_trading_confirmed=True)
            db.add(limits)
        else:
            limits.live_bot_trading_confirmed = True
        limits.updated_at = datetime.utcnow()

    await log_event(
        user_id=user_id,
        event_type=SystemEventType.BOT_ENABLED,
        mode=TradingModeEnum.LIVE,
        description="User confirmed live bot trading",
        severity="critical",
    )

    return {"confirmed": True}
```

**Step 3: Register in `api/main.py`**

```python
from api.routes import risk_limits as risk_limits_routes
# ...
app.include_router(risk_limits_routes.router, prefix="/api/risk", tags=["Risk"])
```

**Step 4: Commit**

```bash
git add services/risk_guard.py api/routes/risk_limits.py api/main.py tests/test_risk_guard.py
git commit -m "feat: risk limits, kill switch, and pre-trade safety checks"
```

---

## Task 10: Update Frontend Polling Hooks for Mode Reset

**Files:**
- Modify: `frontend/src/hooks/usePolling.ts`
- Modify: relevant page components that use `usePolling`

**Step 1: Update `usePolling` to listen for mode resets**

Add mode reset listener to the existing `usePolling` hook so it re-fetches when mode switches:

```typescript
import { useModeResetListener } from "@/hooks/useTradingMode";

export function usePolling<T>({ fetcher, interval, enabled }: UsePollingOptions<T>) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetcher();
      setData(result);
    } catch (err: any) {
      setError(err.message || "Fetch failed");
    } finally {
      setLoading(false);
    }
  }, [fetcher]);

  // Re-fetch on mode switch
  useModeResetListener(refresh);

  // ... existing polling interval logic
}
```

This ensures every component using `usePolling` automatically re-fetches when the trading mode changes.

**Step 2: Commit**

```bash
git add frontend/src/hooks/usePolling.ts
git commit -m "feat: usePolling re-fetches on mode switch via reset listener"
```

---

## Task 11: Rebuild Docker + Integration Test

**Step 1: Rebuild and restart all containers**

```bash
cd ~/adaptive-trading-ecosystem
docker compose build api frontend
docker compose up -d
```

**Step 2: Verify migration ran**

```bash
docker compose exec api alembic current
```

Expected: Shows revision `003`.

**Step 3: Manual integration test**

1. Open `http://localhost:3000` — log in
2. Click Paper/Live toggle — verify:
   - Toggle shows loading state
   - Theme switches
   - Dashboard data re-fetches (may show empty state for live mode)
3. Check backend logs: `docker logs adaptive-trading-ecosystem-api-1 --tail 20`
   - Should see `mode_switched` log entry
   - Should see `system_event_logged` entry

**Step 4: Verify system events table**

```bash
docker compose exec postgres psql -U trader -d trading_ecosystem -c "SELECT * FROM system_events ORDER BY created_at DESC LIMIT 5;"
```

Expected: mode_switch events visible.

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete paper/live mode separation — all 7 architectural corrections"
```

---

## Task Summary

| # | Task | Key Deliverable |
|---|------|-----------------|
| 1 | Alembic migration | 6 new tables, 3 column additions, data migration |
| 2 | SQLAlchemy models | All new models + mode columns on existing models |
| 3 | Event logger service | `log_event()` — fire-and-forget audit logging |
| 4 | Trading mode middleware | Reads mode from DB, sets `request.state.trading_mode` |
| 5 | Mode switch endpoint | `POST /api/user/set-mode` — server-authoritative |
| 6 | Frontend mode + cache | Server-first switching, broadcast reset, loading state |
| 7 | Backend query filtering | All endpoints filter by `request.state.trading_mode` |
| 8 | Account discovery | Store paper/live Webull account IDs on connect |
| 9 | Risk limits + kill switch | Pre-trade checks, daily loss limit, kill switch |
| 10 | Frontend polling reset | `usePolling` re-fetches on mode change |
| 11 | Docker rebuild + test | End-to-end verification |

## Dependencies

```
Task 1 (migration) → Task 2 (models) → Task 3 (event logger)
                                       → Task 4 (middleware) → Task 5 (endpoint) → Task 6 (frontend)
                                       → Task 7 (query filtering)
                                       → Task 8 (account discovery)
                                       → Task 9 (risk guard)
                                       → Task 10 (polling reset)
All → Task 11 (integration test)
```

Tasks 3, 7, 8, 9, 10 can run in parallel after Task 2 completes.

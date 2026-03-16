"""
Tests for Paper/Live mode separation models.
Validates instantiation, defaults, enum completeness, and composite PK.

Column defaults are server-side (applied at flush), so tests that check
defaults insert the row and re-read it from the session.
"""

import pytest

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from db.database import Base
from db.models import (
    TradingModeEnum,
    SystemEventType,
    UserTradingSession,
    StrategyTemplate,
    StrategyInstance,
    UserBrokerAccount,
    UserRiskLimits,
    SystemEvent,
    User,
    UserApiConnection,
    ApiProvider,
    ApiProviderType,
)


@pytest.fixture(scope="module")
def engine():
    """In-memory SQLite engine with all tables created."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    """Fresh DB session, rolled back after each test."""
    conn = engine.connect()
    trans = conn.begin()
    sess = Session(bind=conn)
    yield sess
    sess.close()
    trans.rollback()
    conn.close()


def _seed_user(session, user_id=1):
    """Insert a minimal User row so FK constraints are satisfied."""
    existing = session.get(User, user_id)
    if existing:
        return existing
    user = User(
        id=user_id,
        email=f"test{user_id}@example.com",
        password_hash="fakehash",
        display_name="Test",
    )
    session.add(user)
    session.flush()
    return user


def _seed_provider(session):
    """Insert a minimal ApiProvider so FK constraints are satisfied."""
    existing = session.get(ApiProvider, 1)
    if existing:
        return existing
    prov = ApiProvider(
        id=1,
        slug="test-broker",
        name="Test Broker",
        api_type=ApiProviderType.BROKERAGE,
        credential_fields={"api_key": "string"},
    )
    session.add(prov)
    session.flush()
    return prov


def _seed_connection(session, user_id=1):
    """Insert a minimal UserApiConnection."""
    _seed_user(session, user_id)
    _seed_provider(session)
    conn = UserApiConnection(
        id=1,
        user_id=user_id,
        provider_id=1,
        encrypted_credentials="enc",
    )
    session.add(conn)
    session.flush()
    return conn


# ── SystemEventType enum ────────────────────────────────────────────────────


class TestSystemEventType:
    def test_has_all_nine_values(self):
        members = list(SystemEventType)
        assert len(members) == 9

    def test_expected_values(self):
        expected = {
            "mode_switch",
            "strategy_promoted",
            "trade_executed",
            "trade_failed",
            "account_sync",
            "risk_limit_triggered",
            "kill_switch_toggled",
            "bot_enabled",
            "bot_disabled",
        }
        assert {e.value for e in SystemEventType} == expected


# ── UserTradingSession ──────────────────────────────────────────────────────


class TestUserTradingSession:
    def test_defaults_after_flush(self, session):
        _seed_user(session)
        obj = UserTradingSession(user_id=1)
        session.add(obj)
        session.flush()
        session.refresh(obj)
        assert obj.user_id == 1
        assert obj.active_mode == TradingModeEnum.PAPER

    def test_table_exists(self, engine):
        inspector = inspect(engine)
        assert "user_trading_sessions" in inspector.get_table_names()


# ── StrategyTemplate ────────────────────────────────────────────────────────


class TestStrategyTemplate:
    def test_defaults_after_flush(self, session):
        _seed_user(session)
        obj = StrategyTemplate(
            user_id=1,
            name="Test Strategy",
            conditions={"rsi_below": 30},
        )
        session.add(obj)
        session.flush()
        session.refresh(obj)
        assert obj.action == "BUY"
        assert obj.stop_loss_pct == 0.02
        assert obj.take_profit_pct == 0.05
        assert obj.timeframe == "1D"
        assert obj.description is None
        assert obj.diagnostics is None

    def test_table_has_user_index(self, engine):
        inspector = inspect(engine)
        indexes = inspector.get_indexes("strategy_templates")
        idx_names = [idx["name"] for idx in indexes]
        assert "ix_strategy_template_user" in idx_names


# ── StrategyInstance ────────────────────────────────────────────────────────


class TestStrategyInstance:
    def test_defaults_after_flush(self, session):
        _seed_user(session)
        # Need a template first
        tmpl = StrategyTemplate(
            user_id=1,
            name="Tmpl for instance test",
            conditions={"rsi_below": 30},
        )
        session.add(tmpl)
        session.flush()

        obj = StrategyInstance(
            template_id=tmpl.id,
            user_id=1,
            mode=TradingModeEnum.PAPER,
        )
        session.add(obj)
        session.flush()
        session.refresh(obj)
        assert obj.is_active is True
        assert obj.position_size_pct == 0.1
        assert obj.max_position_value is None
        assert obj.nickname is None
        assert obj.promoted_from_id is None

    def test_table_has_user_mode_index(self, engine):
        inspector = inspect(engine)
        indexes = inspector.get_indexes("strategy_instances")
        idx_names = [idx["name"] for idx in indexes]
        assert "ix_strategy_instance_user_mode" in idx_names


# ── UserBrokerAccount ───────────────────────────────────────────────────────


class TestUserBrokerAccount:
    def test_instantiation(self):
        obj = UserBrokerAccount(
            user_id=1,
            connection_id=10,
            broker_account_id="ACC-123",
            account_type="margin",
        )
        assert obj.broker_account_id == "ACC-123"
        assert obj.account_type == "margin"
        assert obj.nickname is None

    def test_table_has_user_type_index(self, engine):
        inspector = inspect(engine)
        indexes = inspector.get_indexes("user_broker_accounts")
        idx_names = [idx["name"] for idx in indexes]
        assert "ix_user_broker_acct_user_type" in idx_names


# ── UserRiskLimits (composite PK) ──────────────────────────────────────────


class TestUserRiskLimits:
    def test_defaults_after_flush(self, session):
        _seed_user(session)
        obj = UserRiskLimits(user_id=1, mode=TradingModeEnum.PAPER)
        session.add(obj)
        session.flush()
        session.refresh(obj)
        assert obj.daily_loss_limit is None
        assert obj.max_position_size_pct == 0.25
        assert obj.max_open_positions == 10
        assert obj.kill_switch_active is False
        assert obj.live_bot_trading_confirmed is False

    def test_composite_pk(self, engine):
        inspector = inspect(engine)
        pk = inspector.get_pk_constraint("user_risk_limits")
        pk_cols = pk["constrained_columns"]
        assert "user_id" in pk_cols
        assert "mode" in pk_cols
        assert len(pk_cols) == 2

    def test_two_modes_same_user(self, session):
        """Both paper and live risk limits can coexist for the same user."""
        _seed_user(session, 99)
        paper = UserRiskLimits(user_id=99, mode=TradingModeEnum.PAPER)
        live = UserRiskLimits(user_id=99, mode=TradingModeEnum.LIVE)
        session.add_all([paper, live])
        session.flush()

        rows = (
            session.query(UserRiskLimits)
            .filter(UserRiskLimits.user_id == 99)
            .all()
        )
        assert len(rows) == 2
        modes = {r.mode for r in rows}
        assert modes == {TradingModeEnum.PAPER, TradingModeEnum.LIVE}


# ── SystemEvent ─────────────────────────────────────────────────────────────


class TestSystemEvent:
    def test_defaults_after_flush(self, session):
        _seed_user(session)
        obj = SystemEvent(
            user_id=1,
            event_type=SystemEventType.MODE_SWITCH,
            mode=TradingModeEnum.LIVE,
        )
        session.add(obj)
        session.flush()
        session.refresh(obj)
        assert obj.severity == "info"
        assert obj.description is None

    def test_table_has_indexes(self, engine):
        inspector = inspect(engine)
        indexes = inspector.get_indexes("system_events")
        idx_names = [idx["name"] for idx in indexes]
        assert "ix_system_events_user_time" in idx_names
        assert "ix_system_events_type" in idx_names

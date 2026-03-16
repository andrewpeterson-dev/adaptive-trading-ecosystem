"""Tests for trade analytics service (services/ai_core/analytics/trade_analytics.py)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base
from db.models import User  # noqa: F401
from db.cerberus_models import CerberusTrade

from services.ai_core.analytics.trade_analytics import TradeAnalyticsService

TEST_DB_URL = "sqlite+aiosqlite:///"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(session_factory):
    async with session_factory() as sess:
        yield sess


async def _seed_user(session: AsyncSession) -> int:
    user = User(email="test@example.com", password_hash="hash", display_name="Test")
    session.add(user)
    await session.flush()
    return user.id


async def _seed_trades(session: AsyncSession, user_id: int) -> list[CerberusTrade]:
    """Seed 5 trades for testing analytics queries."""
    now = datetime.utcnow()
    trades = [
        CerberusTrade(
            id=str(uuid.uuid4()), user_id=user_id, symbol="AAPL", side="buy",
            quantity=100, entry_price=150.0, exit_price=160.0, entry_ts=now - timedelta(days=5),
            exit_ts=now - timedelta(days=4), gross_pnl=1000.0, net_pnl=990.0,
            return_pct=0.0667, strategy_tag="momentum", bot_id="bot-1",
        ),
        CerberusTrade(
            id=str(uuid.uuid4()), user_id=user_id, symbol="AAPL", side="sell",
            quantity=50, entry_price=162.0, exit_price=155.0, entry_ts=now - timedelta(days=3),
            exit_ts=now - timedelta(days=2), gross_pnl=-350.0, net_pnl=-360.0,
            return_pct=-0.0432, strategy_tag="momentum", bot_id="bot-1",
        ),
        CerberusTrade(
            id=str(uuid.uuid4()), user_id=user_id, symbol="TSLA", side="buy",
            quantity=20, entry_price=200.0, exit_price=220.0, entry_ts=now - timedelta(days=10),
            exit_ts=now - timedelta(days=7), gross_pnl=400.0, net_pnl=390.0,
            return_pct=0.1, strategy_tag="breakout", bot_id="bot-2",
        ),
        CerberusTrade(
            id=str(uuid.uuid4()), user_id=user_id, symbol="SPY", side="buy",
            quantity=200, entry_price=450.0, exit_price=455.0, entry_ts=now - timedelta(days=2),
            exit_ts=now - timedelta(days=1), gross_pnl=1000.0, net_pnl=980.0,
            return_pct=0.0111, strategy_tag="momentum",
        ),
        CerberusTrade(
            id=str(uuid.uuid4()), user_id=user_id, symbol="MSFT", side="buy",
            quantity=30, entry_price=380.0, exit_price=370.0, entry_ts=now - timedelta(days=1),
            exit_ts=now, gross_pnl=-300.0, net_pnl=-310.0,
            return_pct=-0.0263, strategy_tag="breakout",
        ),
    ]
    for t in trades:
        session.add(t)
    await session.flush()
    return trades


def _patch_get_session(session_factory):
    """Return a context manager that patches get_session where it's used by the analytics service."""
    @asynccontextmanager
    async def _mock_get_session():
        async with session_factory() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise

    return patch("services.ai_core.analytics.trade_analytics.get_session", _mock_get_session)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTradeAnalytics:
    @pytest.mark.asyncio
    async def test_get_best_trade(self, session, session_factory):
        uid = await _seed_user(session)
        await _seed_trades(session, uid)
        await session.commit()

        svc = TradeAnalyticsService()
        with _patch_get_session(session_factory):
            result = await svc.get_best_trade(uid)

        assert result["return_pct"] == 0.1
        assert result["symbol"] == "TSLA"

    @pytest.mark.asyncio
    async def test_get_best_trade_no_trades(self, session, session_factory):
        uid = await _seed_user(session)
        await session.commit()

        svc = TradeAnalyticsService()
        with _patch_get_session(session_factory):
            result = await svc.get_best_trade(uid)

        assert "message" in result

    @pytest.mark.asyncio
    async def test_get_worst_trades(self, session, session_factory):
        uid = await _seed_user(session)
        await _seed_trades(session, uid)
        await session.commit()

        svc = TradeAnalyticsService()
        with _patch_get_session(session_factory):
            result = await svc.get_worst_trades(uid, limit=2)

        assert len(result) == 2
        # Worst first
        assert result[0]["return_pct"] <= result[1]["return_pct"]

    @pytest.mark.asyncio
    async def test_get_total_volume(self, session, session_factory):
        uid = await _seed_user(session)
        await _seed_trades(session, uid)
        await session.commit()

        svc = TradeAnalyticsService()
        with _patch_get_session(session_factory):
            result = await svc.get_total_volume(uid)

        assert result["trade_count"] == 5
        assert result["total_volume"] > 0

    @pytest.mark.asyncio
    async def test_get_strategy_performance(self, session, session_factory):
        uid = await _seed_user(session)
        await _seed_trades(session, uid)
        await session.commit()

        svc = TradeAnalyticsService()
        with _patch_get_session(session_factory):
            result = await svc.get_strategy_performance(uid)

        assert len(result) >= 2  # momentum + breakout
        tags = {r["strategy_tag"] for r in result}
        assert "momentum" in tags
        assert "breakout" in tags

        # Check win_rate makes sense
        for r in result:
            assert 0 <= r["win_rate"] <= 1

    @pytest.mark.asyncio
    async def test_get_symbol_performance(self, session, session_factory):
        uid = await _seed_user(session)
        await _seed_trades(session, uid)
        await session.commit()

        svc = TradeAnalyticsService()
        with _patch_get_session(session_factory):
            result = await svc.get_symbol_performance(uid)

        symbols = {r["symbol"] for r in result}
        assert "AAPL" in symbols
        assert "TSLA" in symbols

    @pytest.mark.asyncio
    async def test_get_hold_time_stats(self, session, session_factory):
        uid = await _seed_user(session)
        await _seed_trades(session, uid)
        await session.commit()

        svc = TradeAnalyticsService()
        with _patch_get_session(session_factory):
            result = await svc.get_hold_time_stats(uid)

        assert result["trade_count"] == 5
        assert result["avg_hold_seconds"] > 0
        assert result["avg_hold_hours"] > 0

    @pytest.mark.asyncio
    async def test_get_hold_time_stats_no_trades(self, session, session_factory):
        uid = await _seed_user(session)
        await session.commit()

        svc = TradeAnalyticsService()
        with _patch_get_session(session_factory):
            result = await svc.get_hold_time_stats(uid)

        assert result["trade_count"] == 0
        assert "message" in result

    @pytest.mark.asyncio
    async def test_get_bot_performance(self, session, session_factory):
        uid = await _seed_user(session)
        await _seed_trades(session, uid)
        await session.commit()

        svc = TradeAnalyticsService()
        with _patch_get_session(session_factory):
            result = await svc.get_bot_performance("bot-1")

        assert result["bot_id"] == "bot-1"
        assert result["trade_count"] == 2  # Two trades with bot_id="bot-1"

    @pytest.mark.asyncio
    async def test_get_bot_performance_no_trades(self, session, session_factory):
        await _seed_user(session)
        await session.commit()

        svc = TradeAnalyticsService()
        with _patch_get_session(session_factory):
            result = await svc.get_bot_performance("nonexistent")

        assert result["trade_count"] == 0

    @pytest.mark.asyncio
    async def test_strategy_performance_filtered(self, session, session_factory):
        uid = await _seed_user(session)
        await _seed_trades(session, uid)
        await session.commit()

        svc = TradeAnalyticsService()
        with _patch_get_session(session_factory):
            result = await svc.get_strategy_performance(uid, strategy_tag="momentum")

        assert len(result) == 1
        assert result[0]["strategy_tag"] == "momentum"

    @pytest.mark.asyncio
    async def test_symbol_performance_filtered(self, session, session_factory):
        uid = await _seed_user(session)
        await _seed_trades(session, uid)
        await session.commit()

        svc = TradeAnalyticsService()
        with _patch_get_session(session_factory):
            result = await svc.get_symbol_performance(uid, symbol="AAPL")

        assert len(result) == 1
        assert result[0]["symbol"] == "AAPL"
        assert result[0]["trade_count"] == 2

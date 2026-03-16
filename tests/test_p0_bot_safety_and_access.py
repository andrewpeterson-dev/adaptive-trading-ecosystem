from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from db.cerberus_models import BotStatus, CerberusBot, CerberusBotVersion, CerberusTrade, TradeDecision
from db.database import Base
from db.models import User
from services.bot_engine.runner import BotRunner
from services.reasoning_engine.engine import ReasoningEngine
from services.strategy_learning_engine import StrategyLearningEngine

TEST_DB_URL = "sqlite+aiosqlite:///"


@pytest.fixture
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


@pytest.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def session(session_factory):
    async with session_factory() as sess:
        yield sess


def _session_override(session_factory):
    @asynccontextmanager
    async def _mock_get_session():
        async with session_factory() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise

    return _mock_get_session


async def _seed_user(
    session: AsyncSession,
    *,
    email: str,
    is_admin: bool = False,
) -> User:
    user = User(
        email=email,
        password_hash="hash",
        display_name=email.split("@", 1)[0],
        email_verified=True,
        is_active=True,
        is_admin=is_admin,
    )
    session.add(user)
    await session.flush()
    return user


def _build_app(router, *, prefix: str, user_id: int) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def mock_auth(request: Request, call_next):
        request.state.user_id = user_id
        request.state.is_admin = False
        return await call_next(request)

    app.include_router(router, prefix=prefix)
    return app


def _fake_bars(*, close: float, count: int = 80) -> list[dict]:
    bars: list[dict] = []
    start = 1_700_000_000
    for index in range(count):
        bars.append(
            {
                "time": start + (index * 86_400),
                "open": close - 1,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": 1_000_000 + index,
            }
        )
    return bars


class TestReasoningAccessControl:
    @pytest.mark.anyio
    async def test_reasoning_routes_reject_other_users_bot(self, session, session_factory):
        from api.routes.reasoning import router

        owner = await _seed_user(session, email="owner@example.com")
        intruder = await _seed_user(session, email="intruder@example.com")
        bot = CerberusBot(
            id="bot-owned",
            user_id=owner.id,
            name="Owned Bot",
            status=BotStatus.RUNNING,
        )
        decision = TradeDecision(
            id="decision-1",
            bot_id=bot.id,
            symbol="SPY",
            strategy_signal="BUY",
            context_risk_level="LOW",
            ai_confidence=0.8,
            decision="EXECUTE",
            reasoning="Looks good.",
            size_adjustment=1.0,
            delay_seconds=0,
            events_considered=[],
            model_used="test",
        )
        session.add_all([bot, decision])
        await session.commit()

        app = _build_app(router, prefix="/api/reasoning", user_id=intruder.id)
        mock_get_session = _session_override(session_factory)

        with patch("services.security.access_control.get_session", mock_get_session):
            with patch("api.routes.reasoning.get_session", mock_get_session):
                client = TestClient(app)
                response = client.get(f"/api/reasoning/bots/{bot.id}/decisions")

        assert response.status_code == 404
        assert response.json()["detail"] == "Bot not found"


class TestAdminGuards:
    @pytest.mark.anyio
    async def test_operational_routes_require_admin(self, session, session_factory):
        from api.routes.auto_loop import router as auto_loop_router
        from api.routes.lighthouse import router as lighthouse_router
        from api.routes.llm_status import router as llm_status_router
        from api.routes.system import router as system_router

        member = await _seed_user(session, email="member@example.com", is_admin=False)
        await session.commit()
        mock_get_session = _session_override(session_factory)

        apps = [
            (_build_app(system_router, prefix="/api/system", user_id=member.id), "/api/system/config"),
            (_build_app(lighthouse_router, prefix="/api/system", user_id=member.id), "/api/system/lighthouse"),
            (_build_app(auto_loop_router, prefix="/api/system", user_id=member.id), "/api/system/auto-loop/status"),
            (_build_app(llm_status_router, prefix="/api/system", user_id=member.id), "/api/system/llm-status"),
        ]

        with patch("services.security.access_control.get_session", mock_get_session):
            for app, path in apps:
                client = TestClient(app)
                response = client.get(path)
                assert response.status_code == 403
                assert response.json()["detail"] == "Admin access required"


class TestDeployAndLearningSafety:
    @pytest.mark.anyio
    async def test_deploy_rejects_unvalidated_current_version(self, session, session_factory):
        from api.routes.ai_tools import router

        user = await _seed_user(session, email="bot-owner@example.com")
        bot = CerberusBot(
            id="bot-awaiting-backtest",
            user_id=user.id,
            name="Awaiting Backtest",
            status=BotStatus.DRAFT,
        )
        version = CerberusBotVersion(
            id="version-awaiting-backtest",
            bot_id=bot.id,
            version_number=1,
            config_json={
                "symbols": ["SPY"],
                "timeframe": "1D",
                "action": "BUY",
                "conditions": [{"indicator": "rsi", "operator": ">", "value": 55, "params": {"period": 14}}],
            },
            diff_summary="staged by learning engine",
            created_by="learning_engine",
            backtest_required=True,
        )
        bot.current_version_id = version.id
        session.add_all([bot, version])
        await session.commit()

        app = _build_app(router, prefix="/api/ai/tools", user_id=user.id)
        mock_get_session = _session_override(session_factory)

        with patch("api.routes.ai_tools.get_session", mock_get_session):
            client = TestClient(app)
            response = client.post(f"/api/ai/tools/bots/{bot.id}/deploy")

        assert response.status_code == 409
        assert "awaiting backtest validation" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_learning_engine_stages_new_version_without_promoting_it(self, session, session_factory):
        user = await _seed_user(session, email="learner@example.com")
        bot = CerberusBot(
            id="learning-bot",
            user_id=user.id,
            name="Learning Bot",
            status=BotStatus.RUNNING,
            learning_enabled=True,
            learning_status_json={},
        )
        current_version = CerberusBotVersion(
            id="learning-version-1",
            bot_id=bot.id,
            version_number=1,
            config_json={
                "symbols": ["SPY"],
                "timeframe": "1D",
                "action": "BUY",
                "strategy_type": "ai_generated",
                "conditions": [{"indicator": "rsi", "operator": ">", "value": 55, "params": {"period": 14}}],
                "stop_loss_pct": 0.02,
                "take_profit_pct": 0.05,
                "position_size_pct": 0.10,
                "feature_signals": ["rsi"],
                "learning": {"enabled": True, "methods": ["reinforcement_learning"], "cadence_minutes": 0},
            },
            diff_summary="initial",
            created_by="user",
            backtest_required=False,
        )
        bot.current_version_id = current_version.id
        losing_trade = CerberusTrade(
            id="trade-loss-1",
            user_id=user.id,
            bot_id=bot.id,
            symbol="SPY",
            side="buy",
            quantity=1,
            entry_price=100.0,
            exit_price=90.0,
            gross_pnl=-10.0,
            net_pnl=-10.0,
            return_pct=-0.10,
            entry_ts=datetime.utcnow() - timedelta(days=2),
            exit_ts=datetime.utcnow() - timedelta(days=1),
        )
        session.add_all([bot, current_version, losing_trade])
        await session.commit()

        engine = StrategyLearningEngine()
        engine._min_trades = 1
        mock_get_session = _session_override(session_factory)

        with patch("services.strategy_learning_engine.get_session", mock_get_session):
            result = await engine.optimize_bot(bot.id)

        assert result is not None

        async with session_factory() as verification_session:
            bot_result = await verification_session.execute(
                select(CerberusBot).where(CerberusBot.id == bot.id)
            )
            refreshed_bot = bot_result.scalar_one()
            version_result = await verification_session.execute(
                select(CerberusBotVersion)
                .where(CerberusBotVersion.bot_id == bot.id)
                .order_by(CerberusBotVersion.version_number.asc())
            )
            versions = list(version_result.scalars().all())

        assert len(versions) == 2
        # In paper mode (live_trading_enabled=False), optimized versions are
        # auto-promoted and backtest_required is False.
        # In live mode, they would be staged with backtest_required=True.
        from config.settings import get_settings
        if get_settings().live_trading_enabled:
            assert refreshed_bot.current_version_id == current_version.id
            assert refreshed_bot.learning_status_json["status"] == "awaiting_backtest"
            assert versions[-1].backtest_required is True
        else:
            assert refreshed_bot.current_version_id == versions[-1].id
            assert refreshed_bot.learning_status_json["status"] == "promoted"
            assert versions[-1].backtest_required is False
        assert refreshed_bot.learning_status_json["stagedVersionId"] == versions[-1].id


class TestReasoningFailClosed:
    @pytest.mark.anyio
    async def test_reasoning_engine_delays_trade_when_llm_output_is_invalid(self, session_factory):
        bot = CerberusBot(
            id="reasoning-bot",
            user_id=123,
            name="Reasoning Bot",
            status=BotStatus.RUNNING,
        )
        engine = ReasoningEngine()
        mock_get_session = _session_override(session_factory)
        routed_provider = SimpleNamespace(
            complete=AsyncMock(return_value=SimpleNamespace(content="definitely not json"))
        )
        routed_decision = SimpleNamespace(
            provider=routed_provider,
            model="gpt-4.1",
            provider_name="openai",
        )

        with patch("services.reasoning_engine.engine.get_session", mock_get_session):
            with patch("services.ai_core.model_router.ModelRouter.route", return_value=routed_decision):
                result = await engine._try_llm_reasoning(
                    bot=bot,
                    symbol="SPY",
                    signal="BUY",
                    strategy_config={"ai_context": {"ai_thinking": "Watch macro risk."}},
                    events_dicts=[],
                    vix=22.5,
                )

        assert result["decision"] == "DELAY_TRADE"
        assert result["delay_seconds"] == 300
        assert result["size_adjustment"] == 0.0


class TestBotRunnerSafety:
    @pytest.mark.anyio
    async def test_runner_does_not_reenter_when_symbol_position_is_open(self):
        runner = BotRunner()
        bot = CerberusBot(id="runner-bot", user_id=1, name="Runner Bot", status=BotStatus.RUNNING)
        open_trade = CerberusTrade(
            id="open-trade",
            user_id=1,
            bot_id=bot.id,
            symbol="SPY",
            side="buy",
            quantity=5,
            entry_price=100.0,
        )
        config = {"timeframe": "1D", "exit_conditions": []}
        conditions = [{"indicator": "rsi", "operator": "<", "value": 101, "params": {"period": 14}}]

        runner._fetch_bars = AsyncMock(return_value=_fake_bars(close=100.0))
        runner._get_open_trades = AsyncMock(return_value=[open_trade])
        runner._close_open_trades = AsyncMock()
        runner._execute_trade = AsyncMock()

        await runner._evaluate_symbol(
            bot,
            config,
            "SPY",
            conditions,
            "BUY",
            0.1,
            {"vix": 20.0, "daily_pnl_pct": 0.0, "positions": {}, "total_equity": 100_000.0},
        )

        runner._close_open_trades.assert_not_awaited()
        runner._execute_trade.assert_not_awaited()

    @pytest.mark.anyio
    async def test_runner_closes_open_position_on_take_profit(self):
        runner = BotRunner()
        bot = CerberusBot(id="runner-bot", user_id=1, name="Runner Bot", status=BotStatus.RUNNING)
        open_trade = CerberusTrade(
            id="open-trade",
            user_id=1,
            bot_id=bot.id,
            symbol="SPY",
            side="buy",
            quantity=5,
            entry_price=100.0,
        )
        config = {"timeframe": "1D", "take_profit_pct": 0.05, "exit_conditions": []}
        conditions = [{"indicator": "rsi", "operator": "<", "value": 101, "params": {"period": 14}}]

        runner._fetch_bars = AsyncMock(return_value=_fake_bars(close=106.0))
        runner._get_open_trades = AsyncMock(return_value=[open_trade])
        runner._close_open_trades = AsyncMock()
        runner._execute_trade = AsyncMock()

        await runner._evaluate_symbol(
            bot,
            config,
            "SPY",
            conditions,
            "BUY",
            0.1,
            {"vix": 20.0, "daily_pnl_pct": 0.0, "positions": {}, "total_equity": 100_000.0},
        )

        runner._close_open_trades.assert_awaited_once()
        runner._execute_trade.assert_not_awaited()

    @pytest.mark.anyio
    async def test_runner_passes_real_risk_context_into_reasoning(self):
        runner = BotRunner()
        bot = CerberusBot(id="runner-bot", user_id=1, name="Runner Bot", status=BotStatus.RUNNING)
        config = {"timeframe": "1D", "exit_conditions": []}
        conditions = [{"indicator": "rsi", "operator": "<", "value": 101, "params": {"period": 14}}]

        runner._fetch_bars = AsyncMock(return_value=_fake_bars(close=100.0))
        runner._get_open_trades = AsyncMock(return_value=[])
        runner._execute_trade = AsyncMock(
            return_value=SimpleNamespace(id="trade-1", entry_ts=datetime.utcnow())
        )
        runner._reasoning_engine.evaluate = AsyncMock(
            return_value=SimpleNamespace(
                decision="EXECUTE",
                delay_seconds=0,
                size_adjustment=1.0,
                reasoning="Proceed.",
                ai_confidence=0.85,
            )
        )

        with patch("services.bot_memory.journal.record_trade", AsyncMock()):
            await runner._evaluate_symbol(
                bot,
                config,
                "SPY",
                conditions,
                "BUY",
                0.1,
                {
                    "vix": 22.5,
                    "daily_pnl_pct": -1.5,
                    "positions": {"SPY": {"quantity": 10.0, "mark_price": 100.0}},
                    "total_equity": 4_000.0,
                },
            )

        kwargs = runner._reasoning_engine.evaluate.await_args.kwargs
        assert kwargs["vix"] == 22.5
        assert kwargs["daily_pnl_pct"] == pytest.approx(-1.5)
        assert kwargs["portfolio_exposure"] == pytest.approx(0.25)

    @pytest.mark.anyio
    async def test_runner_does_not_trade_when_reasoning_engine_errors(self):
        runner = BotRunner()
        bot = CerberusBot(id="runner-bot", user_id=1, name="Runner Bot", status=BotStatus.RUNNING)
        config = {"timeframe": "1D", "exit_conditions": []}
        conditions = [{"indicator": "rsi", "operator": "<", "value": 101, "params": {"period": 14}}]

        runner._fetch_bars = AsyncMock(return_value=_fake_bars(close=100.0))
        runner._get_open_trades = AsyncMock(return_value=[])
        runner._execute_trade = AsyncMock()
        runner._reasoning_engine.evaluate = AsyncMock(side_effect=RuntimeError("llm down"))

        await runner._evaluate_symbol(
            bot,
            config,
            "SPY",
            conditions,
            "BUY",
            0.1,
            {"vix": 18.0, "daily_pnl_pct": 0.0, "positions": {}, "total_equity": 100_000.0},
        )

        runner._execute_trade.assert_not_awaited()

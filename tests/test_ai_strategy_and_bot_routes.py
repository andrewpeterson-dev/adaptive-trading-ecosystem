"""Tests for AI strategy generation and bot deployment routes."""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from config.settings import get_settings
from db.cerberus_models import BotStatus, CerberusBot, CerberusBotVersion
from db.database import Base
from db.models import StrategyInstance, StrategyTemplate, TradingModeEnum, User
from services.security.rate_limit import rate_limiter

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


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    rate_limiter.clear()
    yield
    rate_limiter.clear()


async def _seed_user(session: AsyncSession) -> int:
    user = User(email="ai-routes@example.com", password_hash="hash", display_name="AI Routes")
    session.add(user)
    await session.flush()
    return user.id


def _fake_market_bars(count: int = 600) -> list[dict]:
    import math

    bars: list[dict] = []
    base_ts = 1_700_000_000
    for index in range(count):
        close = 100 + (index * 0.08) + (math.sin(index / 5) * 4.5)
        bars.append(
            {
                "t": base_ts + (index * 86_400),
                "o": close - 0.35,
                "h": close + 0.85,
                "l": close - 0.85,
                "c": close,
                "v": 1_000_000 + (index * 1000),
            }
        )
    return bars


def _build_app(session_factory, user_id: int) -> tuple[FastAPI, object]:
    from api.routes.ai_tools import router

    app = FastAPI()

    @app.middleware("http")
    async def mock_auth(request: Request, call_next):
        request.state.user_id = user_id
        return await call_next(request)

    @asynccontextmanager
    async def _mock_get_session():
        async with session_factory() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise

    app.include_router(router, prefix="/api/ai/tools")
    return app, _mock_get_session


def _build_strategies_app(
    session_factory,
    user_id: int,
    mode: TradingModeEnum = TradingModeEnum.PAPER,
) -> tuple[FastAPI, object]:
    from api.routes.strategies import router

    app = FastAPI()

    @app.middleware("http")
    async def mock_auth(request: Request, call_next):
        request.state.user_id = user_id
        request.state.trading_mode = mode
        return await call_next(request)

    @asynccontextmanager
    async def _mock_get_session():
        async with session_factory() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise

    app.include_router(router, prefix="/api")
    return app, _mock_get_session


class TestAIStrategyGeneration:
    @pytest.mark.anyio
    async def test_generate_strategy_returns_builder_draft(self, session, session_factory):
        user_id = await _seed_user(session)
        await session.commit()
        app, mock_get_session = _build_app(session_factory, user_id)

        settings = get_settings()
        old_openai = settings.openai_api_key
        old_anthropic = settings.anthropic_api_key
        settings.openai_api_key = ""
        settings.anthropic_api_key = ""

        try:
            with patch("api.routes.ai_tools.get_session", mock_get_session):
                client = TestClient(app)
                response = client.post(
                    "/api/ai/tools/generate-strategy",
                    json={"prompt": "Create a volatility breakout strategy for SPY options."},
                )
        finally:
            settings.openai_api_key = old_openai
            settings.anthropic_api_key = old_anthropic

        assert response.status_code == 200
        payload = response.json()
        assert payload["builder_draft"]["strategyType"] == "ai_generated"
        assert payload["compiled_strategy"]["strategy_type"] == "ai_generated"
        assert payload["compiled_strategy"]["condition_groups"]
        assert payload["compiled_strategy"]["symbols"] == ["SPY"]

    @pytest.mark.anyio
    async def test_generate_strategy_rate_limits_requests(self, session, session_factory):
        user_id = await _seed_user(session)
        await session.commit()
        app, mock_get_session = _build_app(session_factory, user_id)

        with (
            patch("api.routes.ai_tools.get_session", mock_get_session),
            patch("services.ai_strategy_service.AIStrategyService.generate", AsyncMock(return_value={"builder_draft": {}, "compiled_strategy": {}})),
        ):
            client = TestClient(app)
            for _ in range(12):
                response = client.post(
                    "/api/ai/tools/generate-strategy",
                    json={"prompt": "Build a momentum strategy."},
                )
                assert response.status_code == 200

            response = client.post(
                "/api/ai/tools/generate-strategy",
                json={"prompt": "Build a momentum strategy."},
            )

        assert response.status_code == 429


class TestBotDeploymentFromStrategy:
    @pytest.mark.anyio
    async def test_create_bot_from_strategy_instance(self, session, session_factory):
        user_id = await _seed_user(session)
        template = StrategyTemplate(
            user_id=user_id,
            name="AI Momentum Strategy",
            description="AI-generated test strategy",
            conditions=[
                {
                    "indicator": "rsi",
                    "operator": ">",
                    "value": 55,
                    "params": {"period": 14},
                    "action": "BUY",
                }
            ],
            condition_groups=[
                {
                    "id": "group_a",
                    "label": "Group A",
                    "conditions": [
                        {
                            "indicator": "rsi",
                            "operator": ">",
                            "value": 55,
                            "params": {"period": 14},
                            "action": "BUY",
                        }
                    ],
                }
            ],
            action="BUY",
            stop_loss_pct=0.02,
            take_profit_pct=0.05,
            timeframe="1D",
            symbols=["SPY"],
            strategy_type="ai_generated",
            source_prompt="Build a momentum bot for SPY",
            ai_context={
                "overview": "AI overview",
                "feature_signals": ["rsi"],
                "learning_plan": {
                    "enabled": True,
                    "cadence_minutes": 240,
                    "methods": ["reinforcement_learning"],
                    "goals": ["improve_sharpe_ratio"],
                },
            },
        )
        session.add(template)
        await session.flush()

        instance = StrategyInstance(
            template_id=template.id,
            user_id=user_id,
            mode=TradingModeEnum.PAPER,
            is_active=True,
            position_size_pct=0.1,
        )
        session.add(instance)
        await session.commit()

        app, mock_get_session = _build_app(session_factory, user_id)
        with patch("api.routes.ai_tools.get_session", mock_get_session):
            client = TestClient(app)
            response = client.post(
                "/api/ai/tools/bots/from-strategy",
                json={"strategy_id": instance.id, "name": "Momentum Bot"},
            )

            assert response.status_code == 200
            bot_payload = response.json()
            assert bot_payload["strategy_id"] == instance.id

            list_response = client.get("/api/ai/tools/bots")
            assert list_response.status_code == 200
            bots = list_response.json()
            assert len(bots) == 1
            assert bots[0]["strategyId"] == instance.id
            assert bots[0]["strategyType"] == "ai_generated"
            assert bots[0]["learningStatus"]["enabled"] is True

        result = await session.execute(select(CerberusBot))
        bot = result.scalar_one()
        assert bot.name == "Momentum Bot"

        version_result = await session.execute(select(CerberusBotVersion))
        version = version_result.scalar_one()
        assert version.config_json["strategy_id"] == instance.id
        assert version.config_json["strategy_type"] == "ai_generated"

    @pytest.mark.anyio
    async def test_create_bot_normalizes_chat_strategy_schema(self, session, session_factory):
        user_id = await _seed_user(session)
        await session.commit()
        app, mock_get_session = _build_app(session_factory, user_id)

        with patch("api.routes.ai_tools.get_session", mock_get_session):
            client = TestClient(app)
            response = client.post(
                "/api/ai/tools/create-bot",
                json={
                    "name": "Chat Strategy Bot",
                    "strategy_json": {
                        "name": "Chat Strategy",
                        "description": "Generated from the legacy AI strategy prompt.",
                        "action": "BUY",
                        "stopLossPct": 2,
                        "takeProfitPct": 5,
                        "positionPct": 10,
                        "timeframe": "1D",
                        "symbols": ["SPY"],
                        "strategyType": "ai_generated",
                        "entryConditions": [
                            {
                                "logic": "AND",
                                "indicator": "rsi",
                                "params": {"period": 14},
                                "operator": ">",
                                "value": 55,
                                "signal": "Momentum confirmation",
                            }
                        ],
                        "exitConditions": [],
                    },
                },
            )

            assert response.status_code == 200
            payload = response.json()
            assert payload["status"] == "draft"

            deploy_response = client.post(f"/api/ai/tools/bots/{payload['bot_id']}/deploy")
            assert deploy_response.status_code == 200
            assert deploy_response.json()["status"] == "running"

        version_result = await session.execute(select(CerberusBotVersion))
        version = version_result.scalar_one()
        assert version.config_json["strategy_type"] == "ai_generated"
        assert version.config_json["stop_loss_pct"] == pytest.approx(0.02)
        assert version.config_json["take_profit_pct"] == pytest.approx(0.05)
        assert version.config_json["position_size_pct"] == pytest.approx(0.1)
        assert version.config_json["conditions"][0]["indicator"] == "rsi"
        assert version.config_json["condition_groups"][0]["conditions"][0]["indicator"] == "rsi"

    @pytest.mark.anyio
    async def test_create_bot_rejects_non_executable_strategy(self, session, session_factory):
        user_id = await _seed_user(session)
        await session.commit()
        app, mock_get_session = _build_app(session_factory, user_id)

        with patch("api.routes.ai_tools.get_session", mock_get_session):
            client = TestClient(app)
            response = client.post(
                "/api/ai/tools/create-bot",
                json={
                    "name": "Broken Bot",
                    "strategy_json": {
                        "name": "Broken Strategy",
                        "action": "BUY",
                        "timeframe": "1D",
                        "symbols": ["SPY"],
                        "conditions": [],
                        "condition_groups": [],
                    },
                },
            )

        assert response.status_code == 400
        assert "at least one executable condition is required" in response.json()["detail"]

        result = await session.execute(select(CerberusBot))
        assert result.scalars().all() == []

    @pytest.mark.anyio
    async def test_create_bot_from_strategy_rejects_empty_saved_strategy(self, session, session_factory):
        user_id = await _seed_user(session)
        template = StrategyTemplate(
            user_id=user_id,
            name="Empty Strategy",
            description="No rules defined",
            conditions=[],
            condition_groups=[],
            action="BUY",
            stop_loss_pct=0.02,
            take_profit_pct=0.05,
            timeframe="1D",
            symbols=["SPY"],
            strategy_type="manual",
        )
        session.add(template)
        await session.flush()

        instance = StrategyInstance(
            template_id=template.id,
            user_id=user_id,
            mode=TradingModeEnum.PAPER,
            is_active=True,
            position_size_pct=0.1,
        )
        session.add(instance)
        await session.commit()

        app, mock_get_session = _build_app(session_factory, user_id)
        with patch("api.routes.ai_tools.get_session", mock_get_session):
            client = TestClient(app)
            response = client.post(
                "/api/ai/tools/bots/from-strategy",
                json={"strategy_id": instance.id, "name": "Empty Strategy Bot"},
            )

        assert response.status_code == 400
        assert "Saved strategy cannot be deployed" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_deploy_bot_rejects_missing_current_version(self, session, session_factory):
        user_id = await _seed_user(session)
        bot = CerberusBot(
            id="bot-without-version",
            user_id=user_id,
            name="Draft Bot",
            status=BotStatus.DRAFT,
            learning_enabled=False,
        )
        session.add(bot)
        await session.commit()

        app, mock_get_session = _build_app(session_factory, user_id)
        with patch("api.routes.ai_tools.get_session", mock_get_session):
            client = TestClient(app)
            response = client.post("/api/ai/tools/bots/bot-without-version/deploy")

        assert response.status_code == 400
        assert response.json()["detail"] == "Bot has no deployable version"


class TestBacktestFromSavedStrategy:
    @pytest.mark.anyio
    async def test_backtest_loads_strategy_instance_template(self, session, session_factory):
        user_id = await _seed_user(session)
        template = StrategyTemplate(
            user_id=user_id,
            name="Backtestable Strategy",
            description="Strategy persisted as template + instance.",
            conditions=[
                {
                    "indicator": "rsi",
                    "operator": ">",
                    "value": 55,
                    "params": {"period": 14},
                    "action": "BUY",
                }
            ],
            condition_groups=[
                {
                    "id": "group_a",
                    "label": "Group A",
                    "conditions": [
                        {
                            "indicator": "rsi",
                            "operator": ">",
                            "value": 55,
                            "params": {"period": 14},
                            "action": "BUY",
                        }
                    ],
                }
            ],
            action="BUY",
            stop_loss_pct=0.03,
            take_profit_pct=0.07,
            timeframe="1D",
            symbols=["SPY"],
            commission_pct=0.003,
            slippage_pct=0.0015,
        )
        session.add(template)
        await session.flush()

        instance = StrategyInstance(
            template_id=template.id,
            user_id=user_id,
            mode=TradingModeEnum.PAPER,
            is_active=True,
            position_size_pct=0.15,
        )
        session.add(instance)
        await session.commit()

        app, mock_get_session = _build_strategies_app(session_factory, user_id)
        with patch("api.routes.strategies.get_session", mock_get_session):
            with patch("api.routes.strategies.market_data.get_bars", AsyncMock(return_value=_fake_market_bars())):
                client = TestClient(app)
                response = client.post(
                    "/api/strategies/backtest",
                    json={"strategy_id": instance.id, "lookback_days": 90, "initial_capital": 100000},
                )

        assert response.status_code == 200
        payload = response.json()
        assert payload["commission_pct"] == pytest.approx(0.003)
        assert payload["slippage_pct"] == pytest.approx(0.0015)
        assert "metrics" in payload
        assert "equity_curve" in payload

    @pytest.mark.anyio
    async def test_backtest_respects_sell_action(self, session, session_factory):
        user_id = await _seed_user(session)
        await session.commit()
        app, mock_get_session = _build_strategies_app(session_factory, user_id)

        with patch("api.routes.strategies.get_session", mock_get_session):
            with patch("api.routes.strategies.market_data.get_bars", AsyncMock(return_value=_fake_market_bars())):
                client = TestClient(app)
                response = client.post(
                    "/api/strategies/backtest",
                    json={
                        "conditions": [
                            {
                                "indicator": "rsi",
                                "operator": "<",
                                "value": 101,
                                "params": {"period": 14},
                                "action": "SELL",
                            }
                        ],
                        "lookback_days": 90,
                        "initial_capital": 100000,
                    },
                )

        assert response.status_code == 200
        payload = response.json()
        assert payload["trades"]
        assert {trade["direction"] for trade in payload["trades"]} == {"SHORT"}

    @pytest.mark.anyio
    async def test_backtest_caches_indicators_by_params(self, session, session_factory):
        from services.indicator_engine import IndicatorEngine

        user_id = await _seed_user(session)
        await session.commit()
        app, mock_get_session = _build_strategies_app(session_factory, user_id)

        with patch("api.routes.strategies.get_session", mock_get_session):
            with patch("api.routes.strategies.market_data.get_bars", AsyncMock(return_value=_fake_market_bars())):
                with patch("services.indicator_engine.IndicatorEngine.compute", wraps=IndicatorEngine.compute) as mock_compute:
                    client = TestClient(app)
                    response = client.post(
                        "/api/strategies/backtest",
                        json={
                            "conditions": [
                                {
                                    "indicator": "rsi",
                                    "operator": ">",
                                    "value": 55,
                                    "params": {"period": 7},
                                    "action": "BUY",
                                },
                                {
                                    "indicator": "rsi",
                                    "operator": "<",
                                    "value": 80,
                                    "params": {"period": 14},
                                    "action": "BUY",
                                },
                            ],
                            "lookback_days": 90,
                            "initial_capital": 100000,
                        },
                    )

        assert response.status_code == 200
        requested_periods = sorted(
            call.args[2].get("period")
            for call in mock_compute.call_args_list
            if call.args[0] == "rsi"
        )
        assert requested_periods == [7, 14]

    @pytest.mark.anyio
    async def test_backtest_supports_compare_to_price(self, session, session_factory):
        import pandas as pd

        user_id = await _seed_user(session)
        await session.commit()
        app, mock_get_session = _build_strategies_app(session_factory, user_id)

        def fake_compute(indicator_name, df, params):
            return pd.Series([50.0] * len(df))

        with patch("api.routes.strategies.get_session", mock_get_session):
            with patch("api.routes.strategies.market_data.get_bars", AsyncMock(return_value=_fake_market_bars())):
                with patch("services.indicator_engine.IndicatorEngine.compute", side_effect=fake_compute):
                    client = TestClient(app)
                    response = client.post(
                        "/api/strategies/backtest",
                        json={
                            "conditions": [
                                {
                                    "indicator": "rsi",
                                    "operator": "<",
                                    "value": 0,
                                    "compare_to": "PRICE",
                                    "params": {"period": 14},
                                    "action": "BUY",
                                }
                            ],
                            "lookback_days": 40,
                            "initial_capital": 100000,
                        },
                    )

        assert response.status_code == 200
        assert response.json()["trades"]


class TestRealIndicatorCompute:
    @pytest.mark.anyio
    async def test_compute_indicator_uses_real_market_bars(self, session, session_factory):
        user_id = await _seed_user(session)
        await session.commit()
        app, mock_get_session = _build_strategies_app(session_factory, user_id)

        with patch("api.routes.strategies.get_session", mock_get_session):
            with patch("api.routes.strategies.market_data.get_bars", AsyncMock(return_value=_fake_market_bars(260))):
                client = TestClient(app)
                response = client.post(
                    "/api/strategies/compute-indicator",
                    json={
                        "indicator": "rsi",
                        "params": {"period": 14},
                        "symbol": "QQQ",
                        "timeframe": "1D",
                        "bars": 120,
                    },
                )

        assert response.status_code == 200
        payload = response.json()
        assert payload["symbol"] == "QQQ"
        assert payload["timeframe"] == "1D"
        assert "values" in payload
        assert "synthetic_data" not in payload

    @pytest.mark.anyio
    async def test_backtest_supports_composite_indicator_fields(self, session, session_factory):
        import pandas as pd

        user_id = await _seed_user(session)
        await session.commit()
        app, mock_get_session = _build_strategies_app(session_factory, user_id)

        def fake_compute(indicator_name, df, params):
            if indicator_name == "macd":
                return {
                    "macd": pd.Series([-1.0] * len(df)),
                    "signal": pd.Series([-0.5] * len(df)),
                    "histogram": pd.Series([1.0] * len(df)),
                }
            raise AssertionError(f"Unexpected indicator: {indicator_name}")

        with patch("api.routes.strategies.get_session", mock_get_session):
            with patch("api.routes.strategies.market_data.get_bars", AsyncMock(return_value=_fake_market_bars())):
                with patch("services.indicator_engine.IndicatorEngine.compute", side_effect=fake_compute):
                    client = TestClient(app)
                    response = client.post(
                        "/api/strategies/backtest",
                        json={
                            "conditions": [
                                {
                                    "indicator": "macd",
                                    "field": "histogram",
                                    "operator": ">",
                                    "value": 0,
                                    "params": {},
                                    "action": "BUY",
                                }
                            ],
                            "lookback_days": 40,
                            "initial_capital": 100000,
                        },
                    )

        assert response.status_code == 200
        assert response.json()["trades"]

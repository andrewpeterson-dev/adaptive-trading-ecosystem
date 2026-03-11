"""Tests for AI strategy generation and bot deployment routes."""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from config.settings import get_settings
from db.cerberus_models import CerberusBot, CerberusBotVersion
from db.database import Base
from db.models import StrategyInstance, StrategyTemplate, TradingModeEnum, User

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


async def _seed_user(session: AsyncSession) -> int:
    user = User(email="ai-routes@example.com", password_hash="hash", display_name="AI Routes")
    session.add(user)
    await session.flush()
    return user.id


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

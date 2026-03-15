from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from db.cerberus_models import MarketEvent
from db.database import Base, get_db
from db.models import Strategy, StrategySnapshot, TradeEvent, TradingModeEnum, User

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


def _db_override(session_factory):
    async def _mock_get_db():
        async with session_factory() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise

    return _mock_get_db


async def _seed_user(session: AsyncSession, email: str) -> User:
    user = User(
        email=email,
        password_hash="hash",
        display_name=email.split("@", 1)[0],
        email_verified=True,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


def _build_models_app() -> FastAPI:
    from api.routes.models import router

    app = FastAPI()

    @app.middleware("http")
    async def inject_mode(request: Request, call_next):
        request.state.trading_mode = TradingModeEnum.PAPER
        return await call_next(request)

    app.include_router(router, prefix="/api/models")
    return app


def _build_quant_app(user_id: int, session_factory) -> FastAPI:
    from api.routes.quant import router

    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.state.user_id = user_id
        return await call_next(request)

    app.dependency_overrides[get_db] = _db_override(session_factory)
    app.include_router(router, prefix="/api/quant")
    return app


def _build_reasoning_app(user_id: int) -> FastAPI:
    from api.routes.reasoning import router

    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.state.user_id = user_id
        return await call_next(request)

    app.include_router(router, prefix="/api/reasoning")
    return app


class TestModelRoutesHonesty:
    @pytest.mark.anyio
    async def test_models_routes_do_not_fabricate_data(self, session_factory):
        app = _build_models_app()
        mock_get_session = _session_override(session_factory)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("api.routes.models.get_session", mock_get_session)
            client = TestClient(app)

            allocation = client.get("/api/models/allocation")
            regime = client.get("/api/models/regime")
            ensemble = client.get("/api/models/ensemble-status")
            retrain = client.post("/api/models/retrain?model_name=test-model")

        assert allocation.status_code == 200
        assert allocation.json()["allocations"] == []
        assert allocation.json()["status"] == "no_data"

        assert regime.status_code == 200
        assert regime.json()["regime"] is None
        assert regime.json()["status"] == "no_data"

        assert ensemble.status_code == 200
        assert ensemble.json()["weights"] == {}
        assert ensemble.json()["ensemble_active"] is False
        assert ensemble.json()["retraining_supported"] is False
        assert ensemble.json()["status"] == "no_data"

        assert retrain.status_code == 501
        assert "not implemented" in retrain.json()["detail"]


class TestQuantReasoningLogs:
    @pytest.mark.anyio
    async def test_reasoning_logs_return_real_trade_event_entries(self, session, session_factory):
        user = await _seed_user(session, "quant-user@example.com")
        strategy = Strategy(
            user_id=user.id,
            name="Logged Strategy",
            description="strategy with real logs",
            conditions=[{"indicator": "rsi", "operator": ">", "value": 55}],
            action="BUY",
            timeframe="1D",
            symbols=["SPY"],
        )
        session.add(strategy)
        await session.flush()

        session.add(
            TradeEvent(
                strategy_id=strategy.id,
                symbol="SPY",
                direction="long",
                confidence=82.0,
                approved=True,
                regime="low_vol_bull",
                reasoning_text="Momentum and regime aligned.",
                model_name="ensemble",
                entry_time=datetime.utcnow(),
            )
        )
        await session.commit()

        app = _build_quant_app(user.id, session_factory)
        client = TestClient(app)
        response = client.get(f"/api/quant/strategy/{strategy.id}/reasoning-logs")

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["logs"][0]["symbol"] == "SPY"
        assert payload["logs"][0]["reasoning"] == "Momentum and regime aligned."
        assert payload["logs"][0]["model"] == "ensemble"
        assert payload["logs"][0]["approved"] is True

    @pytest.mark.anyio
    async def test_quant_intelligence_uses_real_trade_metrics_only(self, session, session_factory):
        user = await _seed_user(session, "quant-metrics@example.com")
        strategy = Strategy(
            user_id=user.id,
            name="Metrics Strategy",
            description="strategy with realized trades",
            conditions=[{"indicator": "ema", "operator": ">", "value": 21}],
            action="BUY",
            timeframe="1D",
            symbols=["QQQ"],
        )
        session.add(strategy)
        await session.flush()

        session.add_all(
            [
                StrategySnapshot(
                    strategy_id=strategy.id,
                    timestamp=datetime(2026, 1, 2),
                    equity=100_000,
                ),
                StrategySnapshot(
                    strategy_id=strategy.id,
                    timestamp=datetime(2026, 1, 3),
                    equity=110_000,
                ),
                StrategySnapshot(
                    strategy_id=strategy.id,
                    timestamp=datetime(2026, 1, 4),
                    equity=105_000,
                ),
                TradeEvent(
                    strategy_id=strategy.id,
                    symbol="QQQ",
                    direction="long",
                    confidence=80.0,
                    approved=True,
                    pnl_pct=10.0,
                    entry_time=datetime(2026, 1, 2),
                ),
                TradeEvent(
                    strategy_id=strategy.id,
                    symbol="QQQ",
                    direction="long",
                    confidence=60.0,
                    approved=True,
                    pnl_pct=-5.0,
                    entry_time=datetime(2026, 1, 3),
                ),
            ]
        )
        await session.commit()

        app = _build_quant_app(user.id, session_factory)
        client = TestClient(app)

        intelligence = client.get(f"/api/quant/strategy/{strategy.id}")
        feature_importance = client.get(f"/api/quant/strategy/{strategy.id}/feature-importance")

        assert intelligence.status_code == 200
        perf = intelligence.json()["performance"]
        assert perf["win_rate"] == 0.5
        assert perf["profit_factor"] == 2.0
        assert perf["num_trades"] == 2
        assert perf["confidence"] == 70.0
        assert perf["sortino"] is None

        assert feature_importance.status_code == 200
        assert feature_importance.json()["features"] == []
        assert feature_importance.json()["status"] == "not_available"


class TestReasoningEventContracts:
    @pytest.mark.anyio
    async def test_market_events_filter_is_case_insensitive_and_returns_raw_data(self, session, session_factory):
        user = await _seed_user(session, "events-user@example.com")
        session.add(
            MarketEvent(
                id="evt-1",
                event_type="news",
                impact="LOW",
                symbols=["SPY"],
                sectors=[],
                headline="Fed commentary hits risk assets",
                raw_data={"url": "https://example.com/article", "source": "Reuters"},
                source="finnhub",
                source_id="evt-source-1",
                user_id=user.id,
                detected_at=datetime.utcnow(),
            )
        )
        await session.commit()

        app = _build_reasoning_app(user.id)
        mock_get_session = _session_override(session_factory)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("api.routes.reasoning.get_session", mock_get_session)
            client = TestClient(app)
            response = client.get("/api/reasoning/events?event_type=NEWS")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["event_type"] == "news"
        assert payload[0]["impact"] == "LOW"
        assert payload[0]["raw_data"]["url"] == "https://example.com/article"

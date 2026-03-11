from __future__ import annotations

from contextlib import asynccontextmanager
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import uuid

import pandas as pd
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from db.cerberus_models import CerberusBacktest, CerberusBot, CerberusBotVersion
from db.database import Base
from db.models import User
from services.ai_core.tools.market_tools import _get_earnings_calendar, _get_options_chain
from services.ai_core.tools.research_tools import _get_market_news, _run_research_session
from services.ai_core.tools.risk_tools import _calculate_var
from services.ai_core.tools.trading_tools import _backtest_strategy, _create_bot, _modify_bot
from services.workers.job_runners import execute_backtest_job

TEST_DB_URL = "sqlite+aiosqlite:///"


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
    user = User(email="tool-handlers@example.com", password_hash="hash", display_name="Tool Handlers")
    session.add(user)
    await session.flush()
    return user.id


def _patch_get_session(session_factory):
    @asynccontextmanager
    async def _mock_get_session():
        async with session_factory() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise

    return patch("db.database.get_session", _mock_get_session)


@pytest.mark.asyncio
async def test_get_options_chain_uses_real_chain_service():
    with patch(
        "services.ai_core.tools.market_tools.fetch_options_chain",
        AsyncMock(
            return_value={
                "symbol": "AAPL",
                "expirations": ["2026-03-20"],
                "selected_expiration": "2026-03-20",
                "strikes": [180.0, 185.0],
                "contracts": [
                    {"symbol": "AAPL260320C00180000", "type": "call", "strike": 180.0},
                    {"symbol": "AAPL260320P00180000", "type": "put", "strike": 180.0},
                ],
            }
        ),
    ):
        payload = await _get_options_chain(user_id=1, symbol="aapl", expiration="2026-03-20")

    assert payload["symbol"] == "AAPL"
    assert payload["selected_expiration"] == "2026-03-20"
    assert len(payload["calls"]) == 1
    assert len(payload["puts"]) == 1
    assert payload["contract_count"] == 2


@pytest.mark.asyncio
async def test_get_earnings_calendar_returns_real_event_shape():
    with patch(
        "services.ai_core.tools.market_tools._fetch_finnhub_earnings_calendar",
        AsyncMock(
            return_value=[
                {
                    "symbol": "AAPL",
                    "date": "2026-03-18",
                    "event_type": "earnings",
                    "status": "upcoming",
                    "provider": "finnhub",
                }
            ]
        ),
    ):
        payload = await _get_earnings_calendar(user_id=1, symbol="AAPL", days_ahead=7)

    assert payload["provider"] == "finnhub"
    assert payload["count"] == 1
    assert payload["events"][0]["symbol"] == "AAPL"
    assert payload["events"][0]["event_type"] == "earnings"


@pytest.mark.asyncio
async def test_get_market_news_builds_article_sources():
    articles = [
        {
            "title": "Apple supplier ramps production",
            "url": "https://example.com/apple",
            "source": "Example",
            "published_at": "2026-03-10T12:00:00+00:00",
            "summary": "Production and demand remain strong.",
            "symbols": ["AAPL"],
        }
    ]

    with patch("services.ai_core.tools.research_tools._extract_symbols", return_value=["AAPL"]):
        with patch(
            "services.ai_core.tools.research_tools._news_ingestion.fetch_news",
            return_value=articles,
        ):
            payload = await _get_market_news(user_id=1, query="AAPL supply chain", max_results=5)

    assert payload["symbols"] == ["AAPL"]
    assert payload["count"] == 1
    assert payload["articles"][0]["title"] == "Apple supplier ramps production"
    assert payload["sources"][0]["url"] == "https://example.com/apple"


@pytest.mark.asyncio
async def test_run_research_session_composes_real_inputs():
    with patch("services.ai_core.tools.research_tools._extract_symbols", return_value=["AAPL"]):
        with patch(
            "services.ai_core.tools.research_tools._search_documents",
            AsyncMock(
                return_value={
                    "chunks": [
                        {
                            "document_id": "doc-1",
                            "heading": "AAPL thesis",
                            "content": "Demand remains durable.",
                        }
                    ]
                }
            ),
        ):
            with patch(
                "services.ai_core.tools.research_tools._get_market_news",
                AsyncMock(
                    return_value={
                        "articles": [{"title": "Apple launches new product", "summary": "Launch draws demand."}],
                        "sources": [{"title": "Apple launches new product", "url": "https://example.com/apple"}],
                    }
                ),
            ):
                with patch(
                    "services.ai_core.tools.research_tools._get_macro_events",
                    AsyncMock(return_value={"events": [{"event": "CPI", "date": "2026-03-12"}]}),
                ):
                    with patch(
                        "services.ai_core.tools.research_tools._load_symbol_market_context",
                        AsyncMock(
                            return_value={
                                "symbol": "AAPL",
                                "latest_close": 212.45,
                                "return_20d_pct": 4.2,
                            }
                        ),
                    ):
                        with patch(
                            "services.ai_core.tools.research_tools._get_earnings_context",
                            AsyncMock(return_value={"symbol": "AAPL", "next_earnings": {"date": "2026-04-30"}}),
                        ):
                            payload = await _run_research_session(
                                user_id=1,
                                topic="Research AAPL demand and upcoming catalysts",
                                symbols=None,
                                depth="standard",
                            )

    assert payload["symbols"] == ["AAPL"]
    assert payload["market_data"]["AAPL"]["latest_close"] == 212.45
    assert payload["news_results"][0]["title"] == "Apple launches new product"
    assert payload["macro_events"][0]["event"] == "CPI"
    assert "AAPL last traded at 212.45" in payload["synthesis"]


@pytest.mark.asyncio
async def test_calculate_var_uses_historical_returns():
    returns = pd.Series([0.01, -0.015, 0.004, -0.008, 0.012, -0.006, 0.009, -0.01] * 8, dtype=float)

    with patch(
        "services.ai_core.tools.risk_tools._load_portfolio_returns",
        AsyncMock(
            return_value=(
                returns,
                100_000.0,
                {"source": "portfolio_snapshots", "observations": len(returns), "symbols": ["AAPL", "MSFT"]},
            )
        ),
    ):
        payload = await _calculate_var(user_id=1, confidence=0.95, horizon_days=1, method="historical")

    assert payload["var"] > 0
    assert payload["var_pct"] > 0
    assert payload["data_source"] == "portfolio_snapshots"
    assert payload["method"] == "historical"
    assert "note" not in payload


class _DummySession:
    def __init__(self):
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def add(self, obj):
        self.added.append(obj)


@pytest.mark.asyncio
async def test_backtest_strategy_falls_back_to_inline_execution_when_queue_fails():
    session = _DummySession()

    def _raise_queue_error(*args, **kwargs):
        raise RuntimeError("broker down")

    fake_tasks_module = SimpleNamespace(
        run_backtest=SimpleNamespace(delay=_raise_queue_error)
    )

    with patch("db.database.get_session", return_value=session):
        with patch(
            "services.workers.job_runners.execute_backtest_job",
            AsyncMock(return_value={"metrics": {"total_return": 0.12}}),
        ):
            with patch.dict(sys.modules, {"services.workers.tasks": fake_tasks_module}):
                payload = await _backtest_strategy(
                    user_id=1,
                    strategy_name="momentum",
                    params={"conditions": [{"indicator": "rsi", "operator": ">", "value": 55}]},
                )

    assert payload["status"] == "completed"
    assert payload["execution_mode"] == "inline"
    assert payload["metrics"]["total_return"] == 0.12


@pytest.mark.asyncio
async def test_execute_backtest_job_uses_bot_version_config(session, session_factory):
    user_id = await _seed_user(session)
    bot = CerberusBot(id=str(uuid.uuid4()), user_id=user_id, name="Momentum Bot")
    version = CerberusBotVersion(
        id=str(uuid.uuid4()),
        bot_id=bot.id,
        version_number=1,
        config_json={
            "symbols": ["NVDA"],
            "timeframe": "1H",
            "conditions": [
                {
                    "indicator": "rsi",
                    "operator": ">",
                    "value": 55,
                    "params": {"period": 14},
                    "action": "BUY",
                }
            ],
            "condition_groups": [
                {
                    "conditions": [
                        {
                            "indicator": "rsi",
                            "operator": ">",
                            "value": 55,
                            "params": {"period": 14},
                            "action": "BUY",
                        }
                    ]
                }
            ],
            "commission_pct": 0.002,
            "slippage_pct": 0.001,
        },
    )
    backtest = CerberusBacktest(
        id=str(uuid.uuid4()),
        user_id=user_id,
        bot_id=bot.id,
        bot_version_id=version.id,
        strategy_name="Momentum Bot",
        params_json={"lookback_days": 120},
        status="pending",
    )
    session.add(bot)
    session.add(version)
    session.add(backtest)
    await session.commit()

    captured = {}

    async def fake_run_backtest(req, request=None):
        captured["symbol"] = req.symbol
        captured["timeframe"] = req.timeframe
        captured["conditions"] = req.conditions
        captured["condition_groups"] = req.condition_groups
        return {
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "commission_pct": req.commission_pct,
            "slippage_pct": req.slippage_pct,
            "metrics": {"total_return": 0.21},
            "equity_curve": [{"date": "2026-03-11", "value": 121000}],
            "benchmark_equity_curve": [{"date": "2026-03-11", "value": 110000}],
            "trades": [{"symbol": req.symbol, "pnl": 21000}],
        }

    with _patch_get_session(session_factory):
        with patch("api.routes.strategies.run_backtest", AsyncMock(side_effect=fake_run_backtest)):
            payload = await execute_backtest_job(backtest.id, user_id)

    assert payload["metrics"]["total_return"] == 0.21
    assert captured["symbol"] == "NVDA"
    assert captured["timeframe"] == "1H"
    assert captured["condition_groups"]

    async with session_factory() as verify_session:
        stored = await verify_session.get(CerberusBacktest, backtest.id)
        assert stored.status == "completed"
        assert stored.metrics_json["total_return"] == 0.21
        assert stored.leakage_checks_json["benchmark_equity_curve"]


@pytest.mark.asyncio
async def test_create_bot_tool_requires_executable_config(session, session_factory):
    user_id = await _seed_user(session)
    await session.commit()

    with _patch_get_session(session_factory):
        payload = await _create_bot(
            user_id=user_id,
            name="AI Tool Bot",
            strategy_name="Momentum",
            config=None,
        )

    assert payload["error"] == "Bot config is required"

    result = await session.execute(select(CerberusBot))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_modify_bot_tool_merges_partial_updates_into_current_version(session, session_factory):
    user_id = await _seed_user(session)
    bot = CerberusBot(id=str(uuid.uuid4()), user_id=user_id, name="Merge Bot")
    version = CerberusBotVersion(
        id=str(uuid.uuid4()),
        bot_id=bot.id,
        version_number=1,
        config_json={
            "name": "Merge Bot",
            "action": "BUY",
            "timeframe": "1D",
            "symbols": ["SPY"],
            "conditions": [
                {
                    "indicator": "rsi",
                    "operator": ">",
                    "value": 55,
                    "params": {"period": 14},
                    "action": "BUY",
                }
            ],
            "condition_groups": [
                {
                    "conditions": [
                        {
                            "indicator": "rsi",
                            "operator": ">",
                            "value": 55,
                            "params": {"period": 14},
                            "action": "BUY",
                        }
                    ]
                }
            ],
        },
    )
    bot.current_version_id = version.id
    session.add(bot)
    session.add(version)
    await session.commit()

    with _patch_get_session(session_factory):
        payload = await _modify_bot(
            user_id=user_id,
            bot_id=bot.id,
            config={"timeframe": "4H"},
            diff_summary="Tighten cadence",
        )

    assert payload["version_number"] == 2

    async with session_factory() as verify_session:
        stored_bot = await verify_session.get(CerberusBot, bot.id)
        stored_version = await verify_session.get(CerberusBotVersion, payload["version_id"])
        assert stored_bot.current_version_id == payload["version_id"]
        assert stored_version.config_json["timeframe"] == "4H"
        assert stored_version.config_json["symbols"] == ["SPY"]
        assert stored_version.config_json["conditions"][0]["indicator"] == "rsi"

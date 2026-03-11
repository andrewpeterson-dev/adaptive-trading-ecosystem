"""Async job runners shared by Celery tasks and inline fallbacks."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace


async def execute_backtest_job(backtest_id: str, user_id: int) -> dict:
    """Execute a stored Cerberus backtest using the real strategy backtester."""
    from api.routes.strategies import BacktestRequest, run_backtest as run_strategy_backtest
    from config.settings import get_settings
    from db.database import get_session
    from db.cerberus_models import CerberusBacktest, CerberusBotVersion
    from services.strategy_learning_engine import normalize_bot_config
    from sqlalchemy import select

    async with get_session() as session:
        result = await session.execute(
            select(CerberusBacktest).where(
                CerberusBacktest.id == backtest_id,
                CerberusBacktest.user_id == user_id,
            )
        )
        bt = result.scalar_one_or_none()
        if not bt:
            raise ValueError(f"Backtest {backtest_id} not found")

        bt.status = "running"
        await session.flush()

        params = dict(bt.params_json or {})
        version = None
        if bt.bot_version_id:
            version = await session.get(CerberusBotVersion, bt.bot_version_id)
        elif bt.bot_id:
            version_result = await session.execute(
                select(CerberusBotVersion)
                .where(CerberusBotVersion.bot_id == bt.bot_id)
                .order_by(CerberusBotVersion.version_number.desc())
                .limit(1)
            )
            version = version_result.scalar_one_or_none()

        config = normalize_bot_config(version.config_json if version else {})
        symbol = params.get("symbol") or (config.get("symbols") or ["SPY"])[0]
        request_payload = {
            "strategy_id": params.get("strategy_id"),
            "conditions": params.get("conditions") or config.get("conditions") or None,
            "condition_groups": params.get("condition_groups") or config.get("condition_groups") or None,
            "symbol": symbol,
            "timeframe": params.get("timeframe") or config.get("timeframe"),
            "lookback_days": int(params.get("lookback_days") or 252),
            "initial_capital": float(params.get("initial_capital") or get_settings().initial_capital),
            "commission_pct": float(
                params.get("commission_pct")
                if params.get("commission_pct") is not None
                else config.get("commission_pct") or 0.001
            ),
            "slippage_pct": float(
                params.get("slippage_pct")
                if params.get("slippage_pct") is not None
                else config.get("slippage_pct") or 0.0005
            ),
        }
        request = SimpleNamespace(state=SimpleNamespace(user_id=user_id))

        if not request_payload["strategy_id"] and not (
            request_payload["conditions"] or request_payload["condition_groups"]
        ):
            raise ValueError(
                f"Backtest {backtest_id} is missing strategy_id or normalized bot conditions"
            )

        try:
            result_payload = await run_strategy_backtest(BacktestRequest(**request_payload), request=request)
            bt.metrics_json = result_payload.get("metrics", {})
            bt.equity_curve_json = result_payload.get("equity_curve", [])
            bt.trades_json = result_payload.get("trades", [])
            bt.leakage_checks_json = {
                "symbol": result_payload.get("symbol"),
                "timeframe": result_payload.get("timeframe"),
                "commission_pct": result_payload.get("commission_pct"),
                "slippage_pct": result_payload.get("slippage_pct"),
                "benchmark_equity_curve": result_payload.get("benchmark_equity_curve", []),
            }
            bt.status = "completed"
            bt.completed_at = datetime.utcnow()
            await session.commit()
            return result_payload
        except Exception as exc:
            bt.status = "error"
            bt.completed_at = datetime.utcnow()
            bt.metrics_json = {"error": str(exc)}
            await session.commit()
            raise


async def execute_research_job(query: str, user_id: int, document_ids: list[str] | None = None) -> dict:
    """Execute a real research session and return the assembled output."""
    from services.ai_core.tools.research_tools import _run_research_session

    depth = "deep" if document_ids else "standard"
    result = await _run_research_session(
        user_id=user_id,
        topic=query,
        symbols=None,
        depth=depth,
    )
    if document_ids:
        result["document_ids"] = document_ids
    return result

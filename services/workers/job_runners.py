"""Async job runners shared by Celery tasks and inline fallbacks."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


def _run_vectorbt_backtest(
    symbol: str,
    timeframe: Optional[str],
    lookback_days: int,
    conditions: Optional[List[Dict[str, Any]]],
    condition_groups: Optional[List[Dict[str, Any]]],
    initial_capital: float,
    commission_pct: float,
    slippage_pct: float,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
    action: str = "BUY",
) -> Dict[str, Any]:
    """Run a VectorBT backtest synchronously (called from async via executor)."""
    from services.backtesting.vectorbt_engine import run_vectorbt_backtest

    return run_vectorbt_backtest(
        symbol=symbol,
        timeframe=timeframe or "1D",
        lookback_days=lookback_days,
        conditions=conditions,
        condition_groups=condition_groups,
        initial_capital=initial_capital,
        commission_pct=commission_pct,
        slippage_pct=slippage_pct,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        action=action,
    )


def _run_parameter_sweep(
    conditions: Optional[List[Dict[str, Any]]],
    condition_groups: Optional[List[Dict[str, Any]]],
    parameter_ranges: Dict[str, Dict[str, Any]],
    symbol: str,
    timeframe: str,
    lookback_days: int,
    initial_capital: float,
    commission_pct: float,
    slippage_pct: float,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
    action: str = "BUY",
    metric: str = "sharpe_ratio",
) -> Dict[str, Any]:
    """Run a parameter sweep synchronously (called from async via executor)."""
    from services.backtesting.parameter_sweep import run_parameter_sweep

    return run_parameter_sweep(
        conditions=conditions,
        condition_groups=condition_groups,
        parameter_ranges=parameter_ranges,
        symbol=symbol,
        timeframe=timeframe,
        lookback_days=lookback_days,
        initial_capital=initial_capital,
        commission_pct=commission_pct,
        slippage_pct=slippage_pct,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        action=action,
        metric=metric,
    )


async def execute_backtest_job(backtest_id: str, user_id: int) -> dict:
    """Execute a stored Cerberus backtest using the VectorBT engine."""
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
        timeframe = params.get("timeframe") or config.get("timeframe") or "1D"
        lookback_days = int(params.get("lookback_days") or 252)
        initial_capital = float(params.get("initial_capital") or get_settings().initial_capital)
        commission_pct = float(
            params.get("commission_pct")
            if params.get("commission_pct") is not None
            else config.get("commission_pct") or 0.001
        )
        slippage_pct = float(
            params.get("slippage_pct")
            if params.get("slippage_pct") is not None
            else config.get("slippage_pct") or 0.0005
        )
        stop_loss_pct = config.get("stop_loss_pct")
        take_profit_pct = config.get("take_profit_pct")
        action = config.get("action", "BUY")

        conditions = params.get("conditions") or config.get("conditions") or None
        condition_groups = params.get("condition_groups") or config.get("condition_groups") or None

        # Check for parameter sweep mode
        parameter_ranges = params.get("parameter_ranges")

        if not conditions and not condition_groups:
            # Fall back to loading from strategy via the API route
            strategy_id = params.get("strategy_id")
            if strategy_id:
                from api.routes.strategies import BacktestRequest, run_backtest as run_strategy_backtest
                from types import SimpleNamespace

                request_payload = {
                    "strategy_id": strategy_id,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "lookback_days": lookback_days,
                    "initial_capital": initial_capital,
                    "commission_pct": commission_pct,
                    "slippage_pct": slippage_pct,
                    "stop_loss_pct": stop_loss_pct,
                    "take_profit_pct": take_profit_pct,
                    "action": action,
                }
                request = SimpleNamespace(state=SimpleNamespace(user_id=user_id))
                try:
                    result_payload = await run_strategy_backtest(
                        BacktestRequest(**request_payload), request=request
                    )
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

            raise ValueError(
                f"Backtest {backtest_id} is missing strategy_id or normalized bot conditions"
            )

        try:
            # Run VectorBT in a thread executor to avoid blocking the event loop
            loop = asyncio.get_running_loop()

            if parameter_ranges:
                # Sweep mode
                result_payload = await loop.run_in_executor(
                    None,
                    lambda: _run_parameter_sweep(
                        conditions=conditions,
                        condition_groups=condition_groups,
                        parameter_ranges=parameter_ranges,
                        symbol=symbol,
                        timeframe=timeframe,
                        lookback_days=lookback_days,
                        initial_capital=initial_capital,
                        commission_pct=commission_pct,
                        slippage_pct=slippage_pct,
                        stop_loss_pct=stop_loss_pct,
                        take_profit_pct=take_profit_pct,
                        action=action,
                    ),
                )
            else:
                # Standard backtest mode
                result_payload = await loop.run_in_executor(
                    None,
                    lambda: _run_vectorbt_backtest(
                        symbol=symbol,
                        timeframe=timeframe,
                        lookback_days=lookback_days,
                        conditions=conditions,
                        condition_groups=condition_groups,
                        initial_capital=initial_capital,
                        commission_pct=commission_pct,
                        slippage_pct=slippage_pct,
                        stop_loss_pct=stop_loss_pct,
                        take_profit_pct=take_profit_pct,
                        action=action,
                    ),
                )

            bt.metrics_json = result_payload.get("metrics", {})
            bt.equity_curve_json = result_payload.get("equity_curve", [])
            bt.trades_json = result_payload.get("trades", [])
            bt.leakage_checks_json = {
                "symbol": result_payload.get("symbol"),
                "timeframe": result_payload.get("timeframe"),
                "commission_pct": result_payload.get("commission_pct"),
                "slippage_pct": result_payload.get("slippage_pct"),
                "benchmark_equity_curve": result_payload.get("benchmark_equity_curve", []),
                "drawdown_curve": result_payload.get("drawdown_curve", []),
            }
            bt.status = "completed"
            bt.completed_at = datetime.utcnow()
            await session.commit()

            logger.info(
                "backtest_completed",
                backtest_id=backtest_id,
                engine="vectorbt",
                num_trades=result_payload.get("metrics", {}).get("num_trades", 0),
                sharpe=result_payload.get("metrics", {}).get("sharpe_ratio", 0),
            )
            return result_payload

        except Exception as exc:
            bt.status = "error"
            bt.completed_at = datetime.utcnow()
            bt.metrics_json = {"error": str(exc)}
            await session.commit()
            raise


def _run_walk_forward(
    conditions: Optional[List[Dict[str, Any]]],
    condition_groups: Optional[List[Dict[str, Any]]],
    exit_conditions: Optional[List[Dict[str, Any]]],
    symbol: str,
    timeframe: str,
    lookback_days: int,
    n_segments: int,
    commission_pct: float,
    slippage_pct: float,
    initial_capital: float,
) -> Dict[str, Any]:
    """Run walk-forward validation synchronously (called from async via executor)."""
    from services.backtesting.walk_forward import run_walk_forward

    return run_walk_forward(
        conditions=conditions,
        condition_groups=condition_groups,
        exit_conditions=exit_conditions,
        symbol=symbol,
        timeframe=timeframe,
        lookback_days=lookback_days,
        n_segments=n_segments,
        commission_pct=commission_pct,
        slippage_pct=slippage_pct,
        initial_capital=initial_capital,
    )


def _run_ablation_study(
    conditions: Optional[List[Dict[str, Any]]],
    condition_groups: Optional[List[Dict[str, Any]]],
    exit_conditions: Optional[List[Dict[str, Any]]],
    symbol: str,
    timeframe: str,
    lookback_days: int,
    n_random_trials: int,
    commission_pct: float,
    slippage_pct: float,
    initial_capital: float,
) -> Dict[str, Any]:
    """Run ablation study synchronously (called from async via executor)."""
    from services.backtesting.ablation_study import run_ablation_study

    return run_ablation_study(
        conditions=conditions,
        condition_groups=condition_groups,
        exit_conditions=exit_conditions,
        symbol=symbol,
        timeframe=timeframe,
        lookback_days=lookback_days,
        n_random_trials=n_random_trials,
        commission_pct=commission_pct,
        slippage_pct=slippage_pct,
        initial_capital=initial_capital,
    )


async def execute_walk_forward_job(
    conditions: Optional[List[Dict[str, Any]]] = None,
    condition_groups: Optional[List[Dict[str, Any]]] = None,
    exit_conditions: Optional[List[Dict[str, Any]]] = None,
    symbol: str = "SPY",
    timeframe: str = "1D",
    lookback_days: int = 756,
    n_segments: int = 6,
    commission_pct: float = 0.001,
    slippage_pct: float = 0.0005,
    initial_capital: float = 100_000.0,
) -> dict:
    """Execute a walk-forward validation job in a thread executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: _run_walk_forward(
            conditions=conditions,
            condition_groups=condition_groups,
            exit_conditions=exit_conditions,
            symbol=symbol,
            timeframe=timeframe,
            lookback_days=lookback_days,
            n_segments=n_segments,
            commission_pct=commission_pct,
            slippage_pct=slippage_pct,
            initial_capital=initial_capital,
        ),
    )


async def execute_ablation_study_job(
    conditions: Optional[List[Dict[str, Any]]] = None,
    condition_groups: Optional[List[Dict[str, Any]]] = None,
    exit_conditions: Optional[List[Dict[str, Any]]] = None,
    symbol: str = "SPY",
    timeframe: str = "1D",
    lookback_days: int = 252,
    n_random_trials: int = 1000,
    commission_pct: float = 0.001,
    slippage_pct: float = 0.0005,
    initial_capital: float = 100_000.0,
) -> dict:
    """Execute an ablation study job in a thread executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: _run_ablation_study(
            conditions=conditions,
            condition_groups=condition_groups,
            exit_conditions=exit_conditions,
            symbol=symbol,
            timeframe=timeframe,
            lookback_days=lookback_days,
            n_random_trials=n_random_trials,
            commission_pct=commission_pct,
            slippage_pct=slippage_pct,
            initial_capital=initial_capital,
        ),
    )


async def execute_research_job(query: str, user_id: int, document_ids: Optional[List[str]] = None) -> dict:
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

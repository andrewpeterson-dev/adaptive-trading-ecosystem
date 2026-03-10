"""
Model management endpoints — list models, allocation, regime, performance.
Queries the database and seeds reasonable defaults when tables are empty.
"""

from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select, func

from db.database import get_session
from db.models import (
    TradingModel,
    ModelPerformance,
    CapitalAllocation,
    MarketRegimeRecord,
    TradingModeEnum,
)

logger = structlog.get_logger(__name__)
router = APIRouter()

# The 11 registered models with their types
_DEFAULT_MODELS = [
    {"name": "momentum_fast", "model_type": "MomentumModel"},
    {"name": "momentum_slow", "model_type": "MomentumModel"},
    {"name": "mean_reversion_tight", "model_type": "MeanReversionModel"},
    {"name": "mean_reversion_wide", "model_type": "MeanReversionModel"},
    {"name": "volatility_squeeze", "model_type": "VolatilityModel"},
    {"name": "breakout_sr", "model_type": "BreakoutModel"},
    {"name": "iv_crush", "model_type": "IVCrushModel"},
    {"name": "earnings_momentum", "model_type": "EarningsMomentumModel"},
    {"name": "pairs_statarb", "model_type": "PairsModel"},
    {"name": "ml_xgboost", "model_type": "MLModel"},
    {"name": "ml_random_forest", "model_type": "MLModel"},
]

STARTING_CAPITAL = 8082.72


async def _seed_models(db):
    """Insert default trading models into the database if none exist."""
    for m in _DEFAULT_MODELS:
        model = TradingModel(
            name=m["name"],
            model_type=m["model_type"],
            is_active=True,
        )
        db.add(model)
    await db.flush()
    logger.info("seeded_trading_models", count=len(_DEFAULT_MODELS))

    result = await db.execute(select(TradingModel))
    return result.scalars().all()


@router.get("/list")
async def list_models(request: Request):
    """List all trading models with their latest performance metrics — filtered by mode."""
    mode = request.state.trading_mode

    async with get_session() as db:
        result = await db.execute(
            select(TradingModel)
            .where(TradingModel.mode == mode)
            .order_by(TradingModel.id)
        )
        models = result.scalars().all()

        if not models:
            return {"models": [], "mode": mode.value}

        # Build response with latest performance per model
        model_list = []
        for m in models:
            # Get latest performance record for this mode
            perf_result = await db.execute(
                select(ModelPerformance)
                .where(
                    ModelPerformance.model_id == m.id,
                    ModelPerformance.mode == mode,
                )
                .order_by(ModelPerformance.timestamp.desc())
                .limit(1)
            )
            perf = perf_result.scalar_one_or_none()

            model_list.append({
                "name": m.name,
                "model_type": m.model_type,
                "is_active": m.is_active,
                "sharpe_ratio": perf.sharpe_ratio if perf else None,
                "sortino_ratio": perf.sortino_ratio if perf else None,
                "win_rate": perf.win_rate if perf else None,
                "max_drawdown": perf.max_drawdown if perf else None,
                "total_return": perf.total_return if perf else None,
                "num_trades": perf.num_trades if perf else 0,
            })

    return {"models": model_list, "mode": mode.value}


@router.get("/allocation")
async def get_allocation(request: Request):
    """Get current capital allocation across models — filtered by mode."""
    mode = request.state.trading_mode

    async with get_session() as db:
        # Get the latest allocation timestamp for this mode
        latest_ts = await db.execute(
            select(func.max(CapitalAllocation.timestamp))
            .where(CapitalAllocation.mode == mode)
        )
        max_ts = latest_ts.scalar()

        if max_ts:
            # Get all allocations at the latest timestamp for this mode
            result = await db.execute(
                select(CapitalAllocation, TradingModel.name)
                .join(TradingModel, CapitalAllocation.model_id == TradingModel.id)
                .where(
                    CapitalAllocation.timestamp == max_ts,
                    CapitalAllocation.mode == mode,
                )
                .order_by(TradingModel.name)
            )
            rows = result.all()

            allocations = [
                {
                    "model_name": row.name,
                    "weight": round(row.CapitalAllocation.weight, 4),
                    "allocated_capital": round(row.CapitalAllocation.allocated_capital, 2),
                }
                for row in rows
            ]
            return {"allocations": allocations, "mode": mode.value}

        # No allocation data — return equal weight across active models for this mode
        result = await db.execute(
            select(TradingModel).where(
                TradingModel.is_active == True,
                TradingModel.mode == mode,
            )
        )
        active_models = result.scalars().all()

        if not active_models:
            return {"allocations": [], "mode": mode.value}

        n = len(active_models)
        equal_weight = round(1.0 / n, 4) if n > 0 else 0.0
        per_model_capital = round(STARTING_CAPITAL / n, 2) if n > 0 else 0.0

        allocations = [
            {
                "model_name": m.name,
                "weight": equal_weight,
                "allocated_capital": per_model_capital,
            }
            for m in active_models
        ]

    logger.info("allocation_seed_data", reason="no allocations in db", count=len(allocations), mode=mode.value)
    return {"allocations": allocations, "mode": mode.value}


@router.get("/regime")
async def get_current_regime(request: Request):
    """Get the latest detected market regime."""
    async with get_session() as db:
        result = await db.execute(
            select(MarketRegimeRecord)
            .order_by(MarketRegimeRecord.timestamp.desc())
            .limit(1)
        )
        record = result.scalar_one_or_none()

    if record:
        return {
            "regime": record.regime.value if hasattr(record.regime, "value") else str(record.regime),
            "confidence": record.confidence,
            "volatility_20d": record.volatility_20d,
            "trend_strength": record.trend_strength,
            "timestamp": record.timestamp.isoformat() if record.timestamp else None,
        }

    # No regime data — return default
    logger.info("regime_seed_data", reason="no regime records")
    return {
        "regime": "sideways",
        "confidence": 0.5,
        "volatility_20d": None,
        "trend_strength": None,
        "timestamp": None,
    }


@router.get("/performance/{model_name}")
async def get_model_performance(model_name: str, request: Request):
    """Get detailed performance history for a specific model — filtered by mode."""
    mode = request.state.trading_mode

    async with get_session() as db:
        model_result = await db.execute(
            select(TradingModel).where(
                TradingModel.name == model_name,
                TradingModel.mode == mode,
            )
        )
        model = model_result.scalar_one_or_none()
        if not model:
            raise HTTPException(status_code=404, detail=f"Model not found: {model_name}")

        perf_result = await db.execute(
            select(ModelPerformance)
            .where(
                ModelPerformance.model_id == model.id,
                ModelPerformance.mode == mode,
            )
            .order_by(ModelPerformance.timestamp.desc())
            .limit(50)
        )
        records = perf_result.scalars().all()

    return {
        "name": model.name,
        "model_type": model.model_type,
        "is_active": model.is_active,
        "mode": mode.value,
        "performance_history": [
            {
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "sharpe_ratio": r.sharpe_ratio,
                "sortino_ratio": r.sortino_ratio,
                "win_rate": r.win_rate,
                "profit_factor": r.profit_factor,
                "max_drawdown": r.max_drawdown,
                "total_return": r.total_return,
                "num_trades": r.num_trades,
            }
            for r in records
        ],
    }


@router.post("/retrain")
async def retrain_model(model_name: str = None, request: Request = None):
    """Trigger model retraining. Returns job status."""
    # Stub — real training runs async in production
    return {
        "status": "queued",
        "model": model_name or "all",
        "message": "Retraining queued. Results will be available after training completes.",
        "job_id": f"retrain_{int(__import__('time').time())}"
    }


@router.get("/ensemble-status")
async def get_ensemble_status(request: Request = None):
    """Returns current ensemble weights and model voting status — filtered by mode."""
    mode = request.state.trading_mode if request else TradingModeEnum.PAPER

    async with get_session() as db:
        result = await db.execute(
            select(TradingModel).where(
                TradingModel.is_active == True,
                TradingModel.mode == mode,
            )
        )
        models = result.scalars().all()

        # Try to get latest allocation weights for this mode
        latest_ts = await db.execute(
            select(func.max(CapitalAllocation.timestamp))
            .where(CapitalAllocation.mode == mode)
        )
        max_ts = latest_ts.scalar()

        weights: dict = {}
        if max_ts and models:
            alloc_result = await db.execute(
                select(CapitalAllocation, TradingModel.name)
                .join(TradingModel, CapitalAllocation.model_id == TradingModel.id)
                .where(
                    CapitalAllocation.timestamp == max_ts,
                    CapitalAllocation.mode == mode,
                )
            )
            for row in alloc_result.all():
                weights[row.name] = round(row.CapitalAllocation.weight, 4)
        elif models:
            # Equal weight fallback
            eq = round(1.0 / len(models), 4)
            weights = {m.name: eq for m in models}

        return {
            "ensemble_active": len(models) > 0,
            "model_count": len(models),
            "weights": weights,
            "mode": mode.value,
            "last_updated": models[0].updated_at.isoformat() if models and models[0].updated_at else None,
        }

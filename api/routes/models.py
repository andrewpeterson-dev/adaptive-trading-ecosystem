"""
Model management endpoints — list models, allocation, regime, performance.
Returns only persisted analytics data; it does not synthesize portfolio state.
"""

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


@router.get("/list")
async def list_models(request: Request):
    """List all trading models with their latest performance metrics — filtered by mode."""
    mode = request.state.trading_mode

    async with get_session() as db:
        latest_perf_subquery = (
            select(
                ModelPerformance.model_id.label("model_id"),
                func.max(ModelPerformance.timestamp).label("latest_timestamp"),
            )
            .where(ModelPerformance.mode == mode)
            .group_by(ModelPerformance.model_id)
            .subquery()
        )

        result = await db.execute(
            select(TradingModel, ModelPerformance)
            .outerjoin(
                latest_perf_subquery,
                latest_perf_subquery.c.model_id == TradingModel.id,
            )
            .outerjoin(
                ModelPerformance,
                (ModelPerformance.model_id == TradingModel.id)
                & (ModelPerformance.mode == mode)
                & (ModelPerformance.timestamp == latest_perf_subquery.c.latest_timestamp),
            )
            .where(TradingModel.mode == mode)
            .order_by(TradingModel.id)
        )
        rows = result.all()

        if not rows:
            return {"models": [], "mode": mode.value}

        # Build response with latest performance per model
        model_list = []
        for m, perf in rows:
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
            return {
                "allocations": allocations,
                "mode": mode.value,
                "status": "ready",
                "last_updated": max_ts.isoformat() if max_ts else None,
            }

    return {
        "allocations": [],
        "mode": mode.value,
        "status": "no_data",
        "last_updated": None,
    }


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
            "status": "ready",
        }

    return {
        "regime": None,
        "confidence": None,
        "volatility_20d": None,
        "trend_strength": None,
        "timestamp": None,
        "status": "no_data",
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
    """Trigger model retraining when the backend supports it."""
    raise HTTPException(
        status_code=501,
        detail="Model retraining is not implemented in this environment",
    )


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

        return {
            "ensemble_active": bool(weights),
            "model_count": len(models),
            "weights": weights,
            "mode": mode.value,
            "last_updated": max_ts.isoformat() if max_ts else None,
            "status": "ready" if weights else "no_data",
            "retraining_supported": False,
        }

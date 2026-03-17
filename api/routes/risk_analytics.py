"""Risk analytics endpoints — category scores, drawdown status, risk limits."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from db.database import get_session
from db.models import UserRiskLimits, TradingModeEnum
from services.reasoning_engine.safety import (
    evaluate_drawdown_level,
    get_category_scores,
    update_category_scores,
    get_drawdown_thresholds,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


class UpdateRiskLimitsRequest(BaseModel):
    drawdown_reduce_pct: Optional[float] = None
    drawdown_halt_pct: Optional[float] = None
    drawdown_kill_pct: Optional[float] = None
    weekly_drawdown_kill_pct: Optional[float] = None
    sector_concentration_limit: Optional[float] = None
    category_block_threshold: Optional[float] = None
    daily_loss_limit: Optional[float] = None
    max_position_size_pct: Optional[float] = None
    max_open_positions: Optional[int] = None


@router.get("/category-scores")
async def get_category_scores_endpoint(request: Request):
    """Get category/strategy-type performance scores for the current user."""
    user_id = request.state.user_id
    scores = await get_category_scores(user_id)
    if not scores:
        try:
            await update_category_scores(user_id)
            scores = await get_category_scores(user_id)
        except Exception as e:
            logger.warning("category_scores_compute_error", user_id=user_id, error=str(e))
    return {
        "scores": scores,
        "count": len(scores),
        "blocked_count": sum(1 for s in scores if s.get("is_blocked")),
    }


@router.post("/category-scores/refresh")
async def refresh_category_scores(request: Request):
    """Force recalculation of category scores."""
    user_id = request.state.user_id
    await update_category_scores(user_id)
    scores = await get_category_scores(user_id)
    return {
        "scores": scores,
        "count": len(scores),
        "blocked_count": sum(1 for s in scores if s.get("is_blocked")),
    }


@router.get("/drawdown-status")
async def get_drawdown_status(request: Request):
    """Get current drawdown level and active restrictions."""
    user_id = request.state.user_id
    mode = request.state.trading_mode
    daily_pnl_pct = 0.0
    try:
        from db.models import PaperPortfolio, PaperTrade
        from sqlalchemy import func
        async with get_session() as session:
            portfolio_result = await session.execute(
                select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
            )
            portfolio = portfolio_result.scalar_one_or_none()
            if portfolio and portfolio.initial_capital:
                start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                trade_result = await session.execute(
                    select(func.sum(PaperTrade.pnl)).where(
                        PaperTrade.user_id == user_id,
                        PaperTrade.exit_time.is_not(None),
                        PaperTrade.exit_time >= start_of_day,
                    )
                )
                realized_today = float(trade_result.scalar() or 0.0)
                daily_pnl_pct = realized_today / float(portfolio.initial_capital) * 100.0
    except Exception as e:
        logger.warning("daily_pnl_calc_error", user_id=user_id, error=str(e))

    mode_str = mode.value if hasattr(mode, "value") else str(mode)
    status = await evaluate_drawdown_level(user_id=user_id, daily_pnl_pct=daily_pnl_pct, mode=mode_str)
    thresholds = await get_drawdown_thresholds(user_id, mode=mode_str)
    return {
        "level": status.level,
        "daily_pnl_pct": round(status.daily_pnl_pct, 2),
        "weekly_pnl_pct": round(status.weekly_pnl_pct, 2),
        "size_multiplier": status.size_multiplier,
        "restrictions": status.restrictions,
        "thresholds": thresholds,
    }


@router.put("/limits")
async def update_risk_limits(req: UpdateRiskLimitsRequest, request: Request):
    """Update risk limit thresholds including graduated drawdown settings."""
    mode = request.state.trading_mode
    user_id = request.state.user_id
    async with get_session() as db:
        result = await db.execute(
            select(UserRiskLimits).where(UserRiskLimits.user_id == user_id, UserRiskLimits.mode == mode)
        )
        limits = result.scalar_one_or_none()
        if not limits:
            limits = UserRiskLimits(user_id=user_id, mode=mode)
            db.add(limits)
        if req.daily_loss_limit is not None:
            limits.daily_loss_limit = req.daily_loss_limit
        if req.max_position_size_pct is not None:
            limits.max_position_size_pct = req.max_position_size_pct
        if req.max_open_positions is not None:
            limits.max_open_positions = req.max_open_positions
        if req.drawdown_reduce_pct is not None:
            if req.drawdown_reduce_pct > 0:
                raise HTTPException(400, "drawdown_reduce_pct must be negative")
            limits.drawdown_reduce_pct = req.drawdown_reduce_pct
        if req.drawdown_halt_pct is not None:
            if req.drawdown_halt_pct > 0:
                raise HTTPException(400, "drawdown_halt_pct must be negative")
            limits.drawdown_halt_pct = req.drawdown_halt_pct
        if req.drawdown_kill_pct is not None:
            if req.drawdown_kill_pct > 0:
                raise HTTPException(400, "drawdown_kill_pct must be negative")
            limits.drawdown_kill_pct = req.drawdown_kill_pct
        if req.weekly_drawdown_kill_pct is not None:
            if req.weekly_drawdown_kill_pct > 0:
                raise HTTPException(400, "weekly_drawdown_kill_pct must be negative")
            limits.weekly_drawdown_kill_pct = req.weekly_drawdown_kill_pct
        if req.sector_concentration_limit is not None:
            if req.sector_concentration_limit <= 0 or req.sector_concentration_limit > 1.0:
                raise HTTPException(400, "sector_concentration_limit must be between 0 and 1.0")
            limits.sector_concentration_limit = req.sector_concentration_limit
        if req.category_block_threshold is not None:
            if req.category_block_threshold < 0 or req.category_block_threshold > 100:
                raise HTTPException(400, "category_block_threshold must be between 0 and 100")
            limits.category_block_threshold = req.category_block_threshold
        limits.updated_at = datetime.utcnow()
    return {"success": True, "mode": mode.value if hasattr(mode, "value") else str(mode)}

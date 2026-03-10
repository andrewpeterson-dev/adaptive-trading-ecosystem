"""Risk limits and kill switch management."""

from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from db.database import get_session
from db.models import UserRiskLimits, TradingModeEnum, SystemEventType
from services.event_logger import log_event

logger = structlog.get_logger(__name__)
router = APIRouter()


class UpdateRiskLimitsRequest(BaseModel):
    daily_loss_limit: float | None = None
    max_position_size_pct: float | None = None
    max_open_positions: int | None = None


@router.get("/limits")
async def get_risk_limits(request: Request):
    mode = request.state.trading_mode
    user_id = request.state.user_id

    async with get_session() as db:
        result = await db.execute(
            select(UserRiskLimits).where(
                UserRiskLimits.user_id == user_id,
                UserRiskLimits.mode == mode,
            )
        )
        limits = result.scalar_one_or_none()

    if not limits:
        return {
            "mode": mode.value,
            "daily_loss_limit": None,
            "max_position_size_pct": 0.25,
            "max_open_positions": 10,
            "kill_switch_active": False,
            "live_bot_trading_confirmed": False,
        }

    return {
        "mode": mode.value,
        "daily_loss_limit": limits.daily_loss_limit,
        "max_position_size_pct": limits.max_position_size_pct,
        "max_open_positions": limits.max_open_positions,
        "kill_switch_active": limits.kill_switch_active,
        "live_bot_trading_confirmed": limits.live_bot_trading_confirmed,
    }


@router.put("/limits")
async def update_risk_limits(req: UpdateRiskLimitsRequest, request: Request):
    mode = request.state.trading_mode
    user_id = request.state.user_id

    async with get_session() as db:
        result = await db.execute(
            select(UserRiskLimits).where(
                UserRiskLimits.user_id == user_id,
                UserRiskLimits.mode == mode,
            )
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
        limits.updated_at = datetime.utcnow()

    return {"success": True, "mode": mode.value}


@router.post("/kill-switch")
async def toggle_kill_switch(request: Request):
    mode = request.state.trading_mode
    user_id = request.state.user_id

    async with get_session() as db:
        result = await db.execute(
            select(UserRiskLimits).where(
                UserRiskLimits.user_id == user_id,
                UserRiskLimits.mode == mode,
            )
        )
        limits = result.scalar_one_or_none()

        if not limits:
            limits = UserRiskLimits(user_id=user_id, mode=mode, kill_switch_active=True)
            db.add(limits)
        else:
            limits.kill_switch_active = not limits.kill_switch_active
        limits.updated_at = datetime.utcnow()

        new_state = limits.kill_switch_active

    await log_event(
        user_id=user_id,
        event_type=SystemEventType.KILL_SWITCH_TOGGLED,
        mode=mode,
        description=f"Kill switch {'activated' if new_state else 'deactivated'}",
        severity="critical",
    )

    return {"kill_switch_active": new_state, "mode": mode.value}


@router.post("/confirm-live-bots")
async def confirm_live_bot_trading(request: Request):
    user_id = request.state.user_id
    mode = request.state.trading_mode

    if mode != TradingModeEnum.LIVE:
        raise HTTPException(400, "Can only confirm live bot trading while in live mode")

    async with get_session() as db:
        result = await db.execute(
            select(UserRiskLimits).where(
                UserRiskLimits.user_id == user_id,
                UserRiskLimits.mode == TradingModeEnum.LIVE,
            )
        )
        limits = result.scalar_one_or_none()

        if not limits:
            limits = UserRiskLimits(user_id=user_id, mode=TradingModeEnum.LIVE, live_bot_trading_confirmed=True)
            db.add(limits)
        else:
            limits.live_bot_trading_confirmed = True
        limits.updated_at = datetime.utcnow()

    await log_event(
        user_id=user_id,
        event_type=SystemEventType.BOT_ENABLED,
        mode=TradingModeEnum.LIVE,
        description="User confirmed live bot trading",
        severity="critical",
    )

    return {"confirmed": True}

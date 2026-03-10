"""User trading mode endpoints — server-authoritative mode switching."""

from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from db.database import get_session
from db.models import UserTradingSession, TradingModeEnum, SystemEventType
from services.event_logger import log_event

logger = structlog.get_logger(__name__)
router = APIRouter()


class SetModeRequest(BaseModel):
    mode: str  # "paper" or "live"


@router.get("/mode")
async def get_mode(request: Request):
    """Return the user's current server-side trading mode."""
    user_id = request.state.user_id
    async with get_session() as db:
        result = await db.execute(
            select(UserTradingSession).where(UserTradingSession.user_id == user_id)
        )
        session = result.scalar_one_or_none()

    mode = session.active_mode if session else TradingModeEnum.PAPER
    return {"mode": mode.value}


@router.post("/set-mode")
async def set_mode(req: SetModeRequest, request: Request):
    """Switch the user's active trading mode. Server-authoritative."""
    user_id = request.state.user_id

    # Validate
    try:
        new_mode = TradingModeEnum(req.mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}. Must be 'paper' or 'live'.")

    if new_mode == TradingModeEnum.BACKTEST:
        raise HTTPException(status_code=400, detail="Cannot manually switch to backtest mode.")

    async with get_session() as db:
        result = await db.execute(
            select(UserTradingSession).where(UserTradingSession.user_id == user_id)
        )
        session = result.scalar_one_or_none()

        old_mode = session.active_mode if session else TradingModeEnum.PAPER

        if session:
            session.active_mode = new_mode
            session.updated_at = datetime.utcnow()
        else:
            db.add(UserTradingSession(user_id=user_id, active_mode=new_mode))

    # Log the event
    await log_event(
        user_id=user_id,
        event_type=SystemEventType.MODE_SWITCH,
        mode=new_mode,
        description=f"Switched from {old_mode.value} to {new_mode.value}",
    )

    logger.info("mode_switched", user_id=user_id, old=old_mode.value, new=new_mode.value)
    return {"mode": new_mode.value, "previous": old_mode.value}

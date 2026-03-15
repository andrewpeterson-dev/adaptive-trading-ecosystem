"""Shared authorization helpers for privileged routes."""

from __future__ import annotations

import structlog
from fastapi import HTTPException, Request
from sqlalchemy import select

from db.database import get_session
from db.models import User

logger = structlog.get_logger(__name__)


async def require_admin(request: Request) -> int:
    """Return the authenticated user id when the caller is an active admin."""
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    async with get_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

    if not user or not user.is_active:
        logger.warning("admin_access_denied", user_id=user_id, reason="inactive_or_missing")
        raise HTTPException(status_code=403, detail="Admin access required")
    if not user.is_admin:
        logger.warning("admin_access_denied", user_id=user_id, reason="not_admin")
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id


async def require_owned_bot(request: Request, bot_id: str):
    """Return the authenticated user's bot or raise when it is not owned."""
    from db.cerberus_models import CerberusBot

    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    async with get_session() as session:
        result = await session.execute(
            select(CerberusBot).where(
                CerberusBot.id == bot_id,
                CerberusBot.user_id == user_id,
            )
        )
        bot = result.scalar_one_or_none()

    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return bot

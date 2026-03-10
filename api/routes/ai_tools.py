"""Cerberus tool endpoints -- trade proposals and confirmations."""
from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

logger = structlog.get_logger(__name__)
router = APIRouter()


class CreateBotRequest(BaseModel):
    name: str
    strategy_json: dict


class ConfirmTradeRequest(BaseModel):
    proposalId: str


class ExecuteTradeRequest(BaseModel):
    proposalId: str
    confirmationToken: str


@router.post("/create-bot")
async def create_bot(request: Request, body: CreateBotRequest):
    """Create a trading bot from a strategy spec."""
    from db.database import get_session
    from db.cerberus_models import CerberusBot, CerberusBotVersion, BotStatus
    import uuid

    user_id = request.state.user_id
    bot_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())

    async with get_session() as session:
        bot = CerberusBot(
            id=bot_id,
            user_id=user_id,
            name=body.name,
            status=BotStatus.DRAFT,
        )
        version = CerberusBotVersion(
            id=version_id,
            bot_id=bot_id,
            version_number=1,
            config_json=body.strategy_json,
        )
        bot.current_version_id = version_id
        session.add(bot)
        session.add(version)

    logger.info("bot_created", bot_id=bot_id, user_id=user_id, name=body.name)
    return {
        "bot_id": bot_id,
        "name": body.name,
        "status": "draft",
        "version": 1,
    }


@router.get("/bots")
async def list_bots(request: Request):
    """List all bots for the current user."""
    from db.database import get_session
    from db.cerberus_models import CerberusBot, CerberusBotVersion
    from sqlalchemy import select

    user_id = request.state.user_id

    async with get_session() as session:
        stmt = select(CerberusBot).where(
            CerberusBot.user_id == user_id,
        ).order_by(CerberusBot.created_at.desc())
        result = await session.execute(stmt)
        bots = result.scalars().all()

        bot_list = []
        for b in bots:
            # Get current version config
            config = None
            if b.current_version_id:
                ver_result = await session.execute(
                    select(CerberusBotVersion).where(CerberusBotVersion.id == b.current_version_id)
                )
                ver = ver_result.scalar_one_or_none()
                if ver:
                    config = ver.config_json

            bot_list.append({
                "id": b.id,
                "name": b.name,
                "status": b.status.value if b.status else "draft",
                "config": config,
                "createdAt": b.created_at.isoformat() if b.created_at else None,
            })

    return bot_list


@router.post("/confirm-trade")
async def confirm_trade(request: Request, body: ConfirmTradeRequest):
    """Confirm a trade proposal and get a confirmation token."""
    from services.ai_core.proposals.confirmation_service import ConfirmationService

    user_id = request.state.user_id
    service = ConfirmationService()

    try:
        result = await service.confirm_proposal(body.proposalId, user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/execute-trade")
async def execute_trade(request: Request, body: ExecuteTradeRequest):
    """Execute a confirmed trade."""
    from services.ai_core.proposals.confirmation_service import ConfirmationService

    user_id = request.state.user_id
    service = ConfirmationService()

    try:
        result = await service.execute_confirmed(
            body.proposalId, body.confirmationToken, user_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/proposals")
async def list_proposals(
    request: Request, status: Optional[str] = None, limit: int = 20
):
    """List trade proposals for the current user."""
    from db.database import get_session
    from db.cerberus_models import CerberusTradeProposal
    from sqlalchemy import select

    user_id = request.state.user_id

    async with get_session() as session:
        stmt = select(CerberusTradeProposal).where(
            CerberusTradeProposal.user_id == user_id
        )
        if status:
            stmt = stmt.where(CerberusTradeProposal.status == status)
        stmt = stmt.order_by(CerberusTradeProposal.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        proposals = result.scalars().all()

    return [
        {
            "id": p.id,
            "threadId": p.thread_id,
            "proposalJson": p.proposal_json,
            "riskJson": p.risk_json,
            "explanationMd": p.explanation_md,
            "status": p.status.value if p.status else None,
            "expiresAt": p.expires_at.isoformat() if p.expires_at else None,
            "createdAt": p.created_at.isoformat() if p.created_at else None,
        }
        for p in proposals
    ]

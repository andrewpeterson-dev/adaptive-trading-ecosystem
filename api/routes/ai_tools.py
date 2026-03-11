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


class DeployFromStrategyRequest(BaseModel):
    strategy_id: int
    name: Optional[str] = None


@router.post("/bots/from-strategy")
async def create_bot_from_strategy(request: Request, body: DeployFromStrategyRequest):
    """Create and immediately deploy a bot from a saved strategy."""
    from db.database import get_session
    from db.cerberus_models import CerberusBot, CerberusBotVersion, BotStatus
    from db.models import Strategy
    from sqlalchemy import select
    import uuid

    user_id = request.state.user_id

    async with get_session() as session:
        # Load the strategy
        strat_result = await session.execute(
            select(Strategy).where(Strategy.id == body.strategy_id, Strategy.user_id == user_id)
        )
        strategy = strat_result.scalar_one_or_none()
        if not strategy:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Strategy not found")

        bot_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        bot_name = body.name or strategy.name

        config = {
            "strategy_id": strategy.id,
            "name": strategy.name,
            "action": strategy.action,
            "timeframe": strategy.timeframe,
            "stop_loss_pct": strategy.stop_loss_pct,
            "take_profit_pct": strategy.take_profit_pct,
            "position_size_pct": strategy.position_size_pct,
            "symbols": strategy.symbols or [],
            "conditions": [
                {
                    "indicator": c["indicator"],
                    "operator": c["operator"],
                    "value": c["value"],
                    "params": c.get("params") or {},
                    **({"compare_to": c["compare_to"]} if c.get("compare_to") else {}),
                }
                for c in (strategy.conditions or [])
            ],
        }

        bot = CerberusBot(id=bot_id, user_id=user_id, name=bot_name, status=BotStatus.RUNNING)
        version = CerberusBotVersion(id=version_id, bot_id=bot_id, version_number=1, config_json=config)
        bot.current_version_id = version_id
        session.add(bot)
        session.add(version)

    logger.info("bot_deployed_from_strategy", bot_id=bot_id, strategy_id=body.strategy_id)
    return {"bot_id": bot_id, "name": bot_name, "status": "running", "strategy_id": body.strategy_id}


@router.post("/bots/{bot_id}/deploy")
async def deploy_bot(bot_id: str, request: Request):
    """Deploy (start running) a bot."""
    from db.database import get_session
    from db.cerberus_models import CerberusBot, BotStatus
    from sqlalchemy import select

    user_id = request.state.user_id
    async with get_session() as session:
        result = await session.execute(
            select(CerberusBot).where(CerberusBot.id == bot_id, CerberusBot.user_id == user_id)
        )
        bot = result.scalar_one_or_none()
        if not bot:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Bot not found")
        bot.status = BotStatus.RUNNING

    logger.info("bot_deployed", bot_id=bot_id, user_id=user_id)
    return {"bot_id": bot_id, "status": "running"}


@router.post("/bots/{bot_id}/stop")
async def stop_bot(bot_id: str, request: Request):
    """Stop a running bot."""
    from db.database import get_session
    from db.cerberus_models import CerberusBot, BotStatus
    from sqlalchemy import select

    user_id = request.state.user_id
    async with get_session() as session:
        result = await session.execute(
            select(CerberusBot).where(CerberusBot.id == bot_id, CerberusBot.user_id == user_id)
        )
        bot = result.scalar_one_or_none()
        if not bot:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Bot not found")
        bot.status = BotStatus.STOPPED

    logger.info("bot_stopped", bot_id=bot_id, user_id=user_id)
    return {"bot_id": bot_id, "status": "stopped"}


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


@router.get("/bots/{bot_id}/activity")
async def get_bot_activity(bot_id: str, request: Request, limit: int = 50):
    """Get recent trades made by a bot."""
    from db.database import get_session
    from db.cerberus_models import CerberusTrade
    from sqlalchemy import select

    user_id = request.state.user_id
    async with get_session() as session:
        result = await session.execute(
            select(CerberusTrade)
            .where(
                CerberusTrade.bot_id == bot_id,
                CerberusTrade.user_id == user_id,
            )
            .order_by(CerberusTrade.created_at.desc())
            .limit(limit)
        )
        trades = result.scalars().all()

    return [
        {
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "quantity": t.quantity,
            "entryPrice": t.entry_price,
            "exitPrice": t.exit_price,
            "grossPnl": t.gross_pnl,
            "netPnl": t.net_pnl,
            "status": "filled",
            "strategyTag": t.strategy_tag,
            "createdAt": t.created_at.isoformat() if t.created_at else None,
        }
        for t in trades
    ]

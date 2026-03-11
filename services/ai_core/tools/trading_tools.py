"""Trading tools for the Cerberus.

All write operations create records but do NOT execute trades directly.
Live trade execution requires explicit user confirmation via the proposal flow.
"""
from __future__ import annotations

import uuid

import structlog

from services.ai_core.tools.base import ToolDefinition, ToolCategory, ToolSideEffect
from services.ai_core.tools.registry import get_registry

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _create_bot(
    user_id: int,
    name: str,
    strategy_name: str = None,
    config: dict = None,
) -> dict:
    """Create a new bot in draft status."""
    from db.database import get_session
    from db.cerberus_models import CerberusBot, CerberusBotVersion, BotStatus

    bot_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())

    async with get_session() as session:
        bot = CerberusBot(
            id=bot_id,
            user_id=user_id,
            name=name,
            status=BotStatus.DRAFT,
            current_version_id=version_id,
        )
        version = CerberusBotVersion(
            id=version_id,
            bot_id=bot_id,
            version_number=1,
            config_json=config or {"strategy_name": strategy_name},
            diff_summary="Initial version",
            created_by="cerberus",
        )
        session.add(bot)
        session.add(version)

    return {
        "bot_id": bot_id,
        "version_id": version_id,
        "name": name,
        "status": "draft",
        "version_number": 1,
    }


async def _modify_bot(
    user_id: int,
    bot_id: str,
    config: dict = None,
    diff_summary: str = None,
) -> dict:
    """Modify bot config by creating a new version."""
    from db.database import get_session
    from db.cerberus_models import CerberusBot, CerberusBotVersion
    from sqlalchemy import select, func

    async with get_session() as session:
        # Verify ownership
        stmt = select(CerberusBot).where(CerberusBot.id == bot_id, CerberusBot.user_id == user_id)
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()
        if not bot:
            return {"error": "Bot not found or not owned by user", "bot_id": bot_id}

        # Get next version number
        ver_stmt = select(func.max(CerberusBotVersion.version_number)).where(
            CerberusBotVersion.bot_id == bot_id
        )
        ver_result = await session.execute(ver_stmt)
        max_ver = ver_result.scalar() or 0

        version_id = str(uuid.uuid4())
        version = CerberusBotVersion(
            id=version_id,
            bot_id=bot_id,
            version_number=max_ver + 1,
            config_json=config or {},
            diff_summary=diff_summary or "Updated via Cerberus",
            created_by="cerberus",
        )
        session.add(version)
        bot.current_version_id = version_id

    return {
        "bot_id": bot_id,
        "version_id": version_id,
        "version_number": max_ver + 1,
        "diff_summary": diff_summary or "Updated via Cerberus",
    }


async def _stop_bot(user_id: int, bot_id: str) -> dict:
    """Stop a running bot."""
    return await _set_bot_status(user_id, bot_id, "stopped")


async def _pause_bot(user_id: int, bot_id: str) -> dict:
    """Pause a running bot."""
    return await _set_bot_status(user_id, bot_id, "paused")


async def _resume_bot(user_id: int, bot_id: str) -> dict:
    """Resume a paused bot."""
    return await _set_bot_status(user_id, bot_id, "running")


async def _set_bot_status(user_id: int, bot_id: str, new_status: str) -> dict:
    """Set bot status (internal helper)."""
    from db.database import get_session
    from db.cerberus_models import CerberusBot, BotStatus
    from sqlalchemy import select

    async with get_session() as session:
        stmt = select(CerberusBot).where(CerberusBot.id == bot_id, CerberusBot.user_id == user_id)
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()
        if not bot:
            return {"error": "Bot not found or not owned by user", "bot_id": bot_id}

        old_status = bot.status.value if isinstance(bot.status, BotStatus) else str(bot.status)
        bot.status = BotStatus(new_status)

    return {
        "bot_id": bot_id,
        "old_status": old_status,
        "new_status": new_status,
    }


async def _backtest_strategy(
    user_id: int,
    strategy_name: str,
    params: dict = None,
    bot_id: str = None,
    bot_version_id: str = None,
) -> dict:
    """Create and execute or queue a real backtest run."""
    from db.database import get_session
    from db.cerberus_models import CerberusBacktest
    from services.workers.job_runners import execute_backtest_job

    backtest_id = str(uuid.uuid4())
    params_payload = params or {}

    async with get_session() as session:
        bt = CerberusBacktest(
            id=backtest_id,
            user_id=user_id,
            bot_id=bot_id,
            bot_version_id=bot_version_id,
            strategy_name=strategy_name,
            params_json=params_payload,
            status="pending",
        )
        session.add(bt)

    inline_result = None
    execution_mode = "queued"
    try:
        from services.workers.tasks import run_backtest as run_backtest_task

        run_backtest_task.delay(backtest_id, user_id)
    except Exception as exc:
        logger.warning("backtest_queue_failed_falling_back_inline", backtest_id=backtest_id, error=str(exc))
        inline_result = await execute_backtest_job(backtest_id, user_id)
        execution_mode = "inline"

    return {
        "backtest_id": backtest_id,
        "strategy_name": strategy_name,
        "status": "completed" if inline_result else "pending",
        "execution_mode": execution_mode,
        "message": "Backtest completed" if inline_result else "Backtest queued. Results will be available once processing completes.",
        "metrics": inline_result.get("metrics", {}) if inline_result else {},
    }


async def _create_trade_proposal(
    user_id: int,
    symbol: str,
    side: str,
    quantity: float,
    order_type: str = "market",
    limit_price: float = None,
    explanation: str = None,
    thread_id: str = None,
) -> dict:
    """Create a trade proposal (draft). Does NOT execute."""
    from data.market_data import market_data
    from services.ai_core.proposals.trade_proposal_service import TradeProposalService

    normalized_symbol = symbol.upper()
    estimated_price = float(limit_price) if limit_price is not None else None
    if estimated_price is None:
        quote = await market_data.get_quote(normalized_symbol)
        if quote and quote.get("price") is not None:
            estimated_price = float(quote["price"])

    proposal_json = {
        "symbol": normalized_symbol,
        "side": side,
        "quantity": quantity,
        "order_type": order_type,
        "limit_price": limit_price,
        "estimated_price": estimated_price,
    }

    result = await TradeProposalService().create_proposal(
        user_id=user_id,
        thread_id=thread_id,
        proposal_data=proposal_json,
        explanation=explanation or "",
    )

    result.setdefault("proposal", proposal_json)
    if result.get("status") == "blocked":
        result["message"] = "Trade proposal blocked by pre-trade risk checks."
        return result

    result["expires_in_minutes"] = 5
    result["message"] = "Trade proposal created. User must confirm before execution."
    return result


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register():
    registry = get_registry()

    registry.register(ToolDefinition(
        name="createBot",
        version="1.0",
        description="Create a new trading bot in draft status",
        category=ToolCategory.TRADING,
        side_effect=ToolSideEffect.WRITE,
        timeout_ms=3000,
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Bot name"},
                "strategy_name": {"type": "string", "description": "Strategy identifier"},
                "config": {"type": "object", "description": "Bot configuration object"},
            },
            "required": ["name"],
        },
        output_schema={"type": "object"},
        handler=_create_bot,
    ))

    registry.register(ToolDefinition(
        name="modifyBot",
        version="1.0",
        description="Modify a bot's configuration (creates a new version)",
        category=ToolCategory.TRADING,
        side_effect=ToolSideEffect.WRITE,
        timeout_ms=3000,
        input_schema={
            "type": "object",
            "properties": {
                "bot_id": {"type": "string", "description": "Bot ID to modify"},
                "config": {"type": "object", "description": "New configuration"},
                "diff_summary": {"type": "string", "description": "Description of changes"},
            },
            "required": ["bot_id"],
        },
        output_schema={"type": "object"},
        handler=_modify_bot,
    ))

    registry.register(ToolDefinition(
        name="stopBot",
        version="1.0",
        description="Stop a running bot",
        category=ToolCategory.TRADING,
        side_effect=ToolSideEffect.WRITE,
        timeout_ms=2000,
        input_schema={
            "type": "object",
            "properties": {
                "bot_id": {"type": "string", "description": "Bot ID to stop"},
            },
            "required": ["bot_id"],
        },
        output_schema={"type": "object"},
        handler=_stop_bot,
    ))

    registry.register(ToolDefinition(
        name="pauseBot",
        version="1.0",
        description="Pause a running bot (can be resumed later)",
        category=ToolCategory.TRADING,
        side_effect=ToolSideEffect.WRITE,
        timeout_ms=2000,
        input_schema={
            "type": "object",
            "properties": {
                "bot_id": {"type": "string", "description": "Bot ID to pause"},
            },
            "required": ["bot_id"],
        },
        output_schema={"type": "object"},
        handler=_pause_bot,
    ))

    registry.register(ToolDefinition(
        name="resumeBot",
        version="1.0",
        description="Resume a paused bot",
        category=ToolCategory.TRADING,
        side_effect=ToolSideEffect.WRITE,
        timeout_ms=2000,
        input_schema={
            "type": "object",
            "properties": {
                "bot_id": {"type": "string", "description": "Bot ID to resume"},
            },
            "required": ["bot_id"],
        },
        output_schema={"type": "object"},
        handler=_resume_bot,
    ))

    registry.register(ToolDefinition(
        name="backtestStrategy",
        version="1.0",
        description="Enqueue a backtest run for a strategy with given parameters",
        category=ToolCategory.TRADING,
        side_effect=ToolSideEffect.WRITE,
        timeout_ms=5000,
        input_schema={
            "type": "object",
            "properties": {
                "strategy_name": {"type": "string", "description": "Strategy to backtest"},
                "params": {"type": "object", "description": "Strategy parameters (symbols, dates, etc.)"},
                "bot_id": {"type": "string", "description": "Optional bot ID to associate"},
                "bot_version_id": {"type": "string", "description": "Optional bot version ID"},
            },
            "required": ["strategy_name"],
        },
        output_schema={"type": "object"},
        handler=_backtest_strategy,
    ))

    registry.register(ToolDefinition(
        name="createTradeProposal",
        version="1.0",
        description="Create a trade proposal for user review. Does NOT execute the trade.",
        category=ToolCategory.TRADING,
        side_effect=ToolSideEffect.WRITE,
        requires_confirmation=True,
        timeout_ms=3000,
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol"},
                "side": {"type": "string", "enum": ["buy", "sell"], "description": "Trade side"},
                "quantity": {"type": "number", "description": "Number of shares/contracts"},
                "order_type": {"type": "string", "enum": ["market", "limit", "stop", "stop_limit"], "default": "market"},
                "limit_price": {"type": "number", "description": "Limit price (for limit/stop_limit orders)"},
                "explanation": {"type": "string", "description": "AI explanation of the trade rationale"},
                "thread_id": {"type": "string", "description": "Conversation thread ID"},
            },
            "required": ["symbol", "side", "quantity"],
        },
        output_schema={"type": "object"},
        handler=_create_trade_proposal,
    ))

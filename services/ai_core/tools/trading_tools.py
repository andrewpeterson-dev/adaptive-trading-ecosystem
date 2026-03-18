"""Trading tools for the Cerberus.

All write operations create records but do NOT execute trades directly.
Live trade execution requires explicit user confirmation via the proposal flow.
"""
from __future__ import annotations

from copy import deepcopy
import uuid

import structlog

from services.ai_core.tools.base import ToolDefinition, ToolCategory, ToolSideEffect
from services.ai_core.tools.registry import get_registry
from services.strategy_learning_engine import normalize_bot_config
from services.strategy_validator import validate_strategy_config

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _clean_name(value: str | None) -> str:
    return str(value or "").strip()


def _normalized_symbols(config: dict) -> list[str]:
    raw = config.get("symbols")
    if not isinstance(raw, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw:
        symbol = str(item or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        normalized.append(symbol)
    return normalized


def _iter_condition_candidates(config: dict):
    raw_conditions = config.get("conditions")
    if isinstance(raw_conditions, list):
        for condition in raw_conditions:
            if isinstance(condition, dict):
                yield condition

    raw_groups = config.get("condition_groups")
    if isinstance(raw_groups, list):
        for group in raw_groups:
            if not isinstance(group, dict):
                continue
            conditions = group.get("conditions")
            if not isinstance(conditions, list):
                continue
            for condition in conditions:
                if isinstance(condition, dict):
                    yield condition


def _prepare_bot_config(config: dict | None) -> tuple[dict | None, str | None]:
    if not isinstance(config, dict):
        return None, "Bot config is required"

    normalized = normalize_bot_config(config)
    errors: list[str] = []

    action = str(normalized.get("action", "") or "").strip().upper()
    if action not in {"BUY", "SELL", "SHORT"}:
        errors.append("action must be BUY, SELL, or SHORT")
    else:
        normalized["action"] = action

    timeframe = str(normalized.get("timeframe", "") or "").strip()
    if not timeframe:
        errors.append("timeframe is required")
    else:
        normalized["timeframe"] = timeframe

    symbols = _normalized_symbols(normalized)
    if not symbols:
        errors.append("at least one symbol is required")
    else:
        normalized["symbols"] = symbols

    if not any(
        str(condition.get("indicator", "") or "").strip()
        and str(condition.get("operator", "") or "").strip()
        for condition in _iter_condition_candidates(normalized)
    ):
        errors.append("at least one executable condition is required")

    if errors:
        return None, f"Bot configuration is invalid: {', '.join(errors)}"
    return normalized, None

async def _create_bot(
    user_id: int,
    name: str,
    strategy_name: str = None,
    config: dict = None,
) -> dict:
    """Create a new bot and immediately activate it for trading."""
    from db.database import get_session
    from db.cerberus_models import CerberusBot, CerberusBotVersion, BotStatus

    bot_name = _clean_name(name)
    if not bot_name:
        return {"error": "Bot name is required"}

    normalized_config, error = _prepare_bot_config(config)
    if error:
        logger.warning("tool_create_bot_rejected", user_id=user_id, name=bot_name, detail=error)
        return {"error": error, "name": bot_name}

    # ── Strategy validation gate ──
    is_valid, val_errors, val_warnings = validate_strategy_config(normalized_config)
    if not is_valid:
        detail = "Bot config failed validation: " + "; ".join(val_errors)
        logger.warning("tool_create_bot_validation_failed", user_id=user_id, name=bot_name, errors=val_errors)
        return {"error": detail, "name": bot_name, "validation_errors": val_errors}

    learning = normalized_config.get("learning") or {}
    bot_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())

    async with get_session() as session:
        bot = CerberusBot(
            id=bot_id,
            user_id=user_id,
            name=bot_name,
            status=BotStatus.PAUSED,
            current_version_id=version_id,
            learning_enabled=bool(learning.get("enabled", True)),
            learning_status_json={
                "status": "monitoring" if learning.get("enabled", True) else "disabled",
                "summary": learning.get("last_summary", "Bot created — review and start when ready."),
                "metrics": {},
                "featureSignals": normalized_config.get("feature_signals", []),
                "parameterAdjustments": [],
                "methods": learning.get("methods", []),
            },
        )
        version = CerberusBotVersion(
            id=version_id,
            bot_id=bot_id,
            version_number=1,
            config_json=normalized_config,
            diff_summary="Initial version",
            created_by="cerberus",
        )
        session.add(bot)
        session.add(version)

    result = {
        "bot_id": bot_id,
        "version_id": version_id,
        "name": bot_name,
        "status": "paused",
        "version_number": 1,
        "message": f"Bot '{bot_name}' created in PAUSED state. Use resumeBot to start trading.",
    }
    if val_warnings:
        result["warnings"] = val_warnings
    logger.info("bot_created_paused", bot_id=bot_id, name=bot_name, user_id=user_id)
    return result


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

        base_config: dict = {}
        if bot.current_version_id:
            current_version_stmt = select(CerberusBotVersion).where(
                CerberusBotVersion.id == bot.current_version_id,
                CerberusBotVersion.bot_id == bot_id,
            )
            current_version_result = await session.execute(current_version_stmt)
            current_version = current_version_result.scalar_one_or_none()
            if current_version and isinstance(current_version.config_json, dict):
                base_config = deepcopy(current_version.config_json)

        merged_config = deepcopy(base_config)
        if config:
            merged_config.update(config)

        normalized_config, error = _prepare_bot_config(merged_config if merged_config else config)
        if error:
            logger.warning("tool_modify_bot_rejected", user_id=user_id, bot_id=bot_id, detail=error)
            return {"error": error, "bot_id": bot_id}

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
            config_json=normalized_config,
            diff_summary=diff_summary or "Updated via Cerberus",
            created_by="cerberus",
        )
        session.add(version)
        bot.current_version_id = version_id
        bot.learning_enabled = bool((normalized_config.get("learning") or {}).get("enabled", False))

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
    from db.cerberus_models import CerberusBot, CerberusBotVersion, BotStatus
    from sqlalchemy import select

    async with get_session() as session:
        stmt = select(CerberusBot).where(CerberusBot.id == bot_id, CerberusBot.user_id == user_id)
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()
        if not bot:
            return {"error": "Bot not found or not owned by user", "bot_id": bot_id}

        if new_status == "running":
            if not bot.current_version_id:
                return {"error": "Bot has no deployable version", "bot_id": bot_id}

            version_stmt = select(CerberusBotVersion).where(
                CerberusBotVersion.id == bot.current_version_id,
                CerberusBotVersion.bot_id == bot_id,
            )
            version_result = await session.execute(version_stmt)
            version = version_result.scalar_one_or_none()
            if not version:
                return {"error": "Bot has no deployable version", "bot_id": bot_id}

            normalized_config, error = _prepare_bot_config(version.config_json)
            if error:
                logger.warning("tool_set_bot_status_rejected", user_id=user_id, bot_id=bot_id, detail=error)
                return {"error": error, "bot_id": bot_id}

            version.config_json = normalized_config
            bot.learning_enabled = bool((normalized_config.get("learning") or {}).get("enabled", False))

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


async def _run_deep_trade_analysis(
    user_id: int,
    symbol: str,
    action: str = "buy",
    size: float = 0,
) -> dict:
    """Run multi-agent deep trade analysis pipeline.

    Invokes a LangGraph pipeline with 7 specialist agents:
    Technical Analyst, Fundamental Analyst, Sentiment Analyst,
    Bull Researcher, Bear Researcher, Risk Assessor, and
    Decision Synthesizer.

    Returns structured result with all reports and final recommendation.
    """
    from services.ai_core.multi_agent.runner import run_trade_analysis

    result = await run_trade_analysis(
        symbol=symbol,
        action=action,
        size=size,
        user_id=user_id,
    )
    return result.to_dict()


async def _fix_bot_with_ai(
    user_id: int,
    bot_id: str,
    instruction: str = "",
) -> dict:
    """Use AI to fix or edit a bot's strategy based on natural language.

    Reads current config, sends it to the LLM with the instruction,
    validates the result, creates a new version. If bot was in ERROR
    status, resets to DRAFT.
    """
    import json
    from db.database import get_session
    from db.cerberus_models import CerberusBot, CerberusBotVersion, BotStatus
    from sqlalchemy import select, func

    if not instruction.strip():
        return {"error": "Please describe what you want to fix or change."}

    async with get_session() as session:
        result = await session.execute(
            select(CerberusBot, CerberusBotVersion)
            .join(CerberusBotVersion, CerberusBot.current_version_id == CerberusBotVersion.id)
            .where(CerberusBot.id == bot_id, CerberusBot.user_id == user_id)
        )
        row = result.one_or_none()
        if not row:
            return {"error": "Bot not found or not owned by user", "bot_id": bot_id}
        bot, current_version = row

    current_config = current_version.config_json or {}

    system_prompt = (
        "You are a trading strategy editor. You will receive a bot's current strategy configuration "
        "and a user instruction to modify it. Return ONLY the modified JSON config — no explanation, "
        "no markdown, no code fences. The output must be valid JSON.\n\n"
        "Rules:\n"
        "- Only modify what the user asks for\n"
        "- Keep all other fields unchanged\n"
        "- Valid indicators: rsi, sma, ema, macd, atr, stochastic, vwap, volume, bollinger_bands, obv\n"
        "- Valid operators: >, <, >=, <=, ==, crosses_above, crosses_below\n"
        "- Valid timeframes: 1m, 5m, 15m, 1H, 4H, 1D, 1W\n"
        "- Valid actions: BUY, SELL\n"
        "- Conditions need: indicator, operator, value, params (with period)\n"
        "- stop_loss_pct and take_profit_pct are percentages (e.g., 2.0 = 2%)\n"
    )

    user_prompt = (
        f"Current strategy config:\n{json.dumps(current_config, indent=2)}\n\n"
        f"User instruction: {instruction}\n\n"
        f"Return the modified JSON config:"
    )

    from services.ai_core.model_router import ModelRouter
    from services.ai_core.providers.base import ProviderMessage
    model_router = ModelRouter()
    routing = model_router.route(mode="strategy", message=instruction, has_tools=False)

    try:
        response = await routing.provider.complete(
            messages=[
                ProviderMessage(role="system", content=system_prompt),
                ProviderMessage(role="user", content=user_prompt),
            ],
            model=routing.model,
            temperature=0.3,
        )
        raw_output = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        return {"error": f"AI model error: {e}"}

    from services.ai_strategy_service import extract_json
    json_str = extract_json(raw_output)
    if not json_str:
        return {"error": "AI returned no valid JSON. Try rephrasing your request."}

    try:
        new_config = json.loads(json_str)
    except Exception:
        return {"error": "AI returned invalid JSON. Try rephrasing your request."}

    normalized = normalize_bot_config(new_config)
    is_valid, val_errors, val_warnings = validate_strategy_config(normalized)

    if not is_valid:
        # Retry once with errors
        retry_prompt = (
            f"{user_prompt}\n\n"
            f"YOUR PREVIOUS OUTPUT HAD VALIDATION ERRORS:\n{json.dumps(val_errors)}\n"
            f"Fix these errors and return valid JSON:"
        )
        try:
            response = await routing.provider.complete(
                messages=[
                    ProviderMessage(role="system", content=system_prompt),
                    ProviderMessage(role="user", content=retry_prompt),
                ],
                model=routing.model,
                temperature=0.2,
            )
            raw_output = response.content if hasattr(response, "content") else str(response)
            json_str = extract_json(raw_output)
            if json_str:
                new_config = json.loads(json_str)
                normalized = normalize_bot_config(new_config)
                is_valid, val_errors, val_warnings = validate_strategy_config(normalized)
        except Exception:
            pass

        if not is_valid:
            return {
                "error": "AI edit still has validation errors after retry",
                "validation_errors": val_errors,
                "config": normalized,
            }

    # Create new version
    async with get_session() as session:
        result = await session.execute(select(CerberusBot).where(CerberusBot.id == bot_id))
        bot = result.scalar_one()

        ver_result = await session.execute(
            select(func.max(CerberusBotVersion.version_number)).where(
                CerberusBotVersion.bot_id == bot_id
            )
        )
        max_ver = ver_result.scalar() or 0

        version_id = str(uuid.uuid4())
        version = CerberusBotVersion(
            id=version_id,
            bot_id=bot_id,
            version_number=max_ver + 1,
            config_json=normalized,
            diff_summary=f"AI fix: {instruction[:200]}",
            created_by="cerberus_ai_fix",
            backtest_required=False,
            override_level=current_version.override_level,
            universe_config=current_version.universe_config,
        )
        session.add(version)
        bot.current_version_id = version_id

        was_error = bot.status == BotStatus.ERROR
        if was_error:
            bot.status = BotStatus.DRAFT

    return {
        "status": "fixed" if was_error else "edited",
        "bot_id": bot_id,
        "version_number": max_ver + 1,
        "diff_summary": f"AI fix: {instruction[:200]}",
        "was_error_status": was_error,
        "validation_warnings": val_warnings,
        "message": f"Strategy updated. {'Bot reset from ERROR to DRAFT — you can redeploy it.' if was_error else 'New version created.'}",
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register():
    registry = get_registry()

    registry.register(ToolDefinition(
        name="createBot",
        version="1.1",
        description=(
            "Create a new trading bot in PAUSED state. The user must call resumeBot to "
            "activate it. Config must include: symbols (list of tickers), "
            "action ('BUY' or 'SELL'), timeframe ('1m','5m','15m','1h','1D'), and at least "
            "one condition with indicator, operator, and value. Include stop_loss_pct and "
            "take_profit_pct as decimals (e.g. 0.03 for 3%). position_size_pct controls "
            "capital allocation per trade (e.g. 0.05 for 5% of equity)."
        ),
        category=ToolCategory.TRADING,
        side_effect=ToolSideEffect.WRITE,
        timeout_ms=10000,
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Bot name"},
                "strategy_name": {"type": "string", "description": "Strategy identifier"},
                "config": {"type": "object", "description": "Full executable bot configuration object"},
            },
            "required": ["name", "config"],
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
                "config": {"type": "object", "description": "New or partial bot configuration"},
                "diff_summary": {"type": "string", "description": "Description of changes"},
            },
            "required": ["bot_id", "config"],
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

    registry.register(ToolDefinition(
        name="runDeepTradeAnalysis",
        version="1.0",
        description=(
            "Run a multi-agent deep trade analysis pipeline. Uses 7 specialist AI agents "
            "(Technical Analyst, Fundamental Analyst, Sentiment Analyst, Bull Researcher, "
            "Bear Researcher, Risk Assessor, Decision Synthesizer) to thoroughly evaluate "
            "a proposed trade. Takes 30-90 seconds. Returns structured analysis with all "
            "reports, bull/bear cases, risk assessment, and a final recommendation with "
            "confidence score. Use this when the user asks for deep analysis of a trade."
        ),
        category=ToolCategory.ANALYTICS,
        side_effect=ToolSideEffect.READ,
        timeout_ms=120000,
        cache_ttl_s=0,
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Ticker symbol (e.g. AAPL, TSLA, SPY)",
                },
                "action": {
                    "type": "string",
                    "enum": ["buy", "sell"],
                    "description": "Proposed trade action",
                    "default": "buy",
                },
                "size": {
                    "type": "number",
                    "description": "Proposed position size (shares/contracts)",
                    "default": 0,
                },
            },
            "required": ["symbol"],
        },
        output_schema={"type": "object"},
        handler=_run_deep_trade_analysis,
    ))

    registry.register(ToolDefinition(
        name="fixBotWithAI",
        version="1.0",
        description=(
            "Use AI to fix or edit a bot's strategy configuration using natural language. "
            "Reads the current config, applies AI-driven changes based on the instruction, "
            "validates the result, and creates a new version. If the bot was in ERROR status, "
            "it resets to DRAFT so it can be redeployed. Use this when a user asks to fix "
            "a broken bot, adjust strategy parameters, change indicators, or tweak conditions. "
            "Examples: 'fix the RSI condition', 'make it more aggressive', 'add a MACD filter', "
            "'change timeframe to 4H', 'reduce position size to 5%'."
        ),
        category=ToolCategory.TRADING,
        side_effect=ToolSideEffect.WRITE,
        timeout_ms=30000,
        input_schema={
            "type": "object",
            "properties": {
                "bot_id": {
                    "type": "string",
                    "description": "Bot ID to fix/edit",
                },
                "instruction": {
                    "type": "string",
                    "description": "Natural language instruction describing what to fix or change",
                },
            },
            "required": ["bot_id", "instruction"],
        },
        output_schema={"type": "object"},
        handler=_fix_bot_with_ai,
    ))

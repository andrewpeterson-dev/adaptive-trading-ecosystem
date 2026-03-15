"""Cerberus tool endpoints -- strategy generation, bots, and trade proposals."""
from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Any, Optional

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from config.settings import get_settings
from db.cerberus_models import (
    BotStatus,
    CerberusBot,
    CerberusBotOptimizationRun,
    CerberusBotVersion,
    CerberusTrade,
)
from db.database import get_session
from db.models import Strategy, StrategyInstance
from services.ai_strategy_service import AIStrategyService, strategy_record_to_bot_config
from services.strategy_learning_engine import (
    build_equity_curve_from_trades,
    calculate_trade_metrics,
    normalize_bot_config,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


class CreateBotRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    strategy_json: dict[str, Any]


class GenerateStrategyRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=20_000)


class ConfirmTradeRequest(BaseModel):
    proposalId: str = Field(..., min_length=1)


class ExecuteTradeRequest(BaseModel):
    proposalId: str = Field(..., min_length=1)
    confirmationToken: str = Field(..., min_length=1)


class DeployFromStrategyRequest(BaseModel):
    strategy_id: int
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)


def _coerce_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_name(value: str | None) -> str:
    return str(value or "").strip()


def _normalized_symbols(config: dict[str, Any]) -> list[str]:
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


def _iter_condition_candidates(config: dict[str, Any]):
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


def _is_executable_condition(condition: dict[str, Any]) -> bool:
    indicator = str(condition.get("indicator", "") or "").strip()
    operator = str(condition.get("operator", "") or "").strip()
    return bool(indicator and operator)


def _validate_bot_config(config: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
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

    if not any(_is_executable_condition(condition) for condition in _iter_condition_candidates(normalized)):
        errors.append("at least one executable condition is required")

    return normalized, errors


def _ensure_valid_bot_config(
    config: dict[str, Any] | None,
    *,
    error_detail: str = "Bot configuration is not deployable",
) -> dict[str, Any]:
    normalized, errors = _validate_bot_config(config)
    if errors:
        raise HTTPException(status_code=400, detail=f"{error_detail}: {', '.join(errors)}")
    return normalized


def _extract_probability_score(payload: dict[str, Any]) -> float | None:
    candidates = [
        payload.get("probability_score"),
        payload.get("probability"),
        payload.get("confidence_score"),
        payload.get("confidence"),
        (payload.get("decision") or {}).get("confidence") if isinstance(payload.get("decision"), dict) else None,
    ]
    for candidate in candidates:
        value = _coerce_float(candidate)
        if value is not None:
            return round(value if value <= 1 else value / 100, 4)
    return None


def _extract_indicator_signals(payload: dict[str, Any], config: dict[str, Any]) -> list[str]:
    raw = (
        payload.get("indicator_signals")
        or payload.get("indicators_used")
        or payload.get("signals")
        or config.get("feature_signals")
        or (config.get("ai_context") or {}).get("feature_signals")
        or []
    )
    if not isinstance(raw, list):
        return []

    signals: list[str] = []
    seen: set[str] = set()
    for item in raw:
        label = None
        if isinstance(item, str):
            label = item
        elif isinstance(item, dict):
            label = item.get("indicator") or item.get("signal") or item.get("name")
        if not label:
            continue
        normalized = str(label).strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            signals.append(normalized)
    return signals


def _derive_risk_assessment(config: dict[str, Any]) -> str:
    position_size = _coerce_float(config.get("position_size_pct")) or 0.0
    stop_loss = _coerce_float(config.get("stop_loss_pct")) or 0.0
    max_exposure = _coerce_float(config.get("max_exposure_pct")) or 0.0

    score = 0
    if position_size >= 0.15:
        score += 2
    elif position_size >= 0.08:
        score += 1

    if stop_loss >= 0.03:
        score += 2
    elif stop_loss >= 0.015:
        score += 1

    if max_exposure >= 0.75:
        score += 2
    elif max_exposure >= 0.4:
        score += 1

    if score <= 2:
        return "Conservative"
    if score <= 4:
        return "Balanced"
    return "Aggressive"


def _project_trade_levels(trade: CerberusTrade, config: dict[str, Any]) -> tuple[float | None, float | None]:
    entry_price = _coerce_float(trade.entry_price)
    if entry_price is None:
        return (None, None)

    stop_pct = _coerce_float(config.get("stop_loss_pct"))
    take_pct = _coerce_float(config.get("take_profit_pct"))
    is_short = str(trade.side or "").lower().startswith("sell")

    stop_loss_price = None
    take_profit_price = None

    if stop_pct and stop_pct > 0:
        stop_loss_price = entry_price * (1 + stop_pct if is_short else 1 - stop_pct)
    if take_pct and take_pct > 0:
        take_profit_price = entry_price * (1 - take_pct if is_short else 1 + take_pct)

    return (
        round(stop_loss_price, 4) if stop_loss_price is not None else None,
        round(take_profit_price, 4) if take_profit_price is not None else None,
    )


def _serialize_trade(trade: CerberusTrade, config: dict[str, Any]) -> dict[str, Any]:
    payload = trade.payload_json if isinstance(trade.payload_json, dict) else {}
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
    explanation = payload.get("bot_explanation") or payload.get("explanation") or trade.notes
    stop_loss_price, take_profit_price = _project_trade_levels(trade, config)
    side = str(trade.side or "").lower()
    exit_action = "buy" if side.startswith("sell") else "sell"

    return {
        "id": trade.id,
        "symbol": trade.symbol,
        "side": side,
        "entryAction": side,
        "exitAction": exit_action,
        "quantity": trade.quantity,
        "entryPrice": trade.entry_price,
        "exitPrice": trade.exit_price,
        "grossPnl": trade.gross_pnl,
        "netPnl": trade.net_pnl,
        "returnPct": trade.return_pct,
        "status": "closed" if trade.exit_price is not None or trade.exit_ts is not None else "open",
        "strategyTag": trade.strategy_tag,
        "createdAt": trade.created_at.isoformat() if trade.created_at else None,
        "entryTs": trade.entry_ts.isoformat() if trade.entry_ts else None,
        "exitTs": trade.exit_ts.isoformat() if trade.exit_ts else None,
        "notes": trade.notes,
        "reasons": [str(reason).strip() for reason in reasons if str(reason).strip()],
        "botExplanation": explanation,
        "probabilityScore": _extract_probability_score(payload),
        "riskAssessment": payload.get("risk_assessment") or _derive_risk_assessment(config),
        "indicatorSignals": _extract_indicator_signals(payload, config),
        "stopLossPrice": stop_loss_price,
        "takeProfitPrice": take_profit_price,
    }


def _learning_status(bot: CerberusBot, config: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    learning = deepcopy(config.get("learning") or {})
    stored = deepcopy(bot.learning_status_json or {})
    last_opt = bot.last_optimization_at.isoformat() if bot.last_optimization_at else learning.get("last_optimization_at")
    cadence = int(learning.get("cadence_minutes", 240) or 240)

    return {
        "enabled": bool(learning.get("enabled", False)),
        "status": stored.get("status") or learning.get("status") or "monitoring",
        "lastOptimizationAt": last_opt,
        "nextOptimizationAt": stored.get("nextOptimizationAt"),
        "method": stored.get("method"),
        "summary": stored.get("summary") or learning.get("last_summary"),
        "methods": stored.get("methods") or learning.get("methods", []),
        "featureSignals": stored.get("featureSignals") or metrics.get("feature_signals", []),
        "metrics": stored.get("metrics") or metrics,
        "parameterAdjustments": stored.get("parameterAdjustments") or learning.get("parameter_adjustments", []),
        "cadenceMinutes": cadence,
    }


def _version_to_dict(version: CerberusBotVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "versionNumber": version.version_number,
        "diffSummary": version.diff_summary,
        "createdBy": version.created_by,
        "backtestRequired": version.backtest_required,
        "backtestId": version.backtest_id,
        "createdAt": version.created_at.isoformat() if version.created_at else None,
    }


def _optimization_run_to_dict(run: CerberusBotOptimizationRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "method": run.method,
        "status": run.status,
        "summary": run.summary,
        "metrics": run.metrics_json or {},
        "adjustments": (run.adjustments_json or {}).get("parameter_adjustments", []),
        "sourceVersionId": run.source_version_id,
        "resultVersionId": run.result_version_id,
        "createdAt": run.created_at.isoformat() if run.created_at else None,
    }


def _strategy_instance_to_record(strategy: StrategyInstance) -> dict[str, Any]:
    template = strategy.template
    return {
        "id": strategy.id,
        "name": template.name,
        "description": template.description or "",
        "conditions": template.conditions or [],
        "condition_groups": template.condition_groups or [],
        "action": template.action,
        "stop_loss_pct": template.stop_loss_pct,
        "take_profit_pct": template.take_profit_pct,
        "position_size_pct": strategy.position_size_pct,
        "timeframe": template.timeframe,
        "symbols": template.symbols or ["SPY"],
        "strategy_type": template.strategy_type or "manual",
        "source_prompt": template.source_prompt,
        "ai_context": template.ai_context or {},
    }


def _legacy_strategy_to_record(strategy: Strategy) -> dict[str, Any]:
    return {
        "id": strategy.id,
        "name": strategy.name,
        "description": strategy.description or "",
        "conditions": strategy.conditions or [],
        "condition_groups": strategy.condition_groups or [],
        "action": strategy.action,
        "stop_loss_pct": strategy.stop_loss_pct,
        "take_profit_pct": strategy.take_profit_pct,
        "position_size_pct": strategy.position_size_pct,
        "timeframe": strategy.timeframe,
        "symbols": strategy.symbols or ["SPY"],
        "strategy_type": getattr(strategy, "strategy_type", None) or "manual",
        "source_prompt": getattr(strategy, "source_prompt", None),
        "ai_context": getattr(strategy, "ai_context", None) or {},
    }


async def _load_strategy_record(session, user_id: int, strategy_id: int) -> dict[str, Any] | None:
    # Try StrategyInstance first (new schema)
    instance_result = await session.execute(
        select(StrategyInstance)
        .options(selectinload(StrategyInstance.template))
        .where(StrategyInstance.id == strategy_id, StrategyInstance.user_id == user_id)
    )
    instance = instance_result.scalar_one_or_none()
    if instance and instance.template:
        return _strategy_instance_to_record(instance)
    if instance and not instance.template:
        logger.warning("strategy_instance_missing_template", id=strategy_id, template_id=instance.template_id)

    # Fallback: legacy Strategy table (match by user_id OR user_id is NULL for seed data)
    legacy_result = await session.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            (Strategy.user_id == user_id) | (Strategy.user_id.is_(None)),
        )
    )
    legacy = legacy_result.scalar_one_or_none()
    if legacy:
        return _legacy_strategy_to_record(legacy)

    logger.warning("strategy_not_found", strategy_id=strategy_id, user_id=user_id)
    return None


@router.post("/generate-strategy")
async def generate_strategy(request: Request, body: GenerateStrategyRequest):
    """Generate a structured strategy from a plain-language prompt."""
    user_id = request.state.user_id
    service = AIStrategyService()
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    try:
        result = await service.generate(prompt)
        logger.info("strategy_generated", user_id=user_id, prompt_len=len(prompt))
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/create-bot")
async def create_bot(request: Request, body: CreateBotRequest):
    """Create a trading bot from a strategy spec."""
    user_id = request.state.user_id
    bot_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    bot_name = _clean_name(body.name)
    if not bot_name:
        raise HTTPException(status_code=400, detail="Bot name is required")

    try:
        config = _ensure_valid_bot_config(body.strategy_json, error_detail="Bot configuration is invalid")
    except HTTPException as exc:
        logger.warning("bot_create_rejected", user_id=user_id, name=bot_name, detail=exc.detail)
        raise

    learning = config.get("learning") or {}

    async with get_session() as session:
        bot = CerberusBot(
            id=bot_id,
            user_id=user_id,
            name=bot_name,
            status=BotStatus.DRAFT,
            learning_enabled=bool(learning.get("enabled", True)),
            learning_status_json={
                "status": "monitoring" if learning.get("enabled", True) else "disabled",
                "summary": learning.get("last_summary", "Bot created and waiting for deployment."),
                "metrics": {},
                "featureSignals": config.get("feature_signals", []),
                "parameterAdjustments": [],
                "methods": learning.get("methods", []),
            },
        )
        version = CerberusBotVersion(
            id=version_id,
            bot_id=bot_id,
            version_number=1,
            config_json=config,
            diff_summary="Initial version",
            created_by="user",
        )
        bot.current_version_id = version_id
        session.add(bot)
        session.add(version)

    logger.info("bot_created", bot_id=bot_id, user_id=user_id, name=bot_name)
    return {
        "bot_id": bot_id,
        "name": bot_name,
        "status": "draft",
        "version": 1,
    }


@router.get("/bots")
async def list_bots(request: Request):
    """List all bots for the current user with learning summaries."""
    user_id = request.state.user_id

    async with get_session() as session:
        result = await session.execute(
            select(CerberusBot)
            .where(CerberusBot.user_id == user_id)
            .order_by(CerberusBot.created_at.desc())
        )
        bots = result.scalars().all()

        bot_list: list[dict[str, Any]] = []
        for bot in bots:
            version = None
            config: dict[str, Any] | None = None
            if bot.current_version_id:
                version_result = await session.execute(
                    select(CerberusBotVersion).where(CerberusBotVersion.id == bot.current_version_id)
                )
                version = version_result.scalar_one_or_none()
                config = normalize_bot_config(version.config_json if version else {})
            metrics = await _fetch_bot_metrics(session, bot.id, config or {}, user_id=user_id)
            bot_list.append(
                {
                    "id": bot.id,
                    "name": bot.name,
                    "status": bot.status.value if bot.status else "draft",
                    "createdAt": bot.created_at.isoformat() if bot.created_at else None,
                    "config": config,
                    "strategyId": (config or {}).get("strategy_id"),
                    "strategyType": (config or {}).get("strategy_type", "manual"),
                    "overview": (config or {}).get("overview") or (config or {}).get("description") or "",
                    "primarySymbol": ((config or {}).get("symbols") or ["SPY"])[0],
                    "performance": metrics,
                    "learningStatus": _learning_status(bot, config or {}, metrics),
                    "currentVersion": _version_to_dict(version) if version else None,
                }
            )

    return bot_list


@router.post("/bots/from-strategy")
async def create_bot_from_strategy(request: Request, body: DeployFromStrategyRequest):
    """Create and immediately deploy a bot from a saved strategy."""
    user_id = request.state.user_id

    async with get_session() as session:
        strategy_record = await _load_strategy_record(session, user_id, body.strategy_id)
        if not strategy_record:
            raise HTTPException(status_code=404, detail="Strategy not found")

        bot_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        requested_name = _clean_name(body.name)
        strategy_name = _clean_name(strategy_record.get("name"))
        bot_name = requested_name or strategy_name
        if not bot_name:
            raise HTTPException(status_code=400, detail="Bot name is required")

        try:
            config = _ensure_valid_bot_config(
                strategy_record_to_bot_config(strategy_record),
                error_detail="Saved strategy cannot be deployed",
            )
        except HTTPException as exc:
            logger.warning(
                "bot_deploy_from_strategy_rejected",
                strategy_id=body.strategy_id,
                user_id=user_id,
                detail=exc.detail,
            )
            raise

        bot = CerberusBot(
            id=bot_id,
            user_id=user_id,
            name=bot_name,
            status=BotStatus.RUNNING,
            learning_enabled=bool(config.get("learning", {}).get("enabled", False)),
            learning_status_json={
                "status": "learning" if config.get("learning", {}).get("enabled", False) else "monitoring",
                "summary": config.get("learning", {}).get("last_summary", "Bot deployed and monitoring live performance."),
                "metrics": {},
                "featureSignals": config.get("feature_signals", []),
                "parameterAdjustments": [],
                "methods": config.get("learning", {}).get("methods", []),
            },
        )
        version = CerberusBotVersion(
            id=version_id,
            bot_id=bot_id,
            version_number=1,
            config_json=config,
            diff_summary="Initial deployment from saved strategy",
            created_by="system",
        )
        bot.current_version_id = version_id
        session.add(bot)
        session.add(version)

    logger.info("bot_deployed_from_strategy", bot_id=bot_id, strategy_id=body.strategy_id)
    return {
        "bot_id": bot_id,
        "name": bot_name,
        "status": "running",
        "strategy_id": body.strategy_id,
    }


@router.get("/bots/{bot_id}")
async def get_bot_detail(bot_id: str, request: Request):
    """Get a full bot detail bundle for visualization and learning status."""
    user_id = request.state.user_id
    settings = get_settings()

    async with get_session() as session:
        result = await session.execute(
            select(CerberusBot)
            .where(CerberusBot.id == bot_id, CerberusBot.user_id == user_id)
        )
        bot = result.scalar_one_or_none()
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        version_result = await session.execute(
            select(CerberusBotVersion)
            .where(CerberusBotVersion.bot_id == bot.id)
            .order_by(CerberusBotVersion.version_number.desc())
        )
        versions = list(version_result.scalars().all())
        current_version = next((version for version in versions if version.id == bot.current_version_id), versions[0] if versions else None)
        config = normalize_bot_config(current_version.config_json if current_version else {})

        trade_result = await session.execute(
            select(CerberusTrade)
            .where(CerberusTrade.bot_id == bot.id, CerberusTrade.user_id == user_id)
            .order_by(CerberusTrade.created_at.desc())
        )
        trades = list(trade_result.scalars().all())

        optimization_result = await session.execute(
            select(CerberusBotOptimizationRun)
            .where(CerberusBotOptimizationRun.bot_id == bot.id)
            .order_by(CerberusBotOptimizationRun.created_at.desc())
            .limit(20)
        )
        optimization_runs = list(optimization_result.scalars().all())

        metrics = calculate_trade_metrics(trades, config)
        equity_curve = build_equity_curve_from_trades(trades, settings.initial_capital)

    return {
        "id": bot.id,
        "name": bot.name,
        "status": bot.status.value if bot.status else "draft",
        "createdAt": bot.created_at.isoformat() if bot.created_at else None,
        "currentVersion": _version_to_dict(current_version) if current_version else None,
        "config": config,
        "strategyId": config.get("strategy_id"),
        "strategyType": config.get("strategy_type", "manual"),
        "overview": config.get("overview") or config.get("description") or "",
        "sourcePrompt": config.get("source_prompt"),
        "primarySymbol": (config.get("symbols") or ["SPY"])[0],
        "performance": metrics,
        "learningStatus": _learning_status(bot, config, metrics),
        "equityCurve": equity_curve,
        "trades": [_serialize_trade(trade, config) for trade in trades[:50]],
        "versionHistory": [_version_to_dict(version) for version in versions],
        "optimizationHistory": [_optimization_run_to_dict(run) for run in optimization_runs],
    }


@router.post("/bots/{bot_id}/deploy")
async def deploy_bot(bot_id: str, request: Request):
    """Deploy (start running) a bot."""
    user_id = request.state.user_id
    async with get_session() as session:
        result = await session.execute(
            select(CerberusBot).where(CerberusBot.id == bot_id, CerberusBot.user_id == user_id)
        )
        bot = result.scalar_one_or_none()
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        if not bot.current_version_id:
            logger.warning("bot_deploy_missing_version", bot_id=bot_id, user_id=user_id)
            raise HTTPException(status_code=400, detail="Bot has no deployable version")

        version_result = await session.execute(
            select(CerberusBotVersion).where(
                CerberusBotVersion.id == bot.current_version_id,
                CerberusBotVersion.bot_id == bot.id,
            )
        )
        version = version_result.scalar_one_or_none()
        if not version:
            logger.warning(
                "bot_deploy_version_not_found",
                bot_id=bot_id,
                user_id=user_id,
                version_id=bot.current_version_id,
            )
            raise HTTPException(status_code=400, detail="Bot has no deployable version")
        if version.backtest_required:
            raise HTTPException(
                status_code=409,
                detail="Bot version is awaiting backtest validation before deployment",
            )

        try:
            config = _ensure_valid_bot_config(version.config_json)
        except HTTPException as exc:
            logger.warning("bot_deploy_rejected", bot_id=bot_id, user_id=user_id, detail=exc.detail)
            raise

        version.config_json = config
        bot.learning_enabled = bool((config.get("learning") or {}).get("enabled", False))
        bot.status = BotStatus.RUNNING

    logger.info("bot_deployed", bot_id=bot_id, user_id=user_id)
    return {"bot_id": bot_id, "status": "running"}


@router.post("/bots/{bot_id}/stop")
async def stop_bot(bot_id: str, request: Request):
    """Stop a running bot."""
    user_id = request.state.user_id
    async with get_session() as session:
        result = await session.execute(
            select(CerberusBot).where(CerberusBot.id == bot_id, CerberusBot.user_id == user_id)
        )
        bot = result.scalar_one_or_none()
        if not bot:
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
        return await service.confirm_proposal(body.proposalId, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/execute-trade")
async def execute_trade(request: Request, body: ExecuteTradeRequest):
    """Execute a confirmed trade."""
    from services.ai_core.proposals.confirmation_service import ConfirmationService

    user_id = request.state.user_id
    service = ConfirmationService()

    try:
        return await service.execute_confirmed(
            body.proposalId,
            body.confirmationToken,
            user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/proposals")
async def list_proposals(request: Request, status: Optional[str] = None, limit: int = 20):
    """List trade proposals for the current user."""
    from db.cerberus_models import CerberusTradeProposal

    user_id = request.state.user_id
    async with get_session() as session:
        stmt = select(CerberusTradeProposal).where(CerberusTradeProposal.user_id == user_id)
        if status:
            stmt = stmt.where(CerberusTradeProposal.status == status)
        stmt = stmt.order_by(CerberusTradeProposal.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        proposals = result.scalars().all()

    return [
        {
            "id": proposal.id,
            "threadId": proposal.thread_id,
            "proposalJson": proposal.proposal_json,
            "riskJson": proposal.risk_json,
            "explanationMd": proposal.explanation_md,
            "status": proposal.status.value if proposal.status else None,
            "expiresAt": proposal.expires_at.isoformat() if proposal.expires_at else None,
            "createdAt": proposal.created_at.isoformat() if proposal.created_at else None,
        }
        for proposal in proposals
    ]


@router.get("/bots/{bot_id}/activity")
async def get_bot_activity(bot_id: str, request: Request, limit: int = 50):
    """Get recent trades made by a bot."""
    user_id = request.state.user_id
    async with get_session() as session:
        bot_result = await session.execute(
            select(CerberusBot, CerberusBotVersion)
            .outerjoin(CerberusBotVersion, CerberusBot.current_version_id == CerberusBotVersion.id)
            .where(CerberusBot.id == bot_id, CerberusBot.user_id == user_id)
        )
        bot_row = bot_result.first()
        if not bot_row:
            raise HTTPException(status_code=404, detail="Bot not found")
        config = bot_row[1].config_json if bot_row[1] else {}

        result = await session.execute(
            select(CerberusTrade)
            .where(CerberusTrade.bot_id == bot_id, CerberusTrade.user_id == user_id)
            .order_by(CerberusTrade.created_at.desc())
            .limit(limit)
        )
        trades = result.scalars().all()

    return [_serialize_trade(trade, config) for trade in trades]


async def _fetch_bot_metrics(session, bot_id: str, config: dict[str, Any], user_id: int | None = None) -> dict[str, Any]:
    stmt = select(CerberusTrade).where(CerberusTrade.bot_id == bot_id)
    if user_id is not None:
        stmt = stmt.where(CerberusTrade.user_id == user_id)
    result = await session.execute(stmt.order_by(CerberusTrade.created_at.asc()))
    trades = list(result.scalars().all())
    return calculate_trade_metrics(trades, config)

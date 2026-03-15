"""Autonomous bot learning loop and performance helpers."""

from __future__ import annotations

import asyncio
import math
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev
from typing import Any
from uuid import uuid4

import structlog
from pydantic import ValidationError
from sqlalchemy import func, select

from config.settings import get_settings
from db.cerberus_models import (
    CerberusBot,
    CerberusBotOptimizationRun,
    CerberusBotVersion,
    CerberusTrade,
)
from db.database import get_session
from services.ai_strategy_service import (
    GeneratedStrategySpec,
    compile_strategy_payload,
    default_learning_plan,
    derive_feature_signals,
)

logger = structlog.get_logger(__name__)


def _normalize_fractional_pct(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return round(numeric / 100, 4) if numeric > 1 else numeric


def _compile_legacy_ai_strategy(config: dict[str, Any]) -> dict[str, Any] | None:
    if not config.get("entryConditions"):
        return None

    raw_spec = deepcopy(config)
    raw_spec.setdefault("strategyType", raw_spec.get("strategy_type") or "ai_generated")
    raw_spec.setdefault("sourcePrompt", raw_spec.get("source_prompt") or "")
    raw_spec.setdefault("overview", raw_spec.get("overview") or raw_spec.get("description") or "")
    raw_spec.setdefault("featureSignals", raw_spec.get("feature_signals") or [])
    raw_spec.setdefault("symbols", raw_spec.get("symbols") or ["SPY"])

    try:
        spec = GeneratedStrategySpec.model_validate(raw_spec)
    except ValidationError:
        return None

    compiled = compile_strategy_payload(spec)
    if "learning" in config:
        compiled["learning"] = deepcopy(config["learning"])
    return compiled


def normalize_bot_config(config: dict[str, Any] | None) -> dict[str, Any]:
    normalized = deepcopy(config or {})
    compiled = _compile_legacy_ai_strategy(normalized)
    if compiled:
        normalized = compiled

    if "conditionGroups" in normalized and "condition_groups" not in normalized:
        normalized["condition_groups"] = deepcopy(normalized["conditionGroups"])
    if "strategyType" in normalized and "strategy_type" not in normalized:
        normalized["strategy_type"] = normalized["strategyType"]
    if "sourcePrompt" in normalized and "source_prompt" not in normalized:
        normalized["source_prompt"] = normalized["sourcePrompt"]
    if "aiContext" in normalized and "ai_context" not in normalized:
        normalized["ai_context"] = deepcopy(normalized["aiContext"])
    if "featureSignals" in normalized and "feature_signals" not in normalized:
        normalized["feature_signals"] = deepcopy(normalized["featureSignals"])

    if "stopLossPct" in normalized and "stop_loss_pct" not in normalized:
        normalized["stop_loss_pct"] = _normalize_fractional_pct(normalized["stopLossPct"])
    elif "stopLoss" in normalized and "stop_loss_pct" not in normalized:
        normalized["stop_loss_pct"] = _normalize_fractional_pct(normalized["stopLoss"])

    if "takeProfitPct" in normalized and "take_profit_pct" not in normalized:
        normalized["take_profit_pct"] = _normalize_fractional_pct(normalized["takeProfitPct"])
    elif "takeProfit" in normalized and "take_profit_pct" not in normalized:
        normalized["take_profit_pct"] = _normalize_fractional_pct(normalized["takeProfit"])

    if "positionPct" in normalized and "position_size_pct" not in normalized:
        normalized["position_size_pct"] = _normalize_fractional_pct(normalized["positionPct"])
    elif "positionSize" in normalized and "position_size_pct" not in normalized:
        normalized["position_size_pct"] = _normalize_fractional_pct(normalized["positionSize"])

    if not normalized.get("conditions") and normalized.get("condition_groups"):
        normalized["conditions"] = [
            deepcopy(condition)
            for group in normalized["condition_groups"]
            for condition in group.get("conditions", [])
        ]

    normalized.setdefault("conditions", [])
    normalized.setdefault("condition_groups", [])
    normalized.setdefault("symbols", ["SPY"])
    normalized.setdefault(
        "exit_conditions",
        deepcopy((normalized.get("ai_context") or {}).get("exit_conditions") or []),
    )
    normalized.setdefault("strategy_type", "manual")
    normalized.setdefault("feature_signals", derive_feature_signals(normalized.get("conditions") or []))
    normalized.setdefault("learning", default_learning_plan(normalized.get("strategy_type", "manual")))
    return normalized


def calculate_trade_metrics(trades: list[CerberusTrade], config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = normalize_bot_config(config)
    returns = [float(t.return_pct) for t in trades if t.return_pct is not None]
    pnl_series = [float(t.net_pnl or 0) for t in trades]
    trade_count = len(trades)
    wins = sum(1 for t in trades if (t.net_pnl or 0) > 0)
    total_net_pnl = sum(pnl_series)
    total_gross_pnl = sum(float(t.gross_pnl or 0) for t in trades)
    total_volume = sum(float((t.entry_price or 0) * t.quantity) for t in trades)

    sharpe = 0.0
    if len(returns) >= 2:
        deviation = pstdev(returns)
        if deviation > 1e-9:
            sharpe = mean(returns) / deviation * math.sqrt(min(len(returns), 252))

    max_drawdown = 0.0
    if returns:
        equity = 1.0
        peak = 1.0
        for trade_return in returns:
            equity *= 1 + trade_return
            peak = max(peak, equity)
            if peak > 0:
                max_drawdown = max(max_drawdown, (peak - equity) / peak)
    else:
        equity = 0.0
        peak = 0.0
        for pnl in pnl_series:
            equity += pnl
            peak = max(peak, equity)
            if peak > 0:
                max_drawdown = max(max_drawdown, (peak - equity) / peak)

    return {
        "trade_count": trade_count,
        "win_rate": round(wins / trade_count, 4) if trade_count else 0.0,
        "avg_return_pct": round(mean(returns), 4) if returns else 0.0,
        "total_net_pnl": round(total_net_pnl, 2),
        "total_gross_pnl": round(total_gross_pnl, 2),
        "total_volume": round(total_volume, 2),
        "sharpe_ratio": round(sharpe, 4),
        "max_drawdown": round(max_drawdown, 4),
        "feature_signals": config.get("feature_signals") or derive_feature_signals(config.get("conditions") or []),
    }


def build_equity_curve_from_trades(
    trades: list[CerberusTrade],
    initial_capital: float,
) -> list[dict[str, Any]]:
    if not trades:
        return []

    ordered = sorted(
        trades,
        key=lambda trade: trade.exit_ts or trade.entry_ts or trade.created_at or datetime.min,
    )
    equity = initial_capital
    curve: list[dict[str, Any]] = []
    for trade in ordered:
        equity += float(trade.net_pnl or 0)
        timestamp = trade.exit_ts or trade.entry_ts or trade.created_at or datetime.now(timezone.utc)
        curve.append(
            {
                "date": timestamp.date().isoformat(),
                "value": round(equity, 2),
            }
        )
    return curve


class StrategyLearningEngine:
    """Periodically evaluates bot performance and proposes parameter updates."""

    def __init__(self):
        self._settings = get_settings()
        self._running = False
        self._sleep_seconds = max(300, self._settings.strategy_learning_interval_seconds)
        self._min_trades = max(1, self._settings.strategy_learning_min_trades)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        logger.info("strategy_learning_engine_started")
        while self._running:
            try:
                await self._optimize_due_bots()
            except Exception as exc:  # pragma: no cover - defensive background loop
                logger.error("strategy_learning_cycle_failed", error=str(exc))
            await asyncio.sleep(self._sleep_seconds)

    async def stop(self) -> None:
        self._running = False
        logger.info("strategy_learning_engine_stopped")

    async def _optimize_due_bots(self) -> None:
        async with get_session() as session:
            result = await session.execute(
                select(CerberusBot.id)
                .where(CerberusBot.learning_enabled == True)  # noqa: E712
                .order_by(CerberusBot.updated_at.asc())
            )
            bot_ids = [row[0] for row in result.all()]

        for bot_id in bot_ids:
            await self.optimize_bot(bot_id)

    async def optimize_bot(self, bot_id: str) -> dict[str, Any] | None:
        async with get_session() as session:
            result = await session.execute(
                select(CerberusBot, CerberusBotVersion)
                .join(CerberusBotVersion, CerberusBot.current_version_id == CerberusBotVersion.id, isouter=True)
                .where(CerberusBot.id == bot_id)
            )
            row = result.first()
            if not row:
                return None

            bot, version = row
            if version is None:
                return None

            config = normalize_bot_config(version.config_json)
            learning = deepcopy(config.get("learning") or default_learning_plan(config.get("strategy_type", "manual")))
            if not learning.get("enabled", False):
                return None

            cadence_minutes = int(learning.get("cadence_minutes", 240) or 240)
            last_opt = bot.last_optimization_at
            if last_opt and datetime.utcnow() - last_opt < timedelta(minutes=cadence_minutes):
                return None

            trades_result = await session.execute(
                select(CerberusTrade)
                .where(CerberusTrade.bot_id == bot.id)
                .order_by(CerberusTrade.created_at.desc())
                .limit(500)
            )
            trades = list(reversed(trades_result.scalars().all()))
            metrics = calculate_trade_metrics(trades, config)

            adjustments, method, summary = self._propose_adjustments(config, metrics)
            updated_config = deepcopy(config)
            new_version_id: str | None = None

            if adjustments:
                updated_config = self._apply_adjustments(updated_config, adjustments)
                updated_config.setdefault("learning", {})
                updated_config["learning"].update(
                    {
                        "enabled": True,
                        "cadence_minutes": cadence_minutes,
                        "methods": learning.get("methods", []),
                        "goals": learning.get("goals", []),
                        "status": "optimizing",
                        "last_optimization_at": datetime.now(timezone.utc).isoformat(),
                        "last_summary": summary,
                        "parameter_adjustments": adjustments,
                    }
                )

                next_version_number = await session.scalar(
                    select(func.coalesce(func.max(CerberusBotVersion.version_number), 0) + 1).where(
                        CerberusBotVersion.bot_id == bot.id
                    )
                )
                new_version_id = str(uuid4())
                session.add(
                    CerberusBotVersion(
                        id=new_version_id,
                        bot_id=bot.id,
                        version_number=int(next_version_number or 1),
                        config_json=updated_config,
                        diff_summary=summary,
                        created_by="learning_engine",
                        backtest_required=True,
                    )
                )

            bot.last_optimization_at = datetime.utcnow()
            bot.learning_status_json = {
                "status": "awaiting_backtest" if adjustments else "monitoring",
                "lastOptimizationAt": bot.last_optimization_at.isoformat(),
                "nextOptimizationAt": (bot.last_optimization_at + timedelta(minutes=cadence_minutes)).isoformat(),
                "method": method,
                "summary": summary,
                "metrics": metrics,
                "featureSignals": metrics["feature_signals"],
                "parameterAdjustments": adjustments,
                "methods": learning.get("methods", []),
                "stagedVersionId": new_version_id,
            }

            session.add(
                CerberusBotOptimizationRun(
                    id=str(uuid4()),
                    bot_id=bot.id,
                    source_version_id=version.id,
                    result_version_id=new_version_id,
                    method=method,
                    status="awaiting_backtest" if adjustments else "monitoring",
                    metrics_json=metrics,
                    adjustments_json={"parameter_adjustments": adjustments},
                    summary=summary,
                )
            )

            logger.info(
                "bot_optimized",
                bot_id=bot.id,
                method=method,
                trade_count=metrics["trade_count"],
                adjustments=len(adjustments),
            )

            return {
                "bot_id": bot.id,
                "method": method,
                "summary": summary,
                "adjustments": adjustments,
                "metrics": metrics,
            }

    def _propose_adjustments(
        self,
        config: dict[str, Any],
        metrics: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], str, str]:
        if metrics["trade_count"] < self._min_trades:
            return (
                [],
                "walk_forward_backtesting",
                "Monitoring bot until enough closed trades accumulate for optimization.",
            )

        adjustments: list[dict[str, Any]] = []
        stop_loss = float(config.get("stop_loss_pct", 0.02) or 0.02)
        take_profit = float(config.get("take_profit_pct", 0.05) or 0.05)
        position_size = float(config.get("position_size_pct", 0.1) or 0.1)

        if metrics["max_drawdown"] >= 0.12 or metrics["win_rate"] < 0.45:
            method = "reinforcement_learning"
            new_stop = max(stop_loss * 0.9, 0.005)
            new_position = max(position_size * 0.9, 0.02)
            adjustments.extend(
                [
                    {
                        "path": "stop_loss_pct",
                        "old": round(stop_loss, 4),
                        "new": round(new_stop, 4),
                        "reason": "Tighten downside risk after weak recent performance.",
                    },
                    {
                        "path": "position_size_pct",
                        "old": round(position_size, 4),
                        "new": round(new_position, 4),
                        "reason": "Reduce capital at risk while the bot re-stabilizes.",
                    },
                ]
            )
            summary = "Reinforcement-style risk reduction applied after elevated drawdown or low hit rate."
        elif metrics["sharpe_ratio"] >= 1.1 and metrics["win_rate"] >= 0.55:
            method = "bayesian_tuning"
            new_take = min(take_profit * 1.08, 0.25)
            new_position = min(position_size * 1.05, 0.25)
            adjustments.extend(
                [
                    {
                        "path": "take_profit_pct",
                        "old": round(take_profit, 4),
                        "new": round(new_take, 4),
                        "reason": "Let profitable trades run further when risk-adjusted returns are strong.",
                    },
                    {
                        "path": "position_size_pct",
                        "old": round(position_size, 4),
                        "new": round(new_position, 4),
                        "reason": "Scale slightly into a favorable edge while keeping sizing capped.",
                    },
                ]
            )
            summary = "Bayesian-style parameter tuning expanded upside targets after strong recent risk-adjusted performance."
        else:
            method = "parameter_optimization"
            rsi_adjustment = self._find_condition_adjustment(config.get("conditions") or [])
            if rsi_adjustment:
                adjustments.append(rsi_adjustment)
            summary = (
                "Parameter optimization refreshed signal thresholds using recent trade outcomes."
                if adjustments
                else "Walk-forward review completed with no material parameter changes."
            )
            if not adjustments:
                method = "walk_forward_backtesting"

        deduped = [adjustment for adjustment in adjustments if adjustment["old"] != adjustment["new"]]
        return deduped, method, summary

    def _find_condition_adjustment(self, conditions: list[dict[str, Any]]) -> dict[str, Any] | None:
        for index, condition in enumerate(conditions):
            if str(condition.get("indicator", "")).lower() != "rsi":
                continue

            operator = condition.get("operator", ">")
            old_value = float(condition.get("value", 50) or 50)
            if operator in {">", ">="}:
                new_value = max(45.0, min(75.0, old_value - 2))
            else:
                new_value = max(20.0, min(55.0, old_value + 2))
            return {
                "path": f"conditions[{index}].value",
                "old": round(old_value, 2),
                "new": round(new_value, 2),
                "reason": "Adjust RSI trigger to reduce lag while preserving the existing strategy profile.",
            }
        return None

    def _apply_adjustments(self, config: dict[str, Any], adjustments: list[dict[str, Any]]) -> dict[str, Any]:
        updated = deepcopy(config)
        for adjustment in adjustments:
            path = adjustment["path"]
            if path == "stop_loss_pct":
                updated["stop_loss_pct"] = adjustment["new"]
            elif path == "take_profit_pct":
                updated["take_profit_pct"] = adjustment["new"]
            elif path == "position_size_pct":
                updated["position_size_pct"] = adjustment["new"]
            elif path.startswith("conditions[") and path.endswith("].value"):
                index = int(path.split("[", 1)[1].split("]", 1)[0])
                if index < len(updated.get("conditions") or []):
                    updated["conditions"][index]["value"] = adjustment["new"]

        updated.setdefault("feature_signals", derive_feature_signals(updated.get("conditions") or []))
        return updated

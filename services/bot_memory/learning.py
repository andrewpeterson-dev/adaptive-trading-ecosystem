"""Autonomous adaptation — analyzes trade patterns and suggests parameter changes."""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import structlog
from sqlalchemy import select

from db.database import get_session
from db.cerberus_models import BotAdaptation, BotTradeJournal, CerberusBot, CerberusBotVersion

logger = structlog.get_logger(__name__)


def is_auto_appliable(adaptation_type: str, old_value: dict, new_value: dict) -> bool:
    """Check if an adaptation can be auto-applied (within 50%-150% of original)."""
    auto_types = {"stop_loss", "take_profit", "position_size", "time_filter", "regime_behavior"}
    if adaptation_type not in auto_types:
        return False

    # Check numeric values are within 50%-150% range
    for key in new_value:
        if key in old_value:
            old_v = old_value[key]
            new_v = new_value[key]
            if isinstance(old_v, (int, float)) and isinstance(new_v, (int, float)) and old_v != 0:
                ratio = new_v / old_v
                if ratio < 0.5 or ratio > 1.5:
                    return False
    return True


async def run_adaptation_review(bot_id: str) -> list[BotAdaptation]:
    """Run adaptation review for a bot. Called as Celery task."""
    # Get recent trades
    async with get_session() as session:
        result = await session.execute(
            select(BotTradeJournal).where(BotTradeJournal.bot_id == bot_id)
            .order_by(BotTradeJournal.created_at.desc()).limit(20)
        )
        recent_trades = result.scalars().all()

    if not recent_trades:
        return []

    # Get bot config
    async with get_session() as session:
        result = await session.execute(
            select(CerberusBot).where(CerberusBot.id == bot_id)
        )
        bot = result.scalar_one_or_none()
        if not bot or not bot.current_version_id:
            return []

        result = await session.execute(
            select(CerberusBotVersion).where(CerberusBotVersion.id == bot.current_version_id)
        )
        version = result.scalar_one_or_none()
        if not version:
            return []

    config = version.config_json or {}

    # Analyze patterns
    adaptations = await _analyze_patterns(bot_id, recent_trades, config, bot)

    # Store and optionally apply
    stored = []
    for adaptation in adaptations:
        auto = is_auto_appliable(adaptation["type"], adaptation["old"], adaptation["new"])

        record = BotAdaptation(
            id=str(uuid.uuid4()),
            bot_id=bot_id,
            adaptation_type=adaptation["type"],
            old_value=adaptation["old"],
            new_value=adaptation["new"],
            reasoning=adaptation["reasoning"],
            confidence=adaptation.get("confidence", 0.5),
            auto_applied=auto,
            created_at=datetime.utcnow(),
        )

        async with get_session() as session:
            session.add(record)

        if auto:
            await _apply_adaptation(bot_id, adaptation)

        stored.append(record)

    return stored


async def _analyze_patterns(
    bot_id: str, trades: list[BotTradeJournal], config: dict, bot: CerberusBot
) -> list[dict]:
    """Use LLM to identify patterns and suggest adaptations."""
    adaptations = []

    try:
        from services.ai_core.model_router import ModelRouter

        trade_summaries = []
        for t in trades:
            trade_summaries.append({
                "symbol": t.symbol,
                "side": t.side,
                "pnl_pct": t.pnl_pct,
                "regime": t.regime_at_entry,
                "vix": t.vix_at_entry,
                "ai_confidence": t.ai_confidence_at_entry,
                "hold_duration_s": t.hold_duration_seconds,
            })

        prompt = f"""Analyze these {len(trades)} recent trades for bot "{bot.name}" and suggest parameter adjustments.

Current config: {json.dumps(config, default=str)}

Recent trades:
{json.dumps(trade_summaries, default=str)}

Return a JSON array of adjustments (empty array if none needed):
[{{
    "type": "stop_loss" | "take_profit" | "position_size" | "time_filter" | "indicator_param" | "regime_behavior",
    "old": {{"param_name": old_value}},
    "new": {{"param_name": new_value}},
    "reasoning": "why this change helps",
    "confidence": 0.0-1.0
}}]

Be conservative. Only suggest changes with clear evidence from the trade data. With fewer than 5 trades, return []."""

        router = ModelRouter()
        response = await router.generate(
            model="gpt-4.1",
            system_prompt="You are a quantitative trading analyst reviewing bot performance and suggesting parameter optimizations. Return only valid JSON.",
            user_prompt=prompt,
            temperature=0.3,
            max_tokens=1000,
            user_id=bot.user_id,
        )

        text = response if isinstance(response, str) else response.get("content", "")
        import re
        json_match = re.search(r'\[.*\]', text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            if isinstance(parsed, list):
                adaptations = parsed

    except Exception as e:
        logger.warning("adaptation_analysis_failed", bot_id=bot_id, error=str(e))

    return adaptations


async def _apply_adaptation(bot_id: str, adaptation: dict) -> None:
    """Apply an auto-appliable adaptation to the bot's config."""
    try:
        async with get_session() as session:
            result = await session.execute(
                select(CerberusBot).where(CerberusBot.id == bot_id)
            )
            bot = result.scalar_one_or_none()
            if not bot or not bot.current_version_id:
                return

            result = await session.execute(
                select(CerberusBotVersion).where(CerberusBotVersion.id == bot.current_version_id)
            )
            version = result.scalar_one_or_none()
            if not version:
                return

            config = dict(version.config_json or {})
            new_values = adaptation.get("new", {})
            for key, value in new_values.items():
                config[key] = value

            version.config_json = config

        logger.info("adaptation_applied", bot_id=bot_id, type=adaptation["type"])
    except Exception as e:
        logger.error("adaptation_apply_failed", bot_id=bot_id, error=str(e))

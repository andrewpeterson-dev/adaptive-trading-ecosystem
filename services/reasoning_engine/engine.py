"""Reasoning Engine — evaluates trade signals with AI + safety rules."""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import structlog
from sqlalchemy import select, func, and_

from db.database import get_session
from db.cerberus_models import (
    MarketEvent, TradeDecision, BotRegimeStats, BotTradeJournal, CerberusBot,
)
from services.reasoning_engine.safety import (
    check_hard_blockers, check_soft_guardrails, classify_vix, SafetyResult,
)
from services.reasoning_engine.prompts import TRADE_DECISION_SYSTEM, build_trade_decision_prompt

logger = structlog.get_logger(__name__)


class ReasoningEngine:
    """Per-bot reasoning: safety checks + optional LLM evaluation."""

    async def evaluate(
        self,
        *,
        bot: CerberusBot,
        symbol: str,
        signal: str,
        strategy_config: dict,
        vix: float | None = None,
        portfolio_exposure: float = 0.0,
        daily_pnl_pct: float = 0.0,
    ) -> TradeDecision:
        override_level = "soft"
        if bot.current_version_id:
            async with get_session() as session:
                from db.cerberus_models import CerberusBotVersion
                result = await session.execute(
                    select(CerberusBotVersion).where(CerberusBotVersion.id == bot.current_version_id)
                )
                version = result.scalar_one_or_none()
                if version:
                    override_level = version.override_level or "soft"

        # Fetch active events
        events_raw = await self._get_active_events(bot.user_id, symbol)
        events_dicts = [
            {
                "id": e.id, "event_type": e.event_type, "impact": e.impact,
                "symbols": e.symbols or [], "sectors": e.sectors or [],
                "headline": e.headline, "source": e.source,
                "raw_data": e.raw_data or {},
            }
            for e in events_raw
        ]

        # Hard blockers
        hard = check_hard_blockers(
            vix=vix, events=events_dicts, symbol=symbol,
            portfolio_exposure=portfolio_exposure, daily_pnl_pct=daily_pnl_pct,
        )
        if hard.blocked:
            return await self._build_result(
                bot_id=bot.id, symbol=symbol, signal=signal, vix=vix,
                decision="PAUSE_BOT" if daily_pnl_pct < -5.0 else "DELAY_TRADE",
                confidence=0.0, reasoning="; ".join(hard.reasons),
                size_adjustment=0.0, delay_seconds=300,
                events_considered=[e["id"] for e in events_dicts[:20]],
                model_used="safety_rules",
            )

        # Try LLM reasoning
        llm_result = await self._try_llm_reasoning(
            bot=bot, symbol=symbol, signal=signal,
            strategy_config=strategy_config, events_dicts=events_dicts,
            vix=vix,
        )

        # Soft guardrails
        soft = check_soft_guardrails(
            vix=vix, events=events_dicts, symbol=symbol,
            ai_confidence=llm_result.get("confidence", 0.7),
            override_level=override_level,
        )

        # Merge LLM + safety
        return await self._merge_reasoning(
            bot_id=bot.id, symbol=symbol, signal=signal, vix=vix,
            llm_result=llm_result, soft=soft,
            events_considered=[e["id"] for e in events_dicts[:20]],
        )

    async def _get_active_events(self, user_id: int, symbol: str) -> list[MarketEvent]:
        now = datetime.utcnow()
        async with get_session() as session:
            result = await session.execute(
                select(MarketEvent).where(
                    and_(
                        MarketEvent.detected_at >= now - __import__('datetime').timedelta(hours=4),
                        (MarketEvent.expires_at.is_(None)) | (MarketEvent.expires_at > now),
                        (MarketEvent.user_id.is_(None)) | (MarketEvent.user_id == user_id),
                    )
                ).order_by(MarketEvent.detected_at.desc()).limit(50)
            )
            return list(result.scalars().all())

    async def _try_llm_reasoning(
        self, *, bot, symbol, signal, strategy_config, events_dicts, vix,
    ) -> dict:
        """Call LLM for reasoning. Falls back to defaults on failure."""
        try:
            from services.ai_core.model_router import ModelRouter

            # Check for bot-level model override
            model_config = bot.reasoning_model_config or {}
            model_name = model_config.get("model")

            # Determine model based on event severity
            if not model_name:
                has_high_impact = any(e.get("impact") == "HIGH" for e in events_dicts)
                model_name = "gpt-5.4" if has_high_impact else "gpt-4.1"

            # Get regime stats
            regime_stats = None
            async with get_session() as session:
                result = await session.execute(
                    select(BotRegimeStats).where(BotRegimeStats.bot_id == bot.id)
                )
                stats = result.scalars().all()
                if stats:
                    regime_stats = {s.regime: {"win_rate": s.win_rate, "avg_pnl": s.avg_pnl, "trades": s.total_trades} for s in stats}

            # Get recent trades
            recent_trades = []
            async with get_session() as session:
                result = await session.execute(
                    select(BotTradeJournal).where(BotTradeJournal.bot_id == bot.id)
                    .order_by(BotTradeJournal.created_at.desc()).limit(5)
                )
                for t in result.scalars().all():
                    recent_trades.append({"symbol": t.symbol, "side": t.side, "pnl_pct": t.pnl_pct or 0})

            prompt = build_trade_decision_prompt(
                bot_name=bot.name, symbol=symbol, signal=signal,
                strategy_config=strategy_config, active_events=events_dicts,
                regime_stats=regime_stats, recent_trades=recent_trades,
                vix=vix, ai_thinking=strategy_config.get("aiThinking"),
            )

            router = ModelRouter()
            response = await router.generate(
                model=model_name,
                system_prompt=TRADE_DECISION_SYSTEM,
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=500,
                user_id=bot.user_id,
            )

            # Parse JSON from response
            text = response if isinstance(response, str) else response.get("content", "")
            # Try to extract JSON from the response
            import re
            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                return {
                    "decision": parsed.get("decision", "EXECUTE"),
                    "confidence": float(parsed.get("confidence", 0.7)),
                    "reasoning": parsed.get("reasoning", ""),
                    "size_adjustment": float(parsed.get("size_adjustment", 1.0)),
                    "delay_seconds": int(parsed.get("delay_seconds", 0)),
                    "model_used": model_name,
                }

            return {"decision": "EXECUTE", "confidence": 0.7, "reasoning": "LLM response unparseable — defaulting to execute", "size_adjustment": 1.0, "delay_seconds": 0, "model_used": "safety_rules_fallback"}

        except Exception as e:
            logger.warning("reasoning_llm_failed", error=str(e), bot_id=bot.id)
            return {
                "decision": "EXECUTE", "confidence": 0.5,
                "reasoning": f"LLM unavailable ({e}) — safety rules only",
                "size_adjustment": 1.0, "delay_seconds": 0,
                "model_used": "safety_rules_fallback",
            }

    async def _merge_reasoning(
        self, *, bot_id, symbol, signal, vix, llm_result, soft, events_considered,
    ) -> TradeDecision:
        decision = llm_result.get("decision", "EXECUTE")
        size_adj = llm_result.get("size_adjustment", 1.0)
        delay = llm_result.get("delay_seconds", 0)
        reasons = [llm_result.get("reasoning", "")]

        if soft.reduce_size < size_adj:
            size_adj = soft.reduce_size
        if soft.delay_seconds > delay:
            delay = soft.delay_seconds
        if soft.reasons:
            reasons.extend(soft.reasons)

        return await self._build_result(
            bot_id=bot_id, symbol=symbol, signal=signal, vix=vix,
            decision=decision, confidence=llm_result.get("confidence", 0.7),
            reasoning="; ".join(r for r in reasons if r),
            size_adjustment=size_adj, delay_seconds=delay,
            events_considered=events_considered,
            model_used=llm_result.get("model_used", "safety_rules"),
        )

    async def _build_result(
        self, *, bot_id, symbol, signal, vix, decision, confidence,
        reasoning, size_adjustment, delay_seconds, events_considered, model_used,
    ) -> TradeDecision:
        risk_level = "LOW"
        if vix and vix > 40:
            risk_level = "CRITICAL"
        elif vix and vix > 25:
            risk_level = "HIGH"
        elif vix and vix > 18:
            risk_level = "MEDIUM"

        td = TradeDecision(
            id=str(uuid.uuid4()),
            bot_id=bot_id,
            symbol=symbol,
            strategy_signal=signal,
            context_risk_level=risk_level,
            ai_confidence=confidence,
            decision=decision,
            reasoning=reasoning,
            size_adjustment=size_adjustment,
            delay_seconds=delay_seconds,
            events_considered=events_considered,
            model_used=model_used,
            created_at=datetime.utcnow(),
        )
        async with get_session() as session:
            session.add(td)
        return td

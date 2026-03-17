"""Reasoning Engine — evaluates trade signals with AI + safety rules."""
from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime

import structlog
from sqlalchemy import select, and_

from db.database import get_session
from db.cerberus_models import (
    MarketEvent, TradeDecision, BotRegimeStats, BotTradeJournal, CerberusBot,
)
from db.models import User
from services.ai_core.providers.base import ProviderMessage
from services.reasoning_engine.safety import (
    check_hard_blockers, check_soft_guardrails,
    get_drawdown_thresholds, compute_weekly_pnl_pct,
    is_strategy_type_blocked,
    DRAWDOWN_LEVEL_KILL_DAILY, DRAWDOWN_LEVEL_KILL_WEEKLY,
)
from services.reasoning_engine.prompts import TRADE_DECISION_SYSTEM, build_trade_decision_prompt

logger = structlog.get_logger(__name__)
_ALLOWED_DECISIONS = {"EXECUTE", "REDUCE_SIZE", "DELAY_TRADE", "PAUSE_BOT", "EXIT_POSITION"}

_sector_cache: dict[str, tuple[float, str]] = {}
_SECTOR_CACHE_TTL = 3600  # 1 hour - sectors don't change


class ReasoningEngine:
    """Per-bot reasoning: safety checks + optional LLM evaluation."""

    _TIER_LIMITS: dict[str, dict] = {
        "free": {"tier": "free", "reasoning_limit": 200, "bot_limit": 10, "use_platform_keys": False},
        "pro": {"tier": "pro", "reasoning_limit": 50, "bot_limit": 25, "use_platform_keys": True},
        "admin": {"tier": "admin", "reasoning_limit": 0, "bot_limit": 0, "use_platform_keys": True},
    }

    async def _check_tier_limits(self, user_id: int) -> dict:
        """Look up user subscription tier and return the corresponding limits."""
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
        tier = (user.subscription_tier if user else "free") or "free"
        return dict(self._TIER_LIMITS.get(tier, self._TIER_LIMITS["free"]))

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
        # ── Tier-aware rate limiting ────────────────────────────────────
        tier_info = await self._check_tier_limits(bot.user_id)
        if tier_info["reasoning_limit"] > 0:
            from services.security.rate_limit import rate_limiter, RateLimitExceeded
            try:
                rate_limiter.check(
                    "reasoning:calls",
                    str(bot.user_id),
                    limit=tier_info["reasoning_limit"],
                    window_seconds=3600,
                )
            except RateLimitExceeded:
                return await self._build_result(
                    bot_id=bot.id,
                    symbol=symbol,
                    signal=signal,
                    vix=vix,
                    decision="DELAY_TRADE",
                    confidence=0.0,
                    reasoning=f"Reasoning rate limit exceeded ({tier_info['tier']} tier: {tier_info['reasoning_limit']}/hr)",
                    size_adjustment=0.0,
                    delay_seconds=300,
                    events_considered=[],
                    model_used="rate_limit",
                )

        # Category block
        strategy_type = strategy_config.get("strategy_type", "manual")
        type_blocked, type_score = await is_strategy_type_blocked(bot.user_id, strategy_type)
        if type_blocked:
            return await self._build_result(
                bot_id=bot.id, symbol=symbol, signal=signal, vix=vix,
                decision="PAUSE_BOT", confidence=0.0,
                reasoning=f"Strategy type '{strategy_type}' auto-blocked (score: {type_score:.1f})",
                size_adjustment=0.0, delay_seconds=0,
                events_considered=[], model_used="category_block",
            )

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

        # Graduated drawdown + hard blockers
        drawdown_thresholds = await get_drawdown_thresholds(bot.user_id)
        weekly_pnl_pct = await compute_weekly_pnl_pct(bot.user_id)
        hard = await check_hard_blockers(
            vix=vix, events=events_dicts, symbol=symbol,
            portfolio_exposure=portfolio_exposure, daily_pnl_pct=daily_pnl_pct,
            user_id=bot.user_id, weekly_pnl_pct=weekly_pnl_pct,
            drawdown_thresholds=drawdown_thresholds,
        )
        if hard.blocked:
            if hard.drawdown_level in (DRAWDOWN_LEVEL_KILL_DAILY, DRAWDOWN_LEVEL_KILL_WEEKLY):
                _dd_decision = "PAUSE_BOT"
            elif hard.exits_only:
                _dd_decision = "DELAY_TRADE"
            else:
                _dd_decision = "PAUSE_BOT" if daily_pnl_pct < -5.0 else "DELAY_TRADE"
            return await self._build_result(
                bot_id=bot.id, symbol=symbol, signal=signal, vix=vix,
                decision=_dd_decision,
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

        # Fetch open positions across all bots for correlation risk check
        open_positions = await self._get_open_positions_with_sector(bot.user_id)

        # Soft guardrails
        soft = await check_soft_guardrails(
            vix=vix, events=events_dicts, symbol=symbol,
            ai_confidence=llm_result.get("confidence", 0.7),
            override_level=override_level,
            open_positions=open_positions,
        )

        # Merge LLM + safety
        return await self._merge_reasoning(
            bot_id=bot.id, symbol=symbol, signal=signal, vix=vix,
            llm_result=llm_result, soft=soft,
            events_considered=[e["id"] for e in events_dicts[:20]],
            override_level=override_level,
            events=events_dicts,
        )

    async def _get_open_positions_with_sector(self, user_id: int) -> list[dict]:
        """Fetch open trades across all bots for this user, with sector info."""
        from db.cerberus_models import CerberusTrade
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(CerberusTrade.bot_id, CerberusTrade.symbol).where(
                        and_(
                            CerberusTrade.user_id == user_id,
                            CerberusTrade.exit_ts.is_(None),
                            CerberusTrade.bot_id.is_not(None),
                        )
                    )
                )
                rows = result.all()

            if not rows:
                return []

            # Look up sectors via yfinance (deduplicate symbols first)
            unique_symbols = {row[1] for row in rows}
            symbol_sector: dict[str, str] = {}
            try:
                import asyncio
                import yfinance as yf
                loop = asyncio.get_running_loop()
                for sym in unique_symbols:
                    cached = _sector_cache.get(sym)
                    if cached and (time.time() - cached[0]) < _SECTOR_CACHE_TTL:
                        symbol_sector[sym] = cached[1]
                        continue
                    try:
                        info = await loop.run_in_executor(
                            None, lambda s=sym: yf.Ticker(s).info or {}
                        )
                        sector = info.get("sector", "")
                        symbol_sector[sym] = sector
                        _sector_cache[sym] = (time.time(), sector)
                    except Exception as exc:
                        logger.debug("sector_lookup_failed", symbol=sym, error=str(exc))
                        symbol_sector[sym] = ""
            except Exception as exc:
                logger.warning("sector_enrichment_failed", error=str(exc))

            return [
                {"bot_id": row[0], "symbol": row[1], "sector": symbol_sector.get(row[1], "")}
                for row in rows
            ]
        except Exception as exc:
            logger.warning("open_positions_fetch_failed", user_id=user_id, error=str(exc))
            return []

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

            from config.settings import get_settings
            settings = get_settings()

            # Check for bot-level model override
            model_config = bot.reasoning_model_config or {}
            model_name = model_config.get("model")

            # Determine model based on available provider and event severity
            if not model_name:
                has_high_impact = any(e.get("impact") == "HIGH" for e in events_dicts)
                if settings.openai_api_key:
                    model_name = "gpt-5.4" if has_high_impact else "gpt-4.1"
                else:
                    model_name = settings.anthropic_fallback_model or "claude-sonnet-4-6"

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

            # Fetch sentiment data — required for informed trade decisions
            sentiment_data = None
            try:
                from services.sentiment.sentiment_service import get_sentiment_service
                sentiment_data = await get_sentiment_service().analyze_ticker(symbol)
                logger.info("reasoning_sentiment_fetched", symbol=symbol, sentiment=sentiment_data.get("overall_sentiment"), score=sentiment_data.get("score"))
            except Exception as exc:
                logger.error("reasoning_sentiment_failed", symbol=symbol, error=str(exc), exc_info=True)
                return {
                    "decision": "DELAY_TRADE",
                    "confidence": 0.0,
                    "reasoning": f"Sentiment data unavailable for {symbol} — will not trade without market context",
                    "size_adjustment": 0.0,
                    "delay_seconds": 120,
                    "model_used": "sentiment_required",
                }

            prompt = build_trade_decision_prompt(
                bot_name=bot.name, symbol=symbol, signal=signal,
                strategy_config=strategy_config, active_events=events_dicts,
                regime_stats=regime_stats, recent_trades=recent_trades,
                vix=vix,
                ai_thinking=(
                    strategy_config.get("aiThinking")
                    or (strategy_config.get("ai_context") or {}).get("ai_thinking")
                ),
                sentiment=sentiment_data,
            )

            router = ModelRouter()
            openai_failed = not settings.openai_api_key
            routing = router.route(
                mode="strategy",
                message=prompt,
                has_tools=False,
                openai_failed=openai_failed,
            )
            provider = routing.provider
            resolved_model = model_name or routing.model
            response = await provider.complete(
                messages=[
                    ProviderMessage(role="system", content=TRADE_DECISION_SYSTEM),
                    ProviderMessage(role="user", content=prompt),
                ],
                model=resolved_model,
                temperature=0.3,
                max_tokens=500,
                store=False,
            )

            # Parse JSON from response
            text = response.content if hasattr(response, "content") else str(response)
            parsed = self._extract_reasoning_payload(text)
            if parsed is None:
                return self._fail_closed_reasoning(
                    reasoning="LLM response unparseable — delaying trade until a valid decision is available",
                    model_used=resolved_model,
                )

            return {
                "decision": self._normalize_decision(parsed.get("decision")),
                "confidence": self._bounded_float(parsed.get("confidence"), default=0.0, minimum=0.0, maximum=1.0),
                "reasoning": str(parsed.get("reasoning") or "").strip(),
                "size_adjustment": self._bounded_float(parsed.get("size_adjustment"), default=1.0, minimum=0.0, maximum=1.0),
                "delay_seconds": self._bounded_int(parsed.get("delay_seconds"), default=0, minimum=0),
                "model_used": resolved_model,
            }

        except Exception as e:
            logger.error("reasoning_llm_failed", error=str(e), bot_id=bot.id, exc_info=True)
            # Fail-closed: skip the trade when LLM reasoning is unavailable.
            # Never execute without risk evaluation, especially in live mode.
            return {
                "decision": "DELAY_TRADE",
                "confidence": 0.0,
                "reasoning": "LLM unavailable — skipping trade (fail-closed)",
                "size_adjustment": 0.0,
                "delay_seconds": 60,
                "model_used": "safety_rules_fallback",
            }

    @staticmethod
    def _bounded_float(
        value: object,
        *,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return default
        return max(minimum, min(maximum, numeric))

    @staticmethod
    def _bounded_int(value: object, *, default: int, minimum: int = 0) -> int:
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            return default
        return max(minimum, numeric)

    @staticmethod
    def _normalize_decision(value: object) -> str:
        decision = str(value or "").strip().upper()
        if decision in _ALLOWED_DECISIONS:
            return decision
        return "DELAY_TRADE"

    @staticmethod
    def _extract_reasoning_payload(text: str) -> dict | None:
        stripped = str(text or "").strip()
        if not stripped:
            return None

        candidates = [stripped]
        fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
        if fenced_match:
            candidates.insert(0, fenced_match.group(1))

        object_matches = re.findall(r"\{.*\}", stripped, re.DOTALL)
        candidates.extend(object_matches)

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    @staticmethod
    def _fail_closed_reasoning(*, reasoning: str, model_used: str) -> dict:
        return {
            "decision": "DELAY_TRADE",
            "confidence": 0.0,
            "reasoning": reasoning,
            "size_adjustment": 0.0,
            "delay_seconds": 300,
            "model_used": model_used,
        }

    async def _merge_reasoning(
        self, *, bot_id, symbol, signal, vix, llm_result, soft, events_considered,
        override_level: str = "soft", events: list[dict] | None = None,
    ) -> TradeDecision:
        decision = llm_result.get("decision", "EXECUTE")
        confidence = llm_result.get("confidence", 0.7)
        size_adj = llm_result.get("size_adjustment", 1.0)
        delay = llm_result.get("delay_seconds", 0)
        reasons = [llm_result.get("reasoning", "")]

        # Always apply size reductions from guardrails
        if soft.reduce_size < size_adj:
            size_adj = soft.reduce_size
        # Only apply guardrail delays if the LLM didn't approve the trade
        # with reasonable confidence — the LLM already evaluated the events.
        if decision in ("EXECUTE", "REDUCE_SIZE") and confidence >= 0.4:
            # LLM considered events and chose to proceed — respect that decision.
            # Still apply size reductions above but don't block the trade.
            pass
        elif soft.delay_seconds > delay:
            delay = soft.delay_seconds
        if soft.reasons:
            reasons.extend(soft.reasons)

        # Full autonomy: allow aggressive decisions the engine wouldn't
        # otherwise make under advisory or soft override levels.
        if override_level == "full":
            has_high_impact = any(
                e.get("impact") == "HIGH" for e in (events or [])
            )
            if confidence < 0.2 and has_high_impact:
                decision = "EXIT_POSITION"
                size_adj = 0.0
                reasons.append(
                    "Full autonomy: very low confidence + HIGH impact event — proactively exiting position"
                )

        return await self._build_result(
            bot_id=bot_id, symbol=symbol, signal=signal, vix=vix,
            decision=decision, confidence=confidence,
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

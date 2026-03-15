"""
AI Reasoning Layer endpoints — market events, risk score, bot reasoning/learning/universe data.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, and_, desc

from db.database import get_session
from db.cerberus_models import (
    MarketEvent,
    TradeDecision,
    UniverseCandidate,
    BotTradeJournal,
    BotRegimeStats,
    BotAdaptation,
    CerberusBot,
)
from services.security.access_control import require_owned_bot

logger = structlog.get_logger(__name__)
router = APIRouter()


def _get_user_id(request: Request) -> int:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


async def _require_owned_bot(request: Request, bot_id: str) -> CerberusBot:
    bot = await require_owned_bot(request, bot_id)
    return bot


# ── Market Events ────────────────────────────────────────────────────────────


@router.get("/events")
async def get_market_events(
    request: Request,
    event_type: Optional[str] = Query(None),
    impact: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Get active market events (non-expired)."""
    user_id = _get_user_id(request)
    now = datetime.utcnow()

    async with get_session() as session:
        query = select(MarketEvent).where(
            and_(
                (MarketEvent.expires_at.is_(None)) | (MarketEvent.expires_at > now),
                (MarketEvent.user_id.is_(None)) | (MarketEvent.user_id == user_id),
            )
        )
        if event_type:
            query = query.where(func.lower(MarketEvent.event_type) == event_type.lower())
        if impact:
            query = query.where(func.upper(MarketEvent.impact) == impact.upper())

        query = query.order_by(desc(MarketEvent.detected_at)).limit(limit)
        result = await session.execute(query)
        events = result.scalars().all()

    return [
        {
            "id": e.id,
            "event_type": str(e.event_type or "").lower(),
            "impact": str(e.impact or "").upper(),
            "symbols": e.symbols or [],
            "sectors": e.sectors or [],
            "headline": e.headline,
            "source": e.source,
            "raw_data": e.raw_data or {},
            "detected_at": e.detected_at.isoformat() if e.detected_at else None,
            "expires_at": e.expires_at.isoformat() if e.expires_at else None,
        }
        for e in events
    ]


@router.get("/risk-score")
async def get_risk_score(request: Request):
    """Compute composite risk score (0-100) from VIX + Fear/Greed + active HIGH events."""
    user_id = _get_user_id(request)
    now = datetime.utcnow()

    async with get_session() as session:
        result = await session.execute(
            select(MarketEvent).where(
                and_(
                    (MarketEvent.expires_at.is_(None)) | (MarketEvent.expires_at > now),
                    (MarketEvent.user_id.is_(None)) | (MarketEvent.user_id == user_id),
                )
            ).order_by(desc(MarketEvent.detected_at)).limit(100)
        )
        events = result.scalars().all()

    # Extract VIX
    vix = None
    fear_greed = None
    high_count = 0

    for e in events:
        if e.event_type == "volatility" and e.raw_data:
            vix = e.raw_data.get("vix")
        if e.event_type == "sentiment" and e.source == "cnn_fear_greed" and e.raw_data:
            fear_greed = e.raw_data.get("score")
        if e.impact == "HIGH":
            high_count += 1

    # Composite score: higher = more risk
    score = 0.0
    components = {}

    if vix is not None:
        vix_score = min(100, max(0, (vix - 12) * 3.5))
        score += vix_score * 0.4
        components["vix"] = {"value": vix, "score": round(vix_score, 1)}

    if fear_greed is not None:
        # Invert: low F/G = high risk
        fg_risk = max(0, 100 - fear_greed)
        score += fg_risk * 0.3
        components["fear_greed"] = {"value": fear_greed, "score": round(fg_risk, 1)}

    event_score = min(100, high_count * 25)
    score += event_score * 0.3
    components["high_events"] = {"count": high_count, "score": event_score}

    # Normalize
    score = min(100, max(0, score))
    level = "low" if score < 33 else ("medium" if score < 66 else "high")

    return {
        "score": round(score, 1),
        "level": level,
        "components": components,
        "active_events": len(events),
    }


# ── Bot Reasoning ────────────────────────────────────────────────────────────


@router.get("/bots/{bot_id}/decisions")
async def get_bot_decisions(
    request: Request,
    bot_id: str,
    limit: int = Query(20, ge=1, le=100),
):
    """Get trade decision history for a bot."""
    bot = await _require_owned_bot(request, bot_id)

    async with get_session() as session:
        result = await session.execute(
            select(TradeDecision)
            .where(TradeDecision.bot_id == bot.id)
            .order_by(desc(TradeDecision.created_at))
            .limit(limit)
        )
        decisions = result.scalars().all()

    return [
        {
            "id": d.id,
            "symbol": d.symbol,
            "strategy_signal": d.strategy_signal,
            "context_risk_level": d.context_risk_level,
            "ai_confidence": d.ai_confidence,
            "decision": d.decision,
            "reasoning": d.reasoning,
            "size_adjustment": d.size_adjustment,
            "delay_seconds": d.delay_seconds,
            "events_considered": d.events_considered or [],
            "model_used": d.model_used,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in decisions
    ]


# ── Bot Learning ─────────────────────────────────────────────────────────────


@router.get("/bots/{bot_id}/journal")
async def get_bot_journal(
    request: Request,
    bot_id: str,
    limit: int = Query(20, ge=1, le=100),
):
    """Get trade journal entries for a bot."""
    bot = await _require_owned_bot(request, bot_id)

    async with get_session() as session:
        result = await session.execute(
            select(BotTradeJournal)
            .where(BotTradeJournal.bot_id == bot.id)
            .order_by(desc(BotTradeJournal.created_at))
            .limit(limit)
        )
        entries = result.scalars().all()

    return [
        {
            "id": e.id,
            "trade_id": e.trade_id,
            "symbol": e.symbol,
            "side": e.side,
            "entry_price": e.entry_price,
            "exit_price": e.exit_price,
            "pnl": e.pnl,
            "pnl_pct": e.pnl_pct,
            "vix_at_entry": e.vix_at_entry,
            "ai_confidence_at_entry": e.ai_confidence_at_entry,
            "ai_decision": e.ai_decision,
            "ai_reasoning": e.ai_reasoning,
            "regime_at_entry": e.regime_at_entry,
            "outcome_tag": e.outcome_tag,
            "lesson_learned": e.lesson_learned,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]


@router.get("/bots/{bot_id}/regime-stats")
async def get_bot_regime_stats(request: Request, bot_id: str):
    """Get per-regime performance stats for a bot."""
    bot = await _require_owned_bot(request, bot_id)

    async with get_session() as session:
        result = await session.execute(
            select(BotRegimeStats).where(BotRegimeStats.bot_id == bot.id)
        )
        stats = result.scalars().all()

    return [
        {
            "regime": s.regime,
            "total_trades": s.total_trades,
            "win_rate": s.win_rate,
            "avg_pnl": s.avg_pnl,
            "avg_confidence": s.avg_confidence,
            "sharpe": s.sharpe,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in stats
    ]


@router.get("/bots/{bot_id}/adaptations")
async def get_bot_adaptations(
    request: Request,
    bot_id: str,
    limit: int = Query(20, ge=1, le=100),
):
    """Get learning adaptation history for a bot."""
    bot = await _require_owned_bot(request, bot_id)

    async with get_session() as session:
        result = await session.execute(
            select(BotAdaptation)
            .where(BotAdaptation.bot_id == bot.id)
            .order_by(desc(BotAdaptation.created_at))
            .limit(limit)
        )
        adaptations = result.scalars().all()

    return [
        {
            "id": a.id,
            "adaptation_type": a.adaptation_type,
            "old_value": a.old_value,
            "new_value": a.new_value,
            "reasoning": a.reasoning,
            "confidence": a.confidence,
            "auto_applied": a.auto_applied,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in adaptations
    ]


# ── Bot Universe ─────────────────────────────────────────────────────────────


@router.get("/bots/{bot_id}/universe")
async def get_bot_universe(request: Request, bot_id: str):
    """Get current universe candidates for a bot."""
    bot = await _require_owned_bot(request, bot_id)

    async with get_session() as session:
        result = await session.execute(
            select(UniverseCandidate)
            .where(UniverseCandidate.bot_id == bot.id)
            .order_by(desc(UniverseCandidate.score))
        )
        candidates = result.scalars().all()

    return [
        {
            "id": c.id,
            "symbol": c.symbol,
            "score": c.score,
            "reason": c.reason,
            "scanned_at": c.scanned_at.isoformat() if c.scanned_at else None,
        }
        for c in candidates
    ]

"""Aggregated performance metrics per model per bot."""
from __future__ import annotations

import math

import structlog
from sqlalchemy import select

from db.database import get_session
from db.cerberus_models import BotModelPerformance

logger = structlog.get_logger(__name__)


def compute_model_metrics(rows: list[dict]) -> dict:
    """Compute aggregated metrics from a list of resolved decision dicts.

    Each dict must have: pnl (float), confidence (float), decided_at (str).
    Returns: trades_count, win_rate, avg_return, sharpe_ratio, max_drawdown, total_pnl, avg_confidence.
    """
    if not rows:
        return {
            "trades_count": 0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "total_pnl": 0.0,
            "avg_confidence": 0.0,
        }

    pnls = [float(r["pnl"]) for r in rows]
    confidences = [float(r.get("confidence") or 0) for r in rows]

    trades_count = len(pnls)
    wins = sum(1 for p in pnls if p > 0)
    win_rate = round(wins / trades_count, 4)
    avg_return = round(sum(pnls) / trades_count, 4)
    total_pnl = round(sum(pnls), 4)
    avg_confidence = round(sum(confidences) / trades_count, 4) if confidences else 0.0

    # Sharpe ratio: mean(pnl) / std(pnl) * sqrt(252) — annualized
    # Use sample standard deviation (N-1) per financial convention
    mean_pnl = sum(pnls) / trades_count
    if trades_count < 2:
        sharpe_ratio = 0.0
    else:
        variance = sum((p - mean_pnl) ** 2 for p in pnls) / (trades_count - 1)
        std_pnl = math.sqrt(variance)
        sharpe_ratio = round((mean_pnl / std_pnl) * math.sqrt(252), 4) if std_pnl > 0 else 0.0

    # Max drawdown: peak-to-trough of cumulative P&L
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        cumulative += p
        if cumulative > peak:
            peak = cumulative
        dd = cumulative - peak
        if dd < max_dd:
            max_dd = dd
    max_drawdown = round(max_dd, 4)

    return {
        "trades_count": trades_count,
        "win_rate": win_rate,
        "avg_return": avg_return,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "total_pnl": total_pnl,
        "avg_confidence": avg_confidence,
    }


async def get_bot_model_metrics(bot_id: str) -> dict[str, dict]:
    """Query resolved decisions from DB and compute metrics per model.

    Returns: {"gpt-5.4": {metrics}, "claude-sonnet-4-6": {metrics}, ...}
    """
    async with get_session() as session:
        result = await session.execute(
            select(
                BotModelPerformance.model_used,
                BotModelPerformance.pnl,
                BotModelPerformance.confidence,
                BotModelPerformance.decided_at,
            )
            .where(
                BotModelPerformance.bot_id == bot_id,
                BotModelPerformance.resolved_at.isnot(None),
                BotModelPerformance.pnl.isnot(None),
            )
            .order_by(BotModelPerformance.decided_at)
        )
        rows = result.all()

    # Group by model
    by_model: dict[str, list[dict]] = {}
    for row in rows:
        model = row.model_used
        by_model.setdefault(model, []).append({
            "pnl": row.pnl,
            "confidence": row.confidence,
            "decided_at": row.decided_at.isoformat() if row.decided_at else "",
        })

    return {model: compute_model_metrics(decisions) for model, decisions in by_model.items()}

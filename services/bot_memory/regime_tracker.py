"""Regime classification and performance tracking."""
from __future__ import annotations

import asyncio
from datetime import datetime

import structlog
from sqlalchemy import select, and_

from db.database import get_session
from db.cerberus_models import BotRegimeStats, BotTradeJournal

logger = structlog.get_logger(__name__)


def _fetch_spy_data_sync() -> dict | None:
    """Fetch SPY data for regime classification."""
    try:
        import yfinance as yf
        import numpy as np
        spy = yf.Ticker("SPY")
        hist = spy.history(period="30d", interval="1d")
        if len(hist) < 20:
            return None
        closes = hist["Close"].values
        sma20 = closes[-20:].mean()
        # SMA slope: average daily change over 20 days
        daily_changes = [(closes[i] - closes[i-1]) / closes[i-1] * 100 for i in range(-20, 0) if i-1 >= -len(closes)]
        slope = sum(daily_changes) / len(daily_changes) if daily_changes else 0
        return {"sma20": float(sma20), "slope": slope, "price": float(closes[-1])}
    except Exception as e:
        logger.warning("spy_data_fetch_failed", error=str(e))
        return None


async def classify_regime(vix: float | None = None) -> list[str]:
    """Classify current market regime. Returns list of regime tags."""
    regimes = []

    # VIX-based volatility regime
    if vix is not None:
        if vix < 18:
            regimes.append("low_vol")
        elif vix <= 25:
            regimes.append("normal_vol")
        else:
            regimes.append("high_vol")

    # SPY trend regime
    loop = asyncio.get_running_loop()
    spy_data = await loop.run_in_executor(None, _fetch_spy_data_sync)
    if spy_data:
        slope = spy_data["slope"]
        price = spy_data["price"]
        sma20 = spy_data["sma20"]

        if slope > 0.1 and price > sma20:
            regimes.append("trending_up")
        elif slope < -0.1 and price < sma20:
            regimes.append("trending_down")
        else:
            regimes.append("range_bound")

    return regimes if regimes else ["unknown"]


async def update_regime_stats(bot_id: str) -> None:
    """Recompute regime stats from trade journal for a bot."""
    async with get_session() as session:
        result = await session.execute(
            select(BotTradeJournal).where(BotTradeJournal.bot_id == bot_id)
        )
        trades = result.scalars().all()

    if not trades:
        return

    # Group by regime
    regime_data: dict[str, list] = {}
    for t in trades:
        regime = t.regime_at_entry or "unknown"
        if regime not in regime_data:
            regime_data[regime] = []
        regime_data[regime].append(t)

    async with get_session() as session:
        for regime, regime_trades in regime_data.items():
            total = len(regime_trades)
            wins = sum(1 for t in regime_trades if (t.pnl or 0) > 0)
            win_rate = wins / total if total > 0 else 0.0
            pnls = [t.pnl or 0 for t in regime_trades]
            avg_pnl = sum(pnls) / total if total > 0 else 0.0
            avg_confidence = sum(t.ai_confidence_at_entry or 0 for t in regime_trades) / total if total > 0 else 0.0

            # Sharpe ratio (simplified)
            import statistics
            if len(pnls) > 1:
                std = statistics.stdev(pnls)
                sharpe = (avg_pnl / std) if std > 0 else 0.0
            else:
                sharpe = 0.0

            # Upsert
            existing = await session.execute(
                select(BotRegimeStats).where(
                    and_(BotRegimeStats.bot_id == bot_id, BotRegimeStats.regime == regime)
                )
            )
            stat = existing.scalar_one_or_none()
            if stat:
                stat.total_trades = total
                stat.win_rate = round(win_rate, 4)
                stat.avg_pnl = round(avg_pnl, 4)
                stat.avg_confidence = round(avg_confidence, 4)
                stat.sharpe = round(sharpe, 4)
                stat.updated_at = datetime.utcnow()
            else:
                import uuid
                session.add(BotRegimeStats(
                    id=str(uuid.uuid4()),
                    bot_id=bot_id,
                    regime=regime,
                    total_trades=total,
                    win_rate=round(win_rate, 4),
                    avg_pnl=round(avg_pnl, 4),
                    avg_confidence=round(avg_confidence, 4),
                    sharpe=round(sharpe, 4),
                ))

    logger.info("regime_stats_updated", bot_id=bot_id, regimes=list(regime_data.keys()))

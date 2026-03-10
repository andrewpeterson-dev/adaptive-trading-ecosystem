"""
Dashboard data endpoints — equity curve and portfolio overview.
"""

from datetime import datetime, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Request
from sqlalchemy import select

from db.database import get_session
from db.models import PortfolioSnapshot, TradingModeEnum

logger = structlog.get_logger(__name__)
router = APIRouter()

STARTING_CAPITAL = 8082.72


def _generate_seed_equity_curve():
    """Generate sample equity curve based on $8,082.72 Webull starting capital."""
    import random

    random.seed(42)  # Deterministic seed data
    points = []
    equity = STARTING_CAPITAL
    cash = STARTING_CAPITAL
    now = datetime.utcnow()
    start = now - timedelta(days=60)

    for i in range(61):
        day = start + timedelta(days=i)
        # Slight random walk with upward drift
        daily_return = random.gauss(0.0008, 0.012)
        equity *= (1 + daily_return)
        cash_ratio = max(0.3, min(0.9, cash / equity))
        cash = equity * cash_ratio
        drawdown_pct = max(0.0, (STARTING_CAPITAL - equity) / STARTING_CAPITAL) if equity < STARTING_CAPITAL else 0.0

        points.append({
            "date": day.strftime("%Y-%m-%d"),
            "value": round(equity, 2),
            "cash": round(cash, 2),
            "drawdown_pct": round(drawdown_pct, 4),
        })

    return points


@router.get("/equity-curve")
async def get_equity_curve(request: Request):
    """Get equity curve data for charting — filtered by active trading mode."""
    mode = request.state.trading_mode

    async with get_session() as db:
        result = await db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.mode == mode)
            .order_by(PortfolioSnapshot.timestamp.asc())
            .limit(500)
        )
        snapshots = result.scalars().all()

    if snapshots:
        points = [
            {
                "date": s.timestamp.strftime("%Y-%m-%d"),
                "value": round(s.total_equity, 2),
                "cash": round(s.cash, 2),
                "drawdown_pct": round(s.drawdown_pct, 4),
            }
            for s in snapshots
        ]
        return {"equity_curve": points, "mode": mode.value}

    # No data yet — return seed curve for demo purposes
    logger.info("equity_curve_seed_data", reason="no portfolio snapshots", mode=mode.value)
    return {"equity_curve": _generate_seed_equity_curve(), "mode": mode.value}

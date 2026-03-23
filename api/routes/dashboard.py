"""
Dashboard data endpoints — equity curve and portfolio overview.
"""

import structlog
from fastapi import APIRouter, Request
from sqlalchemy import select

from db.database import get_session
from db.models import PortfolioSnapshot

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/equity-curve")
async def get_equity_curve(request: Request):
    """Get equity curve data for charting — filtered by user and active trading mode."""
    user_id = request.state.user_id
    mode = request.state.trading_mode

    async with get_session() as db:
        result = await db.execute(
            select(PortfolioSnapshot)
            .where(
                PortfolioSnapshot.mode == mode,
                PortfolioSnapshot.user_id == user_id,
            )
            .order_by(PortfolioSnapshot.timestamp.asc())
            .limit(500)
        )
        snapshots = result.scalars().all()

    if snapshots:
        points = [
            {
                "date": s.timestamp.strftime("%Y-%m-%d"),
                "equity": round(s.total_equity, 2),
                "cash": round(s.cash, 2),
                "drawdown": round(s.drawdown_pct, 4),
            }
            for s in snapshots
        ]
        return {"equity_curve": points, "mode": mode.value}

    # No data yet — no trades placed
    logger.info("equity_curve_empty", reason="no portfolio snapshots", mode=mode.value)
    return {"equity_curve": [], "mode": mode.value}

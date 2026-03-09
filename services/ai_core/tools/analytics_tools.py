"""Analytics tools for the AI Copilot."""
from __future__ import annotations

import structlog

from services.ai_core.tools.base import ToolDefinition, ToolCategory, ToolSideEffect
from services.ai_core.tools.registry import get_registry

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _get_best_trade(user_id: int, limit: int = 1) -> dict:
    """Get best trade(s) by return_pct."""
    from db.database import get_session
    from db.copilot_models import CopilotTrade
    from sqlalchemy import select

    async with get_session() as session:
        stmt = (
            select(CopilotTrade)
            .where(CopilotTrade.user_id == user_id, CopilotTrade.return_pct.isnot(None))
            .order_by(CopilotTrade.return_pct.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        trades = result.scalars().all()

    if not trades:
        return {"trades": [], "message": "No trades with return data found"}

    return {
        "trades": [_trade_to_dict(t) for t in trades],
    }


async def _get_worst_trades(user_id: int, limit: int = 5) -> dict:
    """Get worst trades by return_pct."""
    from db.database import get_session
    from db.copilot_models import CopilotTrade
    from sqlalchemy import select

    async with get_session() as session:
        stmt = (
            select(CopilotTrade)
            .where(CopilotTrade.user_id == user_id, CopilotTrade.return_pct.isnot(None))
            .order_by(CopilotTrade.return_pct.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        trades = result.scalars().all()

    if not trades:
        return {"trades": [], "message": "No trades with return data found"}

    return {
        "trades": [_trade_to_dict(t) for t in trades],
    }


async def _get_total_trading_volume(user_id: int, days: int = None) -> dict:
    """Sum of trade volumes."""
    from db.database import get_session
    from db.copilot_models import CopilotTrade
    from sqlalchemy import select, func

    async with get_session() as session:
        stmt = select(
            func.count(CopilotTrade.id).label("trade_count"),
            func.sum(CopilotTrade.quantity).label("total_quantity"),
            func.sum(CopilotTrade.quantity * CopilotTrade.entry_price).label("total_notional"),
        ).where(CopilotTrade.user_id == user_id)

        if days:
            from datetime import datetime, timedelta
            cutoff = datetime.utcnow() - timedelta(days=days)
            stmt = stmt.where(CopilotTrade.entry_ts >= cutoff)

        result = await session.execute(stmt)
        row = result.one()

    return {
        "trade_count": int(row.trade_count or 0),
        "total_quantity": round(float(row.total_quantity or 0), 4),
        "total_notional": round(float(row.total_notional or 0), 2),
        "days": days,
    }


async def _get_strategy_performance(user_id: int) -> dict:
    """Performance grouped by strategy_tag."""
    from db.database import get_session
    from db.copilot_models import CopilotTrade
    from sqlalchemy import select, func

    async with get_session() as session:
        stmt = (
            select(
                CopilotTrade.strategy_tag,
                func.count(CopilotTrade.id).label("trades"),
                func.sum(CopilotTrade.net_pnl).label("total_pnl"),
                func.avg(CopilotTrade.return_pct).label("avg_return_pct"),
                func.sum(
                    func.cast(CopilotTrade.net_pnl > 0, Integer)
                ).label("wins"),
            )
            .where(CopilotTrade.user_id == user_id)
            .group_by(CopilotTrade.strategy_tag)
        )
        result = await session.execute(stmt)
        rows = result.all()

    if not rows:
        return {"strategies": [], "message": "No trade data found"}

    strategies = []
    for row in rows:
        trade_count = int(row.trades or 0)
        wins = int(row.wins or 0)
        strategies.append({
            "strategy_tag": row.strategy_tag or "untagged",
            "trades": trade_count,
            "total_pnl": round(float(row.total_pnl or 0), 2),
            "avg_return_pct": round(float(row.avg_return_pct or 0), 4),
            "win_rate": round(wins / trade_count * 100, 2) if trade_count > 0 else 0,
        })

    return {"strategies": strategies}


async def _get_symbol_performance(user_id: int, limit: int = 20) -> dict:
    """Performance grouped by symbol."""
    from db.database import get_session
    from db.copilot_models import CopilotTrade
    from sqlalchemy import select, func

    async with get_session() as session:
        stmt = (
            select(
                CopilotTrade.symbol,
                func.count(CopilotTrade.id).label("trades"),
                func.sum(CopilotTrade.net_pnl).label("total_pnl"),
                func.avg(CopilotTrade.return_pct).label("avg_return_pct"),
            )
            .where(CopilotTrade.user_id == user_id)
            .group_by(CopilotTrade.symbol)
            .order_by(func.sum(CopilotTrade.net_pnl).desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.all()

    if not rows:
        return {"symbols": [], "message": "No trade data found"}

    return {
        "symbols": [
            {
                "symbol": row.symbol,
                "trades": int(row.trades or 0),
                "total_pnl": round(float(row.total_pnl or 0), 2),
                "avg_return_pct": round(float(row.avg_return_pct or 0), 4),
            }
            for row in rows
        ],
    }


async def _get_hold_time_stats(user_id: int) -> dict:
    """Average hold time statistics."""
    from db.database import get_session
    from db.copilot_models import CopilotTrade
    from sqlalchemy import select

    async with get_session() as session:
        stmt = (
            select(CopilotTrade)
            .where(
                CopilotTrade.user_id == user_id,
                CopilotTrade.entry_ts.isnot(None),
                CopilotTrade.exit_ts.isnot(None),
            )
        )
        result = await session.execute(stmt)
        trades = result.scalars().all()

    if not trades:
        return {"avg_hold_hours": 0, "min_hold_hours": 0, "max_hold_hours": 0, "trades_analyzed": 0, "message": "No closed trades with timestamps"}

    hold_times = []
    for t in trades:
        delta = t.exit_ts - t.entry_ts
        hold_times.append(delta.total_seconds() / 3600)

    avg_hold = sum(hold_times) / len(hold_times)
    return {
        "avg_hold_hours": round(avg_hold, 2),
        "median_hold_hours": round(sorted(hold_times)[len(hold_times) // 2], 2),
        "min_hold_hours": round(min(hold_times), 2),
        "max_hold_hours": round(max(hold_times), 2),
        "trades_analyzed": len(hold_times),
    }


async def _get_bot_performance(user_id: int, bot_id: str = None) -> dict:
    """Bot performance metrics."""
    from db.database import get_session
    from db.copilot_models import CopilotTrade
    from sqlalchemy import select, func

    async with get_session() as session:
        stmt = (
            select(
                CopilotTrade.bot_id,
                func.count(CopilotTrade.id).label("trades"),
                func.sum(CopilotTrade.net_pnl).label("total_pnl"),
                func.avg(CopilotTrade.return_pct).label("avg_return_pct"),
            )
            .where(
                CopilotTrade.user_id == user_id,
                CopilotTrade.bot_id.isnot(None),
            )
        )
        if bot_id:
            stmt = stmt.where(CopilotTrade.bot_id == bot_id)
        stmt = stmt.group_by(CopilotTrade.bot_id)

        result = await session.execute(stmt)
        rows = result.all()

    if not rows:
        return {"bots": [], "message": "No bot trade data found"}

    return {
        "bots": [
            {
                "bot_id": row.bot_id,
                "trades": int(row.trades or 0),
                "total_pnl": round(float(row.total_pnl or 0), 2),
                "avg_return_pct": round(float(row.avg_return_pct or 0), 4),
            }
            for row in rows
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trade_to_dict(t) -> dict:
    return {
        "id": t.id,
        "symbol": t.symbol,
        "side": t.side,
        "quantity": float(t.quantity),
        "entry_price": float(t.entry_price) if t.entry_price else None,
        "exit_price": float(t.exit_price) if t.exit_price else None,
        "entry_ts": t.entry_ts.isoformat() if t.entry_ts else None,
        "exit_ts": t.exit_ts.isoformat() if t.exit_ts else None,
        "gross_pnl": float(t.gross_pnl) if t.gross_pnl else None,
        "net_pnl": float(t.net_pnl) if t.net_pnl else None,
        "return_pct": float(t.return_pct) if t.return_pct else None,
        "strategy_tag": t.strategy_tag,
        "bot_id": t.bot_id,
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

# Need Integer import for the cast in _get_strategy_performance
from sqlalchemy import Integer


def register():
    registry = get_registry()

    registry.register(ToolDefinition(
        name="getBestTrade",
        version="1.0",
        description="Get the best trade(s) by return percentage",
        category=ToolCategory.ANALYTICS,
        side_effect=ToolSideEffect.READ,
        timeout_ms=3000,
        cache_ttl_s=60,
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of top trades to return", "default": 1},
            },
        },
        output_schema={"type": "object"},
        handler=_get_best_trade,
    ))

    registry.register(ToolDefinition(
        name="getWorstTrades",
        version="1.0",
        description="Get the worst trades by return percentage",
        category=ToolCategory.ANALYTICS,
        side_effect=ToolSideEffect.READ,
        timeout_ms=3000,
        cache_ttl_s=60,
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of worst trades to return", "default": 5},
            },
        },
        output_schema={"type": "object"},
        handler=_get_worst_trades,
    ))

    registry.register(ToolDefinition(
        name="getTotalTradingVolume",
        version="1.0",
        description="Get total trading volume (count, quantity, notional value)",
        category=ToolCategory.ANALYTICS,
        side_effect=ToolSideEffect.READ,
        timeout_ms=3000,
        cache_ttl_s=60,
        input_schema={
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Lookback period in days (omit for all time)"},
            },
        },
        output_schema={"type": "object"},
        handler=_get_total_trading_volume,
    ))

    registry.register(ToolDefinition(
        name="getStrategyPerformance",
        version="1.0",
        description="Get performance metrics grouped by strategy tag (P&L, win rate, avg return)",
        category=ToolCategory.ANALYTICS,
        side_effect=ToolSideEffect.READ,
        timeout_ms=5000,
        cache_ttl_s=60,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object"},
        handler=_get_strategy_performance,
    ))

    registry.register(ToolDefinition(
        name="getSymbolPerformance",
        version="1.0",
        description="Get performance metrics grouped by symbol",
        category=ToolCategory.ANALYTICS,
        side_effect=ToolSideEffect.READ,
        timeout_ms=5000,
        cache_ttl_s=60,
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max symbols to return", "default": 20},
            },
        },
        output_schema={"type": "object"},
        handler=_get_symbol_performance,
    ))

    registry.register(ToolDefinition(
        name="getHoldTimeStats",
        version="1.0",
        description="Get average, median, min, and max hold time statistics for closed trades",
        category=ToolCategory.ANALYTICS,
        side_effect=ToolSideEffect.READ,
        timeout_ms=5000,
        cache_ttl_s=60,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object"},
        handler=_get_hold_time_stats,
    ))

    registry.register(ToolDefinition(
        name="getBotPerformance",
        version="1.0",
        description="Get performance metrics for trading bots",
        category=ToolCategory.ANALYTICS,
        side_effect=ToolSideEffect.READ,
        timeout_ms=5000,
        cache_ttl_s=60,
        input_schema={
            "type": "object",
            "properties": {
                "bot_id": {"type": "string", "description": "Specific bot ID (omit for all bots)"},
            },
        },
        output_schema={"type": "object"},
        handler=_get_bot_performance,
    ))

"""Portfolio tools for the Cerberus."""
from __future__ import annotations

import structlog

from services.ai_core.tools.base import ToolDefinition, ToolCategory, ToolSideEffect
from services.ai_core.tools.registry import get_registry

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _get_portfolio(user_id: int, account_id: str = None) -> dict:
    """Get portfolio summary (cash, equity, buying power, P&L)."""
    from db.database import get_session
    from db.cerberus_models import CerberusPortfolioSnapshot
    from sqlalchemy import select

    async with get_session() as session:
        stmt = (
            select(CerberusPortfolioSnapshot)
            .where(CerberusPortfolioSnapshot.user_id == user_id)
        )
        if account_id:
            stmt = stmt.where(CerberusPortfolioSnapshot.brokerage_account_id == account_id)
        stmt = stmt.order_by(CerberusPortfolioSnapshot.snapshot_ts.desc()).limit(1)

        result = await session.execute(stmt)
        snapshot = result.scalar_one_or_none()
        if not snapshot:
            return {"cash": 0, "equity": 0, "positions": 0, "message": "No portfolio data available"}
        return {
            "cash": float(snapshot.cash or 0),
            "equity": float(snapshot.equity or 0),
            "buying_power": float(snapshot.buying_power or 0),
            "margin_used": float(snapshot.margin_used or 0),
            "day_pnl": float(snapshot.day_pnl or 0),
            "total_pnl": float(snapshot.total_pnl or 0),
            "snapshot_ts": snapshot.snapshot_ts.isoformat() if snapshot.snapshot_ts else None,
        }


async def _get_positions(user_id: int, account_id: str = None) -> dict:
    """Get open positions."""
    from db.database import get_session
    from db.cerberus_models import CerberusPosition
    from sqlalchemy import select

    async with get_session() as session:
        stmt = select(CerberusPosition).where(CerberusPosition.user_id == user_id)
        if account_id:
            stmt = stmt.where(CerberusPosition.brokerage_account_id == account_id)

        result = await session.execute(stmt)
        positions = result.scalars().all()
        return {
            "count": len(positions),
            "positions": [
                {
                    "symbol": p.symbol,
                    "asset_type": p.asset_type,
                    "quantity": float(p.quantity),
                    "avg_price": float(p.avg_price or 0),
                    "mark_price": float(p.mark_price or 0),
                    "market_value": float(p.market_value or 0),
                    "unrealized_pnl": float(p.unrealized_pnl or 0),
                    "realized_pnl": float(p.realized_pnl or 0),
                }
                for p in positions
            ],
        }


async def _get_orders(user_id: int, account_id: str = None, status: str = None, limit: int = 20) -> dict:
    """Get recent orders."""
    from db.database import get_session
    from db.cerberus_models import CerberusOrder
    from sqlalchemy import select

    async with get_session() as session:
        stmt = select(CerberusOrder).where(CerberusOrder.user_id == user_id)
        if account_id:
            stmt = stmt.where(CerberusOrder.brokerage_account_id == account_id)
        if status:
            stmt = stmt.where(CerberusOrder.status == status)
        stmt = stmt.order_by(CerberusOrder.created_at.desc()).limit(limit)

        result = await session.execute(stmt)
        orders = result.scalars().all()
        return {
            "count": len(orders),
            "orders": [
                {
                    "id": o.id,
                    "symbol": o.symbol,
                    "side": o.side,
                    "order_type": o.order_type,
                    "quantity": float(o.quantity),
                    "limit_price": float(o.limit_price) if o.limit_price else None,
                    "stop_price": float(o.stop_price) if o.stop_price else None,
                    "status": o.status,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in orders
            ],
        }


async def _get_trade_history(
    user_id: int,
    symbol: str = None,
    strategy_tag: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = 50,
) -> dict:
    """Get trade history with optional filters."""
    from datetime import datetime
    from db.database import get_session
    from db.cerberus_models import CerberusTrade
    from sqlalchemy import select

    async with get_session() as session:
        stmt = select(CerberusTrade).where(CerberusTrade.user_id == user_id)
        if symbol:
            stmt = stmt.where(CerberusTrade.symbol == symbol.upper())
        if strategy_tag:
            stmt = stmt.where(CerberusTrade.strategy_tag == strategy_tag)
        if start_date:
            stmt = stmt.where(CerberusTrade.entry_ts >= datetime.fromisoformat(start_date))
        if end_date:
            stmt = stmt.where(CerberusTrade.entry_ts <= datetime.fromisoformat(end_date))
        stmt = stmt.order_by(CerberusTrade.created_at.desc()).limit(limit)

        result = await session.execute(stmt)
        trades = result.scalars().all()
        return {
            "count": len(trades),
            "trades": [
                {
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
                for t in trades
            ],
        }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register():
    registry = get_registry()

    registry.register(ToolDefinition(
        name="getPortfolio",
        version="1.0",
        description="Get portfolio summary including cash, equity, buying power, and P&L",
        category=ToolCategory.PORTFOLIO,
        side_effect=ToolSideEffect.READ,
        timeout_ms=2000,
        cache_ttl_s=30,
        input_schema={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Optional brokerage account ID"},
            },
        },
        output_schema={"type": "object"},
        handler=_get_portfolio,
    ))

    registry.register(ToolDefinition(
        name="getPositions",
        version="1.0",
        description="Get all open positions with current P&L",
        category=ToolCategory.PORTFOLIO,
        side_effect=ToolSideEffect.READ,
        timeout_ms=2000,
        cache_ttl_s=15,
        input_schema={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Optional brokerage account ID"},
            },
        },
        output_schema={"type": "object"},
        handler=_get_positions,
    ))

    registry.register(ToolDefinition(
        name="getOrders",
        version="1.0",
        description="Get recent orders with optional status filter",
        category=ToolCategory.PORTFOLIO,
        side_effect=ToolSideEffect.READ,
        timeout_ms=2000,
        cache_ttl_s=10,
        input_schema={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Optional brokerage account ID"},
                "status": {"type": "string", "description": "Filter by order status (pending, filled, cancelled, etc.)"},
                "limit": {"type": "integer", "description": "Max orders to return", "default": 20},
            },
        },
        output_schema={"type": "object"},
        handler=_get_orders,
    ))

    registry.register(ToolDefinition(
        name="getTradeHistory",
        version="1.0",
        description="Get trade history with optional filters by symbol, strategy, and date range",
        category=ToolCategory.PORTFOLIO,
        side_effect=ToolSideEffect.READ,
        timeout_ms=3000,
        cache_ttl_s=30,
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Filter by ticker symbol"},
                "strategy_tag": {"type": "string", "description": "Filter by strategy tag"},
                "start_date": {"type": "string", "description": "Start date (ISO format)"},
                "end_date": {"type": "string", "description": "End date (ISO format)"},
                "limit": {"type": "integer", "description": "Max trades to return", "default": 50},
            },
        },
        output_schema={"type": "object"},
        handler=_get_trade_history,
    ))

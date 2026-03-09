"""Trade analytics service — aggregate queries on cerberus_trades."""
from __future__ import annotations

from datetime import datetime, date
from typing import Optional

import structlog
from sqlalchemy import select, func, desc, asc, case, extract

from db.database import get_session

logger = structlog.get_logger(__name__)


class TradeAnalyticsService:
    """Provides async analytics queries on cerberus_trades, scoped by user_id."""

    async def get_best_trade(
        self,
        user_id: int,
        symbol: Optional[str] = None,
        strategy_tag: Optional[str] = None,
    ) -> dict:
        """Return the single trade with the highest return_pct."""
        from db.cerberus_models import CerberusTrade

        async with get_session() as session:
            stmt = (
                select(CerberusTrade)
                .where(CerberusTrade.user_id == user_id)
            )
            if symbol:
                stmt = stmt.where(CerberusTrade.symbol == symbol)
            if strategy_tag:
                stmt = stmt.where(CerberusTrade.strategy_tag == strategy_tag)
            stmt = stmt.order_by(desc(CerberusTrade.return_pct)).limit(1)

            result = await session.execute(stmt)
            trade = result.scalar_one_or_none()

        if not trade:
            return {"message": "No trades found"}

        return _trade_to_dict(trade)

    async def get_worst_trades(
        self,
        user_id: int,
        limit: int = 5,
    ) -> list[dict]:
        """Return the N trades with the lowest return_pct."""
        from db.cerberus_models import CerberusTrade

        async with get_session() as session:
            stmt = (
                select(CerberusTrade)
                .where(CerberusTrade.user_id == user_id)
                .order_by(asc(CerberusTrade.return_pct))
                .limit(limit)
            )
            result = await session.execute(stmt)
            trades = result.scalars().all()

        return [_trade_to_dict(t) for t in trades]

    async def get_total_volume(
        self,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """Return total traded volume (SUM of quantity * entry_price)."""
        from db.cerberus_models import CerberusTrade

        async with get_session() as session:
            volume_expr = func.sum(CerberusTrade.quantity * CerberusTrade.entry_price)
            count_expr = func.count()

            stmt = (
                select(volume_expr.label("total_volume"), count_expr.label("trade_count"))
                .where(CerberusTrade.user_id == user_id)
            )
            if start_date:
                stmt = stmt.where(CerberusTrade.entry_ts >= datetime.combine(start_date, datetime.min.time()))
            if end_date:
                stmt = stmt.where(CerberusTrade.entry_ts <= datetime.combine(end_date, datetime.max.time()))

            result = await session.execute(stmt)
            row = result.one()

        return {
            "total_volume": round(float(row.total_volume or 0), 2),
            "trade_count": row.trade_count or 0,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        }

    async def get_strategy_performance(
        self,
        user_id: int,
        strategy_tag: Optional[str] = None,
    ) -> list[dict]:
        """Return performance grouped by strategy_tag."""
        from db.cerberus_models import CerberusTrade

        async with get_session() as session:
            stmt = (
                select(
                    CerberusTrade.strategy_tag,
                    func.count().label("trade_count"),
                    func.avg(CerberusTrade.return_pct).label("avg_return_pct"),
                    func.sum(CerberusTrade.net_pnl).label("total_net_pnl"),
                    func.sum(
                        case(
                            (CerberusTrade.return_pct > 0, 1),
                            else_=0,
                        )
                    ).label("win_count"),
                )
                .where(CerberusTrade.user_id == user_id)
                .group_by(CerberusTrade.strategy_tag)
            )
            if strategy_tag:
                stmt = stmt.where(CerberusTrade.strategy_tag == strategy_tag)

            result = await session.execute(stmt)
            rows = result.all()

        return [
            {
                "strategy_tag": row.strategy_tag or "untagged",
                "trade_count": row.trade_count,
                "avg_return_pct": round(float(row.avg_return_pct or 0), 4),
                "total_net_pnl": round(float(row.total_net_pnl or 0), 2),
                "win_rate": round(row.win_count / row.trade_count, 4) if row.trade_count else 0,
            }
            for row in rows
        ]

    async def get_symbol_performance(
        self,
        user_id: int,
        symbol: Optional[str] = None,
    ) -> list[dict]:
        """Return performance grouped by symbol."""
        from db.cerberus_models import CerberusTrade

        async with get_session() as session:
            stmt = (
                select(
                    CerberusTrade.symbol,
                    func.count().label("trade_count"),
                    func.avg(CerberusTrade.return_pct).label("avg_return_pct"),
                    func.sum(CerberusTrade.net_pnl).label("total_net_pnl"),
                    func.sum(CerberusTrade.quantity * CerberusTrade.entry_price).label("total_volume"),
                    func.sum(
                        case(
                            (CerberusTrade.return_pct > 0, 1),
                            else_=0,
                        )
                    ).label("win_count"),
                )
                .where(CerberusTrade.user_id == user_id)
                .group_by(CerberusTrade.symbol)
            )
            if symbol:
                stmt = stmt.where(CerberusTrade.symbol == symbol)

            result = await session.execute(stmt)
            rows = result.all()

        return [
            {
                "symbol": row.symbol,
                "trade_count": row.trade_count,
                "avg_return_pct": round(float(row.avg_return_pct or 0), 4),
                "total_net_pnl": round(float(row.total_net_pnl or 0), 2),
                "total_volume": round(float(row.total_volume or 0), 2),
                "win_rate": round(row.win_count / row.trade_count, 4) if row.trade_count else 0,
            }
            for row in rows
        ]

    async def get_hold_time_stats(self, user_id: int) -> dict:
        """Return average hold time statistics (exit_ts - entry_ts)."""
        from db.cerberus_models import CerberusTrade

        async with get_session() as session:
            # Fetch all trades with both entry and exit timestamps
            stmt = (
                select(CerberusTrade.entry_ts, CerberusTrade.exit_ts)
                .where(
                    CerberusTrade.user_id == user_id,
                    CerberusTrade.entry_ts.isnot(None),
                    CerberusTrade.exit_ts.isnot(None),
                )
            )
            result = await session.execute(stmt)
            rows = result.all()

        if not rows:
            return {"avg_hold_seconds": 0, "avg_hold_hours": 0, "trade_count": 0, "message": "No closed trades found"}

        total_seconds = 0.0
        count = 0
        for entry_ts, exit_ts in rows:
            delta = (exit_ts - entry_ts).total_seconds()
            if delta >= 0:
                total_seconds += delta
                count += 1

        if count == 0:
            return {"avg_hold_seconds": 0, "avg_hold_hours": 0, "trade_count": 0}

        avg_seconds = total_seconds / count
        return {
            "avg_hold_seconds": round(avg_seconds, 1),
            "avg_hold_hours": round(avg_seconds / 3600, 2),
            "avg_hold_days": round(avg_seconds / 86400, 2),
            "trade_count": count,
        }

    async def get_bot_performance(self, bot_id: str) -> dict:
        """Return performance stats for a specific bot."""
        from db.cerberus_models import CerberusTrade

        async with get_session() as session:
            stmt = (
                select(
                    func.count().label("trade_count"),
                    func.avg(CerberusTrade.return_pct).label("avg_return_pct"),
                    func.sum(CerberusTrade.net_pnl).label("total_net_pnl"),
                    func.sum(CerberusTrade.gross_pnl).label("total_gross_pnl"),
                    func.sum(CerberusTrade.quantity * CerberusTrade.entry_price).label("total_volume"),
                    func.sum(
                        case(
                            (CerberusTrade.return_pct > 0, 1),
                            else_=0,
                        )
                    ).label("win_count"),
                )
                .where(CerberusTrade.bot_id == bot_id)
            )
            result = await session.execute(stmt)
            row = result.one()

        trade_count = row.trade_count or 0
        return {
            "bot_id": bot_id,
            "trade_count": trade_count,
            "avg_return_pct": round(float(row.avg_return_pct or 0), 4),
            "total_net_pnl": round(float(row.total_net_pnl or 0), 2),
            "total_gross_pnl": round(float(row.total_gross_pnl or 0), 2),
            "total_volume": round(float(row.total_volume or 0), 2),
            "win_rate": round(row.win_count / trade_count, 4) if trade_count else 0,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trade_to_dict(trade) -> dict:
    """Convert a CerberusTrade ORM instance to a plain dict."""
    return {
        "id": trade.id,
        "symbol": trade.symbol,
        "side": trade.side,
        "asset_type": trade.asset_type,
        "entry_ts": trade.entry_ts.isoformat() if trade.entry_ts else None,
        "exit_ts": trade.exit_ts.isoformat() if trade.exit_ts else None,
        "entry_price": trade.entry_price,
        "exit_price": trade.exit_price,
        "quantity": trade.quantity,
        "gross_pnl": trade.gross_pnl,
        "net_pnl": trade.net_pnl,
        "return_pct": trade.return_pct,
        "strategy_tag": trade.strategy_tag,
        "bot_id": trade.bot_id,
        "notes": trade.notes,
    }


# ---------------------------------------------------------------------------
# Materialized view SQL (constants — executed by migration or worker)
# ---------------------------------------------------------------------------

MATERIALIZED_VIEW_SQL: dict[str, str] = {
    "mv_trade_stats_by_symbol": """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_trade_stats_by_symbol AS
        SELECT
            user_id,
            symbol,
            COUNT(*) AS trade_count,
            AVG(return_pct) AS avg_return_pct,
            SUM(net_pnl) AS total_net_pnl,
            SUM(gross_pnl) AS total_gross_pnl,
            SUM(quantity * entry_price) AS total_volume,
            SUM(CASE WHEN return_pct > 0 THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) AS win_rate,
            MIN(entry_ts) AS first_trade,
            MAX(entry_ts) AS last_trade
        FROM cerberus_trades
        GROUP BY user_id, symbol;
    """,
    "mv_trade_stats_by_strategy": """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_trade_stats_by_strategy AS
        SELECT
            user_id,
            COALESCE(strategy_tag, 'untagged') AS strategy_tag,
            COUNT(*) AS trade_count,
            AVG(return_pct) AS avg_return_pct,
            SUM(net_pnl) AS total_net_pnl,
            SUM(gross_pnl) AS total_gross_pnl,
            SUM(CASE WHEN return_pct > 0 THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) AS win_rate,
            MIN(entry_ts) AS first_trade,
            MAX(entry_ts) AS last_trade
        FROM cerberus_trades
        GROUP BY user_id, strategy_tag;
    """,
    "mv_trade_stats_by_day": """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_trade_stats_by_day AS
        SELECT
            user_id,
            DATE(entry_ts) AS trade_date,
            COUNT(*) AS trade_count,
            AVG(return_pct) AS avg_return_pct,
            SUM(net_pnl) AS total_net_pnl,
            SUM(quantity * entry_price) AS total_volume
        FROM cerberus_trades
        WHERE entry_ts IS NOT NULL
        GROUP BY user_id, DATE(entry_ts);
    """,
    "mv_bot_performance": """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_bot_performance AS
        SELECT
            bot_id,
            COUNT(*) AS trade_count,
            AVG(return_pct) AS avg_return_pct,
            SUM(net_pnl) AS total_net_pnl,
            SUM(gross_pnl) AS total_gross_pnl,
            SUM(quantity * entry_price) AS total_volume,
            SUM(CASE WHEN return_pct > 0 THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) AS win_rate,
            MIN(entry_ts) AS first_trade,
            MAX(entry_ts) AS last_trade
        FROM cerberus_trades
        WHERE bot_id IS NOT NULL
        GROUP BY bot_id;
    """,
}

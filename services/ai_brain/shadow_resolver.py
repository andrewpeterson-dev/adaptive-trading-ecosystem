"""
Shadow P&L Resolver — background task that resolves shadow model decisions
via mark-to-market pricing for the model comparison leaderboard.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import structlog
from sqlalchemy import select, and_

from db.database import get_session

logger = structlog.get_logger(__name__)

RESOLVE_INTERVAL = 300  # 5 minutes
# Shadow decisions are resolved after this duration if not resolved by
# the primary model's corresponding position closing first
MAX_SHADOW_AGE_MINUTES = 60


async def shadow_resolver_loop() -> None:
    """Background loop that resolves unresolved shadow decisions."""
    while True:
        try:
            await _resolve_shadows()
        except Exception as e:
            logger.error("shadow_resolver_error", error=str(e))
        await asyncio.sleep(RESOLVE_INTERVAL)


async def _resolve_shadows() -> None:
    """Find unresolved shadow BUY/SELL decisions and mark-to-market."""
    from db.cerberus_models import BotModelPerformance

    cutoff = datetime.utcnow() - timedelta(minutes=MAX_SHADOW_AGE_MINUTES)

    async with get_session() as session:
        result = await session.execute(
            select(BotModelPerformance).where(
                and_(
                    BotModelPerformance.is_shadow == True,  # noqa: E712
                    BotModelPerformance.resolved_at.is_(None),
                    BotModelPerformance.action.in_(["BUY", "SELL"]),
                    BotModelPerformance.decided_at <= cutoff,
                    BotModelPerformance.entry_price.isnot(None),
                    BotModelPerformance.entry_price > 0,
                )
            )
        )
        unresolved = result.scalars().all()

        if not unresolved:
            return

        logger.info("shadow_resolver_found", count=len(unresolved))

        for perf in unresolved:
            try:
                current_price = await _get_current_price(perf.symbol)
                if current_price is None or current_price <= 0:
                    continue

                # Calculate P&L based on direction
                direction = 1.0 if perf.action == "BUY" else -1.0
                pnl = (current_price - perf.entry_price) * direction

                perf.exit_price = current_price
                perf.pnl = round(pnl, 4)
                perf.resolved_at = datetime.utcnow()
                await session.flush()

                logger.info(
                    "shadow_resolved",
                    perf_id=perf.id,
                    symbol=perf.symbol,
                    model=perf.model_used,
                    pnl=perf.pnl,
                )
            except Exception as e:
                logger.error(
                    "shadow_resolve_single_error",
                    perf_id=perf.id,
                    error=str(e),
                )


async def _get_current_price(symbol: str) -> float | None:
    """Fetch current price for a symbol."""
    try:
        from services.market_data import get_quote

        quote = await get_quote(symbol)
        if quote and "price" in quote:
            return float(quote["price"])
    except Exception:
        pass

    # Fallback: try yfinance
    try:
        import yfinance as yf
        from concurrent.futures import ThreadPoolExecutor
        import asyncio

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            ticker = await loop.run_in_executor(pool, lambda: yf.Ticker(symbol))
            info = await loop.run_in_executor(pool, lambda: ticker.info)
            return float(info.get("regularMarketPrice", 0) or 0)
    except Exception:
        return None

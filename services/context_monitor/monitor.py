"""Context Monitor — background service aggregating market intelligence."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select, and_

from db.database import get_session
from db.cerberus_models import MarketEvent
from services.context_monitor.classifier import classify_impact

logger = structlog.get_logger(__name__)
_ET = ZoneInfo("America/New_York")


class ContextMonitor:
    """Background loop polling market data sources and storing MarketEvents."""

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("context_monitor_started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("context_monitor_stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                interval = self._get_interval()
                await self._poll_sources()
                await self._expire_events()
            except Exception as e:
                logger.error("context_monitor_error", error=str(e))
                interval = 120
            await asyncio.sleep(interval)

    def _get_interval(self) -> int:
        now = datetime.now(_ET)
        market_open = dtime(9, 0)
        market_close = dtime(16, 30)
        if now.weekday() < 5 and market_open <= now.time() <= market_close:
            return 120  # 2 min during market hours
        return 900  # 15 min outside hours

    async def _poll_sources(self) -> None:
        from services.context_monitor.sources.vix import fetch_vix_events
        from services.context_monitor.sources.cnn_fear_greed import fetch_fear_greed_events
        from services.context_monitor.sources.finnhub_news import fetch_finnhub_news_events
        from services.context_monitor.sources.finnhub_calendar import fetch_earnings_events, fetch_economic_events
        from services.context_monitor.sources.stocktwits import fetch_stocktwits_events
        from services.context_monitor.sources.sector_etfs import fetch_sector_events
        from services.context_monitor.sources.yfinance_news import fetch_yfinance_news_events

        fetchers = [
            fetch_vix_events,
            fetch_fear_greed_events,
            fetch_finnhub_news_events,
            fetch_yfinance_news_events,
            fetch_earnings_events,
            fetch_economic_events,
            fetch_stocktwits_events,
            fetch_sector_events,
        ]

        results = await asyncio.gather(*[f() for f in fetchers], return_exceptions=True)
        all_events = []
        for r in results:
            if isinstance(r, list):
                all_events.extend(r)
            elif isinstance(r, Exception):
                logger.warning("source_fetch_exception", error=str(r))

        if all_events:
            await self._store_events(all_events)
            logger.info("context_monitor_poll_complete", events_found=len(all_events))

    async def _store_events(self, events: list[dict]) -> None:
        async with get_session() as session:
            for evt in events:
                source_id = evt.get("source_id", "")
                if not source_id:
                    continue

                existing = await session.execute(
                    select(MarketEvent.id).where(MarketEvent.source_id == source_id).limit(1)
                )
                if existing.scalar_one_or_none():
                    continue

                evt["impact"] = classify_impact(evt)

                record = MarketEvent(
                    id=str(uuid.uuid4()),
                    event_type=evt.get("event_type", "unknown"),
                    impact=evt["impact"],
                    symbols=evt.get("symbols", []),
                    sectors=evt.get("sectors", []),
                    headline=evt.get("headline", "")[:512],
                    raw_data=evt.get("raw_data", {}),
                    source=evt.get("source", "unknown"),
                    source_id=source_id,
                    user_id=evt.get("user_id"),
                    detected_at=datetime.utcnow(),
                    expires_at=evt.get("expires_at"),
                )
                session.add(record)

    async def _expire_events(self) -> None:
        now = datetime.utcnow()
        async with get_session() as session:
            result = await session.execute(
                select(MarketEvent).where(
                    and_(MarketEvent.expires_at.isnot(None), MarketEvent.expires_at < now)
                )
            )
            expired = result.scalars().all()
            for evt in expired:
                await session.delete(evt)
            if expired:
                logger.info("context_monitor_expired_events", count=len(expired))

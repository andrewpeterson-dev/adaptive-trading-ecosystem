"""Backward-compatible shim: drop-in replacement for the old ActivityBus.

``ActivityBusCompat`` exposes the exact same synchronous
``subscribe`` / ``publish`` / ``unsubscribe`` interface that the rest of
the codebase already uses, but routes events through the Redis-backed
``SignalBus`` under the hood.

Migration path:
  1. Replace ``from services.activity_bus import activity_bus``
     with    ``from services.signal_bus import activity_bus``
  2. Everything else keeps working.  Gradually move callers to the
     native ``SignalBus`` async API at your own pace.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

import structlog

from services.activity_bus import BotActivityEvent
from services.signal_bus.bus import SignalBus, get_signal_bus
from services.signal_bus.events import CHANNEL_BOT_ACTIVITY

logger = structlog.get_logger(__name__)


class ActivityBusCompat:
    """Drop-in replacement for ``ActivityBus`` backed by ``SignalBus``.

    The old interface is fully synchronous (``publish`` is not a coroutine,
    ``subscribe`` returns an ``asyncio.Queue``).  This shim preserves that
    contract while funnelling events through Redis when available.

    Key differences from the original:
      - Events also flow through Redis so other worker processes see them.
      - If Redis is down the fallback in-process path is still used, so
        behaviour is identical to the original ``ActivityBus``.
    """

    def __init__(self, bus: SignalBus | None = None) -> None:
        self._bus: SignalBus | None = bus
        # user_id -> list[asyncio.Queue]  (mirrors original ActivityBus)
        self._subscribers: dict[int, list[asyncio.Queue]] = defaultdict(list)

    @property
    def bus(self) -> SignalBus:
        if self._bus is None:
            self._bus = get_signal_bus()
        return self._bus

    # ── Public interface (matches original ActivityBus) ──────────────────

    def subscribe(self, user_id: int) -> asyncio.Queue:
        """Create a subscription queue for *user_id*. Returns the queue."""
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers[user_id].append(q)
        return q

    def unsubscribe(self, user_id: int, q: asyncio.Queue) -> None:
        """Remove a subscription queue."""
        queues = self._subscribers.get(user_id, [])
        try:
            queues.remove(q)
        except ValueError:
            pass
        if not queues:
            self._subscribers.pop(user_id, None)

    def publish(self, event: BotActivityEvent) -> None:
        """Publish an event to all local subscribers *and* to Redis.

        This method is intentionally synchronous to match the old API.
        Redis publishing is fire-and-forget via ``create_task``.
        """
        if event.user_id is None:
            return

        # 1. Deliver to local in-process subscribers (instant, same as before)
        for q in self._subscribers.get(event.user_id, []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

        # 2. Also publish through SignalBus (Redis) for cross-process delivery
        try:
            self.bus.publish_and_forget(
                CHANNEL_BOT_ACTIVITY,
                {
                    "event_type": event.event_type,
                    "bot_id": event.bot_id,
                    "bot_name": event.bot_name,
                    "symbol": event.symbol,
                    "headline": event.headline,
                    "detail": event.detail,
                    "timestamp": event.timestamp,
                    "user_id": event.user_id,
                },
                user_id=event.user_id,
            )
        except Exception as exc:
            # Never let Redis issues break event delivery
            logger.debug("compat_redis_publish_failed", error=str(exc))

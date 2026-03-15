"""In-process event bus for bot activity and safety alerts.

Components publish events (safety interventions, trade executions, etc.)
and the WebSocket handler subscribes per-user to forward them to the frontend.

This is a lightweight asyncio-based bus — no Redis required.
Events are fire-and-forget; missed events (disconnected clients) are dropped.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class BotActivityEvent:
    """A single bot activity or safety event."""

    event_type: str  # "safety_block", "safety_reduce", "trade_executed", "trade_delayed", "bot_paused", "candidate_found"
    bot_id: str
    bot_name: str
    symbol: str | None = None
    headline: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    user_id: int | None = None  # Set so we only push to the right user


class ActivityBus:
    """Simple pub/sub for bot activity events scoped by user_id."""

    def __init__(self) -> None:
        # user_id → list of asyncio.Queue
        self._subscribers: dict[int, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, user_id: int) -> asyncio.Queue:
        """Create a subscription queue for a user. Returns the queue."""
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
        """Publish an event to all subscribers for the event's user_id."""
        if event.user_id is None:
            return
        for q in self._subscribers.get(event.user_id, []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest to make room
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass


# Singleton instance used across the app
activity_bus = ActivityBus()

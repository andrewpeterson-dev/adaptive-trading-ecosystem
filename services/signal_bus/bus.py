"""Redis Pub/Sub event bus for cross-process communication.

Supports multiple event channels:
  - bot_activity:     Bot actions, safety events, trade executions
  - market_signals:   Price alerts, regime changes, event triggers
  - risk_alerts:      Risk limit breaches, circuit breaker activations

Falls back to in-process asyncio.Queue when Redis is unavailable so the
app never crashes due to a missing or flaky Redis connection.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime
from typing import Any, AsyncIterator

import structlog

from config.settings import get_settings
from services.activity_bus import BotActivityEvent
from services.signal_bus.events import (
    CHANNEL_BOT_ACTIVITY,
)

try:
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover
    aioredis = None  # type: ignore[assignment]

logger = structlog.get_logger(__name__)

# How long to wait before retrying a failed Redis connection
_RECONNECT_DELAY_SECONDS = 5.0
# Maximum number of events buffered per in-process fallback queue
_FALLBACK_QUEUE_MAXSIZE = 500


def _channel_key(channel: str, user_id: int | None = None) -> str:
    """Build the Redis channel key.

    ``signal:{channel}:{user_id}`` for user-scoped channels,
    ``signal:{channel}:global`` for broadcast.
    """
    suffix = str(user_id) if user_id is not None else "global"
    return f"signal:{channel}:{suffix}"


class SignalBus:
    """Redis-backed event bus with automatic in-process fallback.

    Usage::

        bus = SignalBus()
        await bus.connect()

        # publish
        await bus.publish("risk_alerts", {"level": "high"}, user_id=2)

        # subscribe (async generator)
        async for event in bus.subscribe("risk_alerts", user_id=2):
            print(event)

        await bus.disconnect()
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url: str = redis_url or get_settings().redis_url
        self._redis: Any | None = None  # redis.asyncio client
        self._pubsub_clients: list[Any] = []
        self._connected: bool = False
        self._use_fallback: bool = False

        # In-process fallback state (mirrors old ActivityBus)
        self._fallback_queues: dict[str, list[asyncio.Queue]] = defaultdict(list)

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Initialize the Redis connection.  Sets ``_use_fallback`` on failure."""
        if aioredis is None:
            logger.warning("signal_bus_no_redis_lib", msg="redis.asyncio not installed, using fallback")
            self._use_fallback = True
            return

        try:
            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                retry_on_timeout=True,
            )
            # Verify connectivity
            await self._redis.ping()
            self._connected = True
            self._use_fallback = False
            logger.info("signal_bus_connected", redis_url=self._redacted_url)
        except Exception as exc:
            logger.warning(
                "signal_bus_redis_unavailable",
                error=str(exc),
                msg="falling back to in-process queues",
            )
            self._redis = None
            self._connected = False
            self._use_fallback = True

    async def disconnect(self) -> None:
        """Clean up all Redis connections and pubsub listeners."""
        for ps in self._pubsub_clients:
            try:
                await ps.unsubscribe()
                await ps.aclose()
            except Exception:
                pass
        self._pubsub_clients.clear()

        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None

        self._connected = False
        logger.info("signal_bus_disconnected")

    # ── Publishing ───────────────────────────────────────────────────────

    async def publish(
        self,
        channel: str,
        event: dict[str, Any],
        user_id: int | None = None,
    ) -> None:
        """Publish *event* to *channel*.

        If *user_id* is specified the event is scoped to that user's
        channel key; otherwise it goes to the global channel.
        """
        envelope = {
            "event_type": event.get("event_type", "unknown"),
            "channel": channel,
            "user_id": user_id,
            "payload": event,
            "timestamp": event.get("timestamp") or datetime.utcnow().isoformat(),
        }

        if self._use_fallback or not self._connected:
            self._publish_fallback(channel, user_id, envelope)
            return

        key = _channel_key(channel, user_id)
        try:
            await self._redis.publish(key, json.dumps(envelope))
        except Exception as exc:
            logger.warning("signal_bus_publish_failed", channel=key, error=str(exc))
            await self._handle_redis_failure()
            # Still deliver locally so the current process sees the event
            self._publish_fallback(channel, user_id, envelope)

    def publish_and_forget(
        self,
        channel: str,
        event: dict[str, Any],
        user_id: int | None = None,
    ) -> None:
        """Fire-and-forget publish — wraps ``publish`` in ``create_task``.

        Safe to call from sync-ish contexts that have a running event loop.
        Errors are logged, never raised.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._safe_publish(channel, event, user_id))
        except RuntimeError:
            # No running event loop — publish to fallback directly
            envelope = {
                "event_type": event.get("event_type", "unknown"),
                "channel": channel,
                "user_id": user_id,
                "payload": event,
                "timestamp": event.get("timestamp") or datetime.utcnow().isoformat(),
            }
            self._publish_fallback(channel, user_id, envelope)

    async def publish_bot_activity(self, event: BotActivityEvent) -> None:
        """Convenience: publish a ``BotActivityEvent`` (backward-compat).

        Translates the legacy dataclass into the signal bus envelope and
        publishes to ``bot_activity:{user_id}``.
        """
        payload = {
            "event_type": event.event_type,
            "bot_id": event.bot_id,
            "bot_name": event.bot_name,
            "symbol": event.symbol,
            "headline": event.headline,
            "detail": event.detail,
            "timestamp": event.timestamp,
            "user_id": event.user_id,
        }
        await self.publish(CHANNEL_BOT_ACTIVITY, payload, user_id=event.user_id)

    # ── Subscribing ──────────────────────────────────────────────────────

    async def subscribe(
        self,
        channel: str,
        user_id: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to *channel* and yield events as dicts.

        This is an async generator — use ``async for event in bus.subscribe(...)``.
        The generator handles Redis disconnections gracefully by switching to
        the in-process fallback and attempting reconnection in the background.
        """
        if self._use_fallback or not self._connected:
            async for event in self._subscribe_fallback(channel, user_id):
                yield event
            return

        key = _channel_key(channel, user_id)
        pubsub = self._redis.pubsub()
        self._pubsub_clients.append(pubsub)
        try:
            await pubsub.subscribe(key)
            while True:
                try:
                    msg = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=2.0,
                    )
                    if msg is not None and msg["type"] == "message":
                        try:
                            data = json.loads(msg["data"])
                            yield data
                        except (json.JSONDecodeError, TypeError):
                            logger.debug("signal_bus_bad_message", raw=msg["data"])
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning("signal_bus_subscribe_error", channel=key, error=str(exc))
                    await self._handle_redis_failure()
                    # Fall through to fallback
                    async for event in self._subscribe_fallback(channel, user_id):
                        yield event
                    return
        except asyncio.CancelledError:
            pass
        finally:
            try:
                await pubsub.unsubscribe(key)
                await pubsub.aclose()
            except Exception:
                pass
            try:
                self._pubsub_clients.remove(pubsub)
            except ValueError:
                pass

    async def subscribe_bot_activity(
        self,
        user_id: int,
    ) -> AsyncIterator[dict[str, Any]]:
        """Convenience: subscribe to bot activity for a specific user."""
        async for event in self.subscribe(CHANNEL_BOT_ACTIVITY, user_id=user_id):
            yield event

    # ── In-process fallback ──────────────────────────────────────────────

    def _publish_fallback(
        self,
        channel: str,
        user_id: int | None,
        envelope: dict[str, Any],
    ) -> None:
        """Deliver event to all in-process fallback queues for this channel/user."""
        key = _channel_key(channel, user_id)
        for q in self._fallback_queues.get(key, []):
            try:
                q.put_nowait(envelope)
            except asyncio.QueueFull:
                # Drop oldest to make room
                try:
                    q.get_nowait()
                    q.put_nowait(envelope)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

    async def _subscribe_fallback(
        self,
        channel: str,
        user_id: int | None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield events from an in-process asyncio.Queue (fallback mode)."""
        key = _channel_key(channel, user_id)
        q: asyncio.Queue = asyncio.Queue(maxsize=_FALLBACK_QUEUE_MAXSIZE)
        self._fallback_queues[key].append(q)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=2.0)
                    yield event
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    return
        finally:
            try:
                self._fallback_queues[key].remove(q)
            except ValueError:
                pass
            if not self._fallback_queues[key]:
                self._fallback_queues.pop(key, None)

    # ── Reconnection ─────────────────────────────────────────────────────

    async def _handle_redis_failure(self) -> None:
        """Switch to fallback and schedule a background reconnect attempt."""
        if self._use_fallback:
            return  # already in fallback mode
        self._connected = False
        self._use_fallback = True
        logger.warning("signal_bus_switched_to_fallback")
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._reconnect_loop())
        except RuntimeError:
            pass

    async def _reconnect_loop(self, max_attempts: int = 60) -> None:
        """Periodically try to re-establish the Redis connection."""
        attempt = 0
        while self._use_fallback and attempt < max_attempts:
            attempt += 1
            await asyncio.sleep(_RECONNECT_DELAY_SECONDS)
            try:
                if self._redis is not None:
                    try:
                        await self._redis.aclose()
                    except Exception:
                        pass

                self._redis = aioredis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                )
                await self._redis.ping()
                self._connected = True
                self._use_fallback = False
                logger.info("signal_bus_reconnected", attempts=attempt)
                return
            except Exception as exc:
                logger.debug("signal_bus_reconnect_failed", attempt=attempt, error=str(exc))
        if self._use_fallback:
            logger.warning("signal_bus_reconnect_exhausted", max_attempts=max_attempts)

    # ── Helpers ──────────────────────────────────────────────────────────

    async def _safe_publish(
        self,
        channel: str,
        event: dict[str, Any],
        user_id: int | None,
    ) -> None:
        """Wrapper for ``publish`` that swallows all exceptions."""
        try:
            await self.publish(channel, event, user_id)
        except Exception as exc:
            logger.debug("signal_bus_safe_publish_error", error=str(exc))

    @property
    def _redacted_url(self) -> str:
        """Redis URL with password masked for logging."""
        url = self._redis_url
        if "@" in url:
            prefix, rest = url.rsplit("@", 1)
            scheme_end = prefix.find("://")
            if scheme_end != -1:
                return f"{prefix[:scheme_end + 3]}***@{rest}"
        return url

    @property
    def is_connected(self) -> bool:
        """Whether the bus is connected to Redis (vs. using fallback)."""
        return self._connected and not self._use_fallback


# ── Module-level singleton ───────────────────────────────────────────────────

_signal_bus: SignalBus | None = None


def get_signal_bus() -> SignalBus:
    """Return the module-level SignalBus singleton (creates if needed).

    The bus is *not* connected until ``await bus.connect()`` is called —
    typically in the FastAPI lifespan or startup event.
    """
    global _signal_bus
    if _signal_bus is None:
        _signal_bus = SignalBus()
    return _signal_bus

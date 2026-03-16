"""Standardized event types and schema for the signal bus.

All events flowing through the SignalBus use SignalEvent as their
canonical representation.  The EventType enum covers known event types
but the bus accepts arbitrary strings for forward-compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Known event types grouped by channel."""

    # ── Bot activity ─────────────────────────────────────────────────────
    TRADE_EXECUTED = "trade_executed"
    TRADE_DELAYED = "trade_delayed"
    TRADE_BLOCKED = "trade_blocked"
    POSITION_CLOSED = "position_closed"
    BOT_PAUSED = "bot_paused"
    BOT_RESUMED = "bot_resumed"
    CANDIDATE_FOUND = "candidate_found"
    SAFETY_BLOCK = "safety_block"
    SAFETY_REDUCE = "safety_reduce"

    # ── Market signals ───────────────────────────────────────────────────
    PRICE_ALERT = "price_alert"
    REGIME_CHANGE = "regime_change"
    VIX_SPIKE = "vix_spike"
    EARNINGS_ALERT = "earnings_alert"

    # ── Risk alerts ──────────────────────────────────────────────────────
    STOP_LOSS_HIT = "stop_loss_hit"
    DRAWDOWN_WARNING = "drawdown_warning"
    EXPOSURE_LIMIT = "exposure_limit"
    CIRCUIT_BREAKER = "circuit_breaker"
    KILL_SWITCH = "kill_switch"


# Canonical channel names
CHANNEL_BOT_ACTIVITY = "bot_activity"
CHANNEL_MARKET_SIGNALS = "market_signals"
CHANNEL_RISK_ALERTS = "risk_alerts"


@dataclass
class SignalEvent:
    """Canonical event for the signal bus.

    Attributes:
        event_type: An EventType member or any string for custom events.
        channel:    Logical channel name (bot_activity, market_signals, risk_alerts).
        user_id:    If set, the event is scoped to this user.
        bot_id:     Originating bot, if applicable.
        symbol:     Ticker symbol, if applicable.
        headline:   Human-readable one-liner for the UI.
        payload:    Arbitrary structured data for consumers.
        timestamp:  ISO-8601 string, auto-generated if omitted.
    """

    event_type: EventType | str
    channel: str = CHANNEL_BOT_ACTIVITY
    user_id: int | None = None
    bot_id: str | None = None
    symbol: str | None = None
    headline: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # ── Serialization ────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict for Redis transport."""
        return {
            "event_type": self.event_type.value if isinstance(self.event_type, Enum) else self.event_type,
            "channel": self.channel,
            "user_id": self.user_id,
            "bot_id": self.bot_id,
            "symbol": self.symbol,
            "headline": self.headline,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SignalEvent:
        """Deserialize from a dict (e.g. received over Redis)."""
        raw_type = data.get("event_type", "")
        try:
            event_type: EventType | str = EventType(raw_type)
        except ValueError:
            event_type = raw_type
        return cls(
            event_type=event_type,
            channel=data.get("channel", CHANNEL_BOT_ACTIVITY),
            user_id=data.get("user_id"),
            bot_id=data.get("bot_id"),
            symbol=data.get("symbol"),
            headline=data.get("headline", ""),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
        )

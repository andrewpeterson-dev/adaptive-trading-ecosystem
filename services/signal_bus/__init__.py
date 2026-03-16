"""Redis-backed signal bus for cross-process event communication.

Quick start::

    from services.signal_bus import get_signal_bus, SignalBus

    bus = get_signal_bus()
    await bus.connect()
    await bus.publish("risk_alerts", {"level": "high"}, user_id=2)

Backward-compatible drop-in for the old ``ActivityBus``::

    from services.signal_bus import activity_bus   # same interface as before
    activity_bus.publish(BotActivityEvent(...))
"""

from services.signal_bus.bus import SignalBus, get_signal_bus
from services.signal_bus.compat import ActivityBusCompat
from services.signal_bus.events import (
    CHANNEL_BOT_ACTIVITY,
    CHANNEL_MARKET_SIGNALS,
    CHANNEL_RISK_ALERTS,
    EventType,
    SignalEvent,
)

# Module-level compat instance — same interface as the old activity_bus singleton
activity_bus = ActivityBusCompat()

__all__ = [
    "SignalBus",
    "get_signal_bus",
    "ActivityBusCompat",
    "activity_bus",
    "SignalEvent",
    "EventType",
    "CHANNEL_BOT_ACTIVITY",
    "CHANNEL_MARKET_SIGNALS",
    "CHANNEL_RISK_ALERTS",
]

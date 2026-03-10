"""System event logger — records critical actions for audit trail."""

from __future__ import annotations

from typing import Optional

import structlog
from db.database import get_session
from db.models import SystemEvent, SystemEventType, TradingModeEnum

logger = structlog.get_logger(__name__)


async def log_event(
    user_id: int,
    event_type: SystemEventType,
    mode: TradingModeEnum,
    description: str = "",
    severity: str = "info",
    metadata: Optional[dict] = None,
) -> None:
    """Write a system event to the database. Fire-and-forget safe."""
    try:
        async with get_session() as db:
            db.add(SystemEvent(
                user_id=user_id,
                event_type=event_type,
                mode=mode,
                severity=severity,
                description=description,
                metadata_json=metadata or {},
            ))
        logger.info("system_event_logged", event_type=event_type.value, user_id=user_id)
    except Exception as exc:
        # Never let event logging crash the caller
        logger.error("system_event_log_failed", error=str(exc), event_type=event_type.value)

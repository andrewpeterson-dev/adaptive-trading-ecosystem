"""Broker factory -- returns a configured BrokerAdapter by name.

Caches instances by (broker_name, user_id, mode) so repeated calls within
the same process reuse the same connected client.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import structlog

from services.broker.base import BrokerAdapter

logger = structlog.get_logger(__name__)

_cache: dict[tuple[str, Optional[int], str], BrokerAdapter] = {}
_cache_lock = asyncio.Lock()


async def get_broker(
    broker_name: str = "alpaca",
    user_id: int | None = None,
    mode: str = "paper",
) -> BrokerAdapter:
    """Get a configured broker adapter by name.

    Parameters
    ----------
    broker_name : str
        ``"alpaca"`` or ``"webull"``.
    user_id : int | None
        Required for Webull (per-user encrypted credentials).  Ignored for
        Alpaca which uses global env-var keys.
    mode : str
        ``"paper"`` (default) or ``"live"``.

    Returns
    -------
    BrokerAdapter
        A connected adapter instance.  Cached by ``(broker_name, user_id, mode)``.
    """
    key = (broker_name.lower(), user_id, mode.lower())

    async with _cache_lock:
        if key in _cache:
            return _cache[key]

        adapter = await _build(broker_name, user_id, mode)
        await adapter.connect()
        _cache[key] = adapter
        logger.info(
            "broker_adapter_created",
            broker=broker_name,
            user_id=user_id,
            mode=mode,
        )
        return adapter


async def _build(broker_name: str, user_id: int | None, mode: str) -> BrokerAdapter:
    name = broker_name.lower()

    if name == "alpaca":
        from services.broker.alpaca_adapter import build_alpaca_adapter

        return build_alpaca_adapter(mode=mode)

    if name == "webull":
        return await _build_webull(user_id, mode)

    raise ValueError(f"Unknown broker: {broker_name!r}. Supported: alpaca, webull.")


async def _build_webull(user_id: int | None, mode: str) -> BrokerAdapter:
    """Build a WebullAdapter using encrypted credentials from the database."""
    if user_id is None:
        raise ValueError("Webull requires a user_id to look up encrypted credentials.")

    from sqlalchemy import select

    from db.database import get_session
    from db.encryption import decrypt_value
    from db.models import BrokerCredential, BrokerType
    from services.broker.webull_adapter import WebullAdapter

    async with get_session() as session:
        stmt = (
            select(BrokerCredential)
            .where(
                BrokerCredential.user_id == user_id,
                BrokerCredential.broker_type == BrokerType.WEBULL,
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        cred = result.scalar_one_or_none()

    if cred is None:
        raise LookupError(
            f"No Webull credentials found for user_id={user_id}. "
            "Store credentials via Settings > API Connections first."
        )

    app_key = decrypt_value(cred.encrypted_api_key)
    app_secret = decrypt_value(cred.encrypted_api_secret)

    return WebullAdapter(app_key=app_key, app_secret=app_secret, mode=mode)


async def close_broker(
    broker_name: str = "alpaca",
    user_id: int | None = None,
    mode: str = "paper",
) -> None:
    """Disconnect and remove a cached broker adapter."""
    key = (broker_name.lower(), user_id, mode.lower())
    async with _cache_lock:
        adapter = _cache.pop(key, None)
    if adapter is not None:
        await adapter.disconnect()
        logger.info("broker_adapter_closed", broker=broker_name, user_id=user_id, mode=mode)


async def close_all() -> None:
    """Disconnect every cached broker adapter. Call on shutdown."""
    async with _cache_lock:
        adapters = list(_cache.values())
        _cache.clear()
    for adapter in adapters:
        try:
            await adapter.disconnect()
        except Exception as exc:
            logger.warning("broker_disconnect_error", error=str(exc))
    logger.info("all_broker_adapters_closed", count=len(adapters))

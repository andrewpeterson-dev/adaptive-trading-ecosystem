"""Trading mode middleware — reads the user's active mode from DB, cached in-memory."""

from __future__ import annotations

import time
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy import select

from db.database import get_session
from db.models import UserTradingSession, TradingModeEnum

logger = structlog.get_logger(__name__)

# Paths that don't need trading mode
_SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}
_SKIP_PREFIXES = ("/api/auth/",)

# In-memory cache: user_id → (expires_at, mode)
_MODE_CACHE: dict[int, tuple[float, TradingModeEnum]] = {}
_CACHE_TTL = 15  # seconds


def invalidate_mode_cache(user_id: int | None = None) -> None:
    """Call this when user switches trading mode to bust the cache."""
    if user_id is None:
        _MODE_CACHE.clear()
    else:
        _MODE_CACHE.pop(user_id, None)


class TradingModeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip for unauthenticated / non-data paths
        path = request.url.path
        if path in _SKIP_PATHS or any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        # Only run if auth middleware has set user_id
        user_id = getattr(request.state, "user_id", None)
        if user_id is None:
            return await call_next(request)

        # Check in-memory cache first
        now = time.monotonic()
        cached = _MODE_CACHE.get(user_id)
        if cached and cached[0] > now:
            request.state.trading_mode = cached[1]
            return await call_next(request)

        # Cache miss — query DB
        try:
            async with get_session() as db:
                result = await db.execute(
                    select(UserTradingSession).where(
                        UserTradingSession.user_id == user_id
                    )
                )
                session = result.scalar_one_or_none()

            mode = session.active_mode if session else TradingModeEnum.PAPER
            _MODE_CACHE[user_id] = (now + _CACHE_TTL, mode)
            request.state.trading_mode = mode
        except Exception as exc:
            logger.warning("trading_mode_middleware_error", error=str(exc))
            request.state.trading_mode = TradingModeEnum.PAPER

        return await call_next(request)

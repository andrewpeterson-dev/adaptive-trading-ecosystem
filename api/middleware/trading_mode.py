"""Trading mode middleware — reads the user's active mode from DB on every request."""

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

        # Look up server-side mode
        try:
            async with get_session() as db:
                result = await db.execute(
                    select(UserTradingSession).where(
                        UserTradingSession.user_id == user_id
                    )
                )
                session = result.scalar_one_or_none()

            request.state.trading_mode = (
                session.active_mode if session else TradingModeEnum.PAPER
            )
        except Exception as exc:
            logger.warning("trading_mode_middleware_error", error=str(exc))
            request.state.trading_mode = TradingModeEnum.PAPER

        return await call_next(request)

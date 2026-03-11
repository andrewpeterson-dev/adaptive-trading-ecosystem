"""JWT authentication middleware for FastAPI."""

import jwt
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from config.settings import get_settings

logger = structlog.get_logger(__name__)

# Paths that don't require authentication
_PUBLIC_PATHS = frozenset({
    "/health",
    "/api/auth/login",
    "/api/auth/register",
    "/docs",
    "/openapi.json",
    "/redoc",
})

_PUBLIC_PREFIXES = ("/api/auth/verify", "/ws/", "/api/documents/upload/")


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public paths
        if path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)

        # OPTIONS (CORS preflight) always passes
        if request.method == "OPTIONS":
            return await call_next(request)

        # Extract token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        token = auth_header[7:]
        try:
            payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
            user_id = payload.get("user_id")
            if user_id is None:
                raise jwt.InvalidTokenError("Missing user_id claim")

            request.state.user_id = int(user_id)
            request.state.is_admin = payload.get("is_admin", False)
            request.state.email = payload.get("email", "")
        except jwt.ExpiredSignatureError:
            logger.warning("jwt_auth_failed", path=path, reason="expired")
            return JSONResponse({"detail": "Token expired"}, status_code=401)
        except (jwt.InvalidTokenError, TypeError, ValueError) as exc:
            logger.warning("jwt_auth_failed", path=path, reason="invalid", error=str(exc))
            return JSONResponse({"detail": "Invalid token"}, status_code=401)

        return await call_next(request)

"""JWT authentication middleware for FastAPI."""

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from services.security.auth_session import ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME
from services.security.request_auth import (
    AuthenticationError,
    AuthenticationUnavailableError,
    authenticate_token,
)

logger = structlog.get_logger(__name__)

# Paths that don't require authentication
_PUBLIC_PATHS = frozenset({
    "/health",
    "/health/ready",
    "/api/auth/login",
    "/api/auth/register",
    "/docs",
    "/openapi.json",
    "/redoc",
})

_PUBLIC_PREFIXES = (
    "/api/auth/verify-email",
    "/api/auth/resend-verification",
    "/api/auth/password-reset/",
    "/ws/",
)
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public paths
        if path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)

        # OPTIONS (CORS preflight) always passes
        if request.method == "OPTIONS":
            return await call_next(request)

        # Extract token: Authorization header first, then HttpOnly cookie fallback.
        token = None
        auth_via_cookie = False
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = request.cookies.get(ACCESS_COOKIE_NAME)
            auth_via_cookie = bool(token)

        if not token:
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        try:
            authenticated = await authenticate_token(token, allowed_scopes={"access"})
        except AuthenticationUnavailableError as exc:
            logger.error("jwt_auth_unavailable", path=path, error=str(exc))
            return JSONResponse({"detail": "Authentication unavailable"}, status_code=503)
        except AuthenticationError as exc:
            status_code = 401
            if exc.reason in {"inactive", "unverified"}:
                status_code = 403
            logger.warning("jwt_auth_failed", path=path, reason=exc.reason, error=exc.detail)
            return JSONResponse({"detail": exc.detail}, status_code=status_code)

        if auth_via_cookie and request.method.upper() not in _SAFE_METHODS:
            csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME, "")
            csrf_header = request.headers.get("X-CSRF-Token", "")
            if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                logger.warning("csrf_validation_failed", path=path)
                return JSONResponse({"detail": "CSRF validation failed"}, status_code=403)

        request.state.user = authenticated.user
        request.state.user_id = authenticated.user.id
        request.state.is_admin = authenticated.user.is_admin
        request.state.email = authenticated.user.email
        request.state.auth_via_cookie = auth_via_cookie
        request.state.auth_scope = authenticated.payload.get("scope", "access")

        return await call_next(request)

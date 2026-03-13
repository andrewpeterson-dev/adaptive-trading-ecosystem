"""Shared token authentication helpers for HTTP and WebSocket flows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import jwt
from sqlalchemy import select

from db.database import get_session
from db.models import User
from services.security.jwt_utils import JWTConfigurationError, decode_jwt


class AuthenticationUnavailableError(RuntimeError):
    """Raised when auth validation cannot run because config is missing."""


class AuthenticationError(RuntimeError):
    """Raised when a presented token cannot be trusted."""

    def __init__(self, detail: str, *, reason: str = "invalid") -> None:
        super().__init__(detail)
        self.detail = detail
        self.reason = reason


@dataclass
class AuthenticatedRequest:
    user: User
    payload: dict[str, Any]


def _allowed_scope_set(allowed_scopes: Iterable[str] | None) -> set[str]:
    scopes = {str(scope).strip() for scope in (allowed_scopes or {"access"}) if str(scope).strip()}
    return scopes or {"access"}


async def authenticate_token(
    token: str,
    *,
    allowed_scopes: Iterable[str] | None = None,
) -> AuthenticatedRequest:
    """Decode a JWT and re-check the user against the database."""
    try:
        payload = decode_jwt(token)
    except JWTConfigurationError as exc:
        raise AuthenticationUnavailableError("Authentication is unavailable") from exc
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token expired", reason="expired") from exc
    except (jwt.InvalidTokenError, TypeError, ValueError) as exc:
        raise AuthenticationError("Invalid token", reason="invalid") from exc

    user_id = payload.get("user_id")
    if user_id is None:
        raise AuthenticationError("Invalid token", reason="missing_user")

    scope = str(payload.get("scope") or "access").strip().lower()
    if scope not in _allowed_scope_set(allowed_scopes):
        raise AuthenticationError("Invalid token scope", reason="scope")

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Invalid token", reason="invalid_user") from exc

    async with get_session() as db:
        result = await db.execute(select(User).where(User.id == user_id_int))
        user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("Account not found", reason="missing_user")
    if not user.is_active:
        raise AuthenticationError("Account is disabled", reason="inactive")
    if not user.email_verified:
        raise AuthenticationError("Account is not verified", reason="unverified")

    try:
        token_session_version = int(payload.get("session_version"))
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Invalid token", reason="invalid_session_version") from exc

    if token_session_version != int(user.session_version or 0):
        raise AuthenticationError("Session has expired", reason="revoked")

    return AuthenticatedRequest(user=user, payload=payload)

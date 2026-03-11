"""JWT helpers that fail closed when the signing secret is missing."""
from __future__ import annotations

from typing import Any, Mapping

import jwt

from config.settings import Settings, get_settings

_INVALID_JWT_SECRETS = frozenset({"", "ate-dev-secret-change-in-production"})


class JWTConfigurationError(RuntimeError):
    """Raised when JWT operations are attempted without a configured secret."""


def is_jwt_secret_configured(settings: Settings | None = None) -> bool:
    """Return True when the JWT secret is present and not using a known placeholder."""
    active_settings = settings or get_settings()
    secret = (active_settings.jwt_secret or "").strip()
    return secret not in _INVALID_JWT_SECRETS


def get_jwt_secret(settings: Settings | None = None) -> str:
    """Return the configured JWT secret or raise a fail-closed configuration error."""
    active_settings = settings or get_settings()
    secret = (active_settings.jwt_secret or "").strip()
    if secret in _INVALID_JWT_SECRETS:
        raise JWTConfigurationError("JWT_SECRET is not configured")
    return secret


def encode_jwt(payload: Mapping[str, Any], settings: Settings | None = None) -> str:
    """Encode a JWT using the configured application secret."""
    return jwt.encode(dict(payload), get_jwt_secret(settings), algorithm="HS256")


def decode_jwt(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """Decode a JWT using the configured application secret."""
    payload = jwt.decode(token, get_jwt_secret(settings), algorithms=["HS256"])
    return dict(payload)

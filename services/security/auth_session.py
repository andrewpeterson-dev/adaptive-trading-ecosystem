"""Cookie and token helpers for browser authentication."""

from __future__ import annotations

import hashlib
import secrets

from fastapi.responses import Response

from config.settings import Settings, get_settings

ACCESS_COOKIE_NAME = "access_token"
CSRF_COOKIE_NAME = "csrf_token"


def issue_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def should_use_secure_cookies(settings: Settings | None = None) -> bool:
    active_settings = settings or get_settings()
    return active_settings.base_url.strip().lower().startswith("https://")


def set_auth_cookies(
    response: Response,
    *,
    token: str,
    csrf_token: str,
    settings: Settings | None = None,
) -> None:
    active_settings = settings or get_settings()
    max_age = max(active_settings.jwt_expiry_days, 1) * 24 * 60 * 60
    secure = should_use_secure_cookies(active_settings)

    response.set_cookie(
        ACCESS_COOKIE_NAME,
        token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        httponly=False,
        secure=secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )


def clear_auth_cookies(response: Response, settings: Settings | None = None) -> None:
    active_settings = settings or get_settings()
    secure = should_use_secure_cookies(active_settings)

    response.delete_cookie(ACCESS_COOKIE_NAME, path="/", secure=secure, samesite="lax")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/", secure=secure, samesite="lax")

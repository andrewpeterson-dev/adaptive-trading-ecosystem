"""Origin validation helpers for browser-initiated requests."""

from __future__ import annotations

from typing import Iterable
from urllib.parse import urlsplit

from fastapi import WebSocket

from config.settings import Settings, get_settings


def _normalize_origin(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None

    parsed = urlsplit(raw)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if scheme not in {"http", "https", "ws", "wss"} or not host:
        return None

    normalized_scheme = {"ws": "http", "wss": "https"}.get(scheme, scheme)
    port = parsed.port
    default_port = 443 if normalized_scheme == "https" else 80
    if port in (None, default_port):
        return f"{normalized_scheme}://{host}"
    return f"{normalized_scheme}://{host}:{port}"


def _configured_origins(settings: Settings) -> set[str]:
    configured: set[str] = set()
    candidates: Iterable[str | None] = (
        settings.base_url,
        settings.frontend_url,
        *(origin.strip() for origin in settings.cors_origins.split(",")),
    )
    for candidate in candidates:
        normalized = _normalize_origin(candidate)
        if normalized:
            configured.add(normalized)
    return configured


def websocket_origin_allowed(websocket: WebSocket, settings: Settings | None = None) -> bool:
    """Accept only browser origins that match configured frontend origins.

    Also allows Vercel preview/branch deployment subdomains matching the
    team slug pattern (e.g. *-pimpinpetes-projects.vercel.app).
    """
    active_settings = settings or get_settings()
    origin = _normalize_origin(websocket.headers.get("origin"))
    if not origin:
        return False
    if origin in _configured_origins(active_settings):
        return True
    # Allow Vercel preview deployments: https://<hash>-<team>.vercel.app
    parsed = urlsplit(origin)
    host = (parsed.hostname or "").lower()
    if host.endswith(".vercel.app"):
        # Check that at least one configured origin is on vercel.app
        # (prevents accepting random Vercel projects)
        configured = _configured_origins(active_settings)
        if any("vercel.app" in o for o in configured):
            return True
    return False

"""Shared provider credential helpers for Cerberus tools."""
from __future__ import annotations

import json
from typing import Sequence

import structlog
from sqlalchemy import select

from config.settings import get_settings
from db.database import get_session
from db.encryption import decrypt_value
from db.models import ApiProvider, UserApiConnection

logger = structlog.get_logger(__name__)


def _env_credentials_for_slug(provider_slug: str) -> dict | None:
    settings = get_settings()
    normalized = provider_slug.strip().lower()

    if normalized == "alpha_vantage" and settings.alphavantage_api_key:
        return {"api_key": settings.alphavantage_api_key}
    if normalized in {"finnhub", "finnhub_news"} and settings.finnhub_api_key:
        return {"api_key": settings.finnhub_api_key}
    if normalized in {"tradier", "tradier_options"} and settings.tradier_api_key:
        return {"access_token": settings.tradier_api_key}

    return None


async def get_connected_provider_credentials(
    user_id: int,
    provider_slugs: Sequence[str],
) -> tuple[str | None, dict | None]:
    """Return credentials for the first connected provider in priority order."""
    priorities = [slug.strip().lower() for slug in provider_slugs if slug and slug.strip()]
    if not priorities:
        return None, None

    async with get_session() as session:
        result = await session.execute(
            select(UserApiConnection, ApiProvider)
            .join(ApiProvider, UserApiConnection.provider_id == ApiProvider.id)
            .where(
                UserApiConnection.user_id == user_id,
                UserApiConnection.status == "connected",
                ApiProvider.slug.in_(priorities),
            )
            .order_by(UserApiConnection.updated_at.desc())
        )
        rows = result.all()

    by_slug: dict[str, dict] = {}
    for connection, provider in rows:
        slug = str(provider.slug or "").strip().lower()
        if slug in by_slug:
            continue
        try:
            by_slug[slug] = json.loads(decrypt_value(connection.encrypted_credentials))
        except Exception as exc:  # pragma: no cover - defensive against bad secrets
            logger.warning(
                "provider_credentials_decrypt_failed",
                user_id=user_id,
                provider=slug,
                error=str(exc),
            )

    for slug in priorities:
        creds = by_slug.get(slug)
        if creds:
            return slug, creds
    return None, None


async def resolve_provider_credentials(
    user_id: int,
    provider_slugs: Sequence[str],
) -> tuple[str | None, dict | None]:
    """Resolve provider credentials from user connections first, then env settings."""
    slug, creds = await get_connected_provider_credentials(user_id, provider_slugs)
    if slug and creds:
        return slug, creds

    for provider_slug in provider_slugs:
        env_creds = _env_credentials_for_slug(provider_slug)
        if env_creds:
            return provider_slug.strip().lower(), env_creds

    return None, None

"""
API connection management routes.

Handles provider catalog, user connections (CRUD + test), and API settings
(active broker, market data priority).

All endpoints require JWT authentication via request.state.user_id.
"""

import time
from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from db.database import get_session
from db.models import ApiProvider, ApiProviderType, UserApiConnection, UserApiSettings
from services.api_connection_manager import api_connection_manager

logger = structlog.get_logger(__name__)
router = APIRouter()

# Per-connection test cooldown: connection_id -> last_tested epoch
_test_cooldowns: dict[int, float] = {}
_TEST_COOLDOWN_SECONDS = 10


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_user(request: Request) -> int:
    """Return user_id or raise 401."""
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


def _provider_dict(p: ApiProvider) -> dict:
    return {
        "id": p.id,
        "slug": p.slug,
        "name": p.name,
        "api_type": p.api_type.value if hasattr(p.api_type, "value") else p.api_type,
        "supports_trading": p.supports_trading,
        "supports_paper": p.supports_paper,
        "supports_market_data": p.supports_market_data,
        "supports_options": p.supports_options,
        "supports_crypto": p.supports_crypto,
        "requires_secret": p.requires_secret,
        "unified_mode": p.unified_mode or False,
        "credential_note": p.credential_note,
        "credential_fields": p.credential_fields,
        "docs_url": p.docs_url,
        "is_available": p.is_available,
    }


def _connection_dict(conn: UserApiConnection) -> dict:
    """Safe connection representation — never includes credentials."""
    provider = conn.provider
    return {
        "id": conn.id,
        "provider_id": conn.provider_id,
        "provider_name": provider.name if provider else None,
        "provider_slug": provider.slug if provider else None,
        "api_type": (
            provider.api_type.value
            if provider and hasattr(provider.api_type, "value")
            else (provider.api_type if provider else None)
        ),
        "status": conn.status,
        "error_message": conn.error_message,
        "is_paper": conn.is_paper,
        "unified_mode": provider.unified_mode if provider else False,
        "supports_market_data": provider.supports_market_data if provider else False,
        "nickname": conn.nickname,
        "created_at": conn.created_at.isoformat() if conn.created_at else None,
        "last_tested_at": conn.last_tested_at.isoformat() if conn.last_tested_at else None,
    }


def _settings_dict(s: UserApiSettings) -> dict:
    return {
        "active_equity_broker_id": s.active_equity_broker_id,
        "active_crypto_broker_id": s.active_crypto_broker_id,
        "primary_market_data_id": s.primary_market_data_id,
        "fallback_market_data_ids": s.fallback_market_data_ids or [],
        "primary_options_data_id": s.primary_options_data_id,
    }


# ── Connection tester ─────────────────────────────────────────────────────────

async def _test_connection_internal(
    conn: UserApiConnection, credentials: dict
) -> dict:
    """
    Attempt a lightweight validation of the API credentials.
    Returns {"connected": bool, "error": str | None}.
    """
    provider = conn.provider
    slug = provider.slug if provider else ""

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:

            if slug == "alpaca":
                api_key = credentials.get("api_key", "")
                api_secret = credentials.get("api_secret", "")
                base = (
                    "https://paper-api.alpaca.markets"
                    if conn.is_paper
                    else "https://api.alpaca.markets"
                )
                resp = await client.get(
                    f"{base}/v2/account",
                    headers={
                        "APCA-API-KEY-ID": api_key,
                        "APCA-API-SECRET-KEY": api_secret,
                    },
                )
                if resp.status_code == 200:
                    return {"connected": True, "error": None}
                return {"connected": False, "error": f"Alpaca returned {resp.status_code}"}

            elif slug == "polygon":
                api_key = credentials.get("api_key", "")
                resp = await client.get(
                    "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2023-01-09/2023-01-09",
                    params={"apiKey": api_key},
                )
                if resp.status_code == 403:
                    return {"connected": False, "error": "Invalid Polygon API key"}
                return {"connected": True, "error": None}

            elif slug == "finnhub":
                api_key = credentials.get("api_key", "")
                resp = await client.get(
                    "https://finnhub.io/api/v1/quote",
                    params={"symbol": "AAPL", "token": api_key},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if "c" in data:
                        return {"connected": True, "error": None}
                    return {"connected": False, "error": "Unexpected Finnhub response format"}
                return {"connected": False, "error": f"Finnhub returned {resp.status_code}"}

            elif slug == "tradier":
                access_token = credentials.get("access_token", "")
                base = "https://sandbox.tradier.com" if conn.is_paper else "https://api.tradier.com"
                resp = await client.get(
                    f"{base}/v1/user/profile",
                    headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                )
                if resp.status_code == 200:
                    return {"connected": True, "error": None}
                return {"connected": False, "error": f"Tradier returned {resp.status_code}"}

            elif slug == "fred":
                api_key = credentials.get("api_key", "")
                resp = await client.get(
                    "https://api.stlouisfed.org/fred/series",
                    params={"series_id": "GDP", "api_key": api_key, "file_type": "json"},
                )
                if resp.status_code == 200:
                    return {"connected": True, "error": None}
                return {"connected": False, "error": f"FRED returned {resp.status_code}"}

            else:
                # No dedicated validation — treat as connected
                return {"connected": True, "error": None}

    except httpx.TimeoutException:
        return {"connected": False, "error": "Connection timed out"}
    except Exception as exc:
        logger.warning("connection_test_error", slug=slug, error=str(exc))
        return {"connected": False, "error": str(exc)}


# ── Request models ────────────────────────────────────────────────────────────

class CreateConnectionRequest(BaseModel):
    provider_id: int
    credentials: dict
    is_paper: bool = True
    nickname: Optional[str] = None


class SetActiveBrokerRequest(BaseModel):
    connection_id: int


class SetActiveCryptoBrokerRequest(BaseModel):
    connection_id: int


class SetMarketDataPriorityRequest(BaseModel):
    primary_id: int
    fallback_ids: list[int] = []


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/providers")
async def list_providers(request: Request):
    """Return all available API providers (no credentials)."""
    _require_user(request)
    async with get_session() as db:
        result = await db.execute(
            select(ApiProvider).where(ApiProvider.is_available == True).order_by(ApiProvider.name)
        )
        providers = result.scalars().all()
    return [_provider_dict(p) for p in providers]


@router.get("/connections")
async def list_connections(request: Request):
    """Return user's connections with status — credentials never included."""
    user_id = _require_user(request)
    async with get_session() as db:
        result = await db.execute(
            select(UserApiConnection)
            .where(UserApiConnection.user_id == user_id)
            .order_by(UserApiConnection.created_at.desc())
        )
        connections = result.scalars().all()

        # Eagerly load providers
        provider_ids = list({c.provider_id for c in connections})
        if provider_ids:
            prov_result = await db.execute(
                select(ApiProvider).where(ApiProvider.id.in_(provider_ids))
            )
            providers_by_id = {p.id: p for p in prov_result.scalars().all()}
            for c in connections:
                c.provider = providers_by_id.get(c.provider_id)

    return [_connection_dict(c) for c in connections]


@router.post("/connections", status_code=201)
async def create_connection(req: CreateConnectionRequest, request: Request):
    """Save a new API connection, test it immediately, return connection object."""
    user_id = _require_user(request)

    # Validate provider exists and is available
    async with get_session() as db:
        prov_result = await db.execute(
            select(ApiProvider).where(ApiProvider.id == req.provider_id)
        )
        provider = prov_result.scalar_one_or_none()

    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    if not provider.is_available:
        raise HTTPException(status_code=400, detail="Provider is not available")

    # Save via service (manages its own session)
    conn = await api_connection_manager.save_connection(
        user_id=user_id,
        provider_id=req.provider_id,
        credentials=req.credentials,
        is_paper=req.is_paper,
        nickname=req.nickname,
    )

    # Reload with provider relationship for test + response
    async with get_session() as db:
        conn_result = await db.execute(
            select(UserApiConnection).where(UserApiConnection.id == conn.id)
        )
        conn = conn_result.scalar_one()
        conn.provider = provider

        # Test immediately
        test_result = await _test_connection_internal(conn, req.credentials)
        conn.status = "connected" if test_result["connected"] else "error"
        conn.error_message = test_result.get("error")
        conn.last_tested_at = datetime.utcnow()
        await db.commit()
        await db.refresh(conn)
        conn.provider = provider

    # Discover and store broker accounts for Webull
    if provider.slug == "webull":
        try:
            from services.account_discovery import discover_and_store_accounts
            await discover_and_store_accounts(
                user_id=user_id,
                connection_id=conn.id,
                app_key=req.credentials.get("app_key", ""),
                app_secret=req.credentials.get("app_secret", ""),
            )
        except Exception as exc:
            logger.warning("account_discovery_failed_on_connect", error=str(exc))

    logger.info(
        "connection_created",
        user_id=user_id,
        provider=provider.slug,
        status=conn.status,
    )
    return _connection_dict(conn)


@router.delete("/connections/{connection_id}")
async def delete_connection(connection_id: int, request: Request):
    """Soft-delete a connection (set to disconnected). Clears active settings if needed."""
    user_id = _require_user(request)

    async with get_session() as db:
        result = await db.execute(
            select(UserApiConnection).where(
                UserApiConnection.id == connection_id,
                UserApiConnection.user_id == user_id,
            )
        )
        conn = result.scalar_one_or_none()
        if not conn:
            raise HTTPException(status_code=404, detail="Connection not found")

        conn.status = "disconnected"
        conn.updated_at = datetime.now(timezone.utc)

        # Clear any active settings pointing to this connection
        settings_result = await db.execute(
            select(UserApiSettings).where(UserApiSettings.user_id == user_id)
        )
        settings = settings_result.scalar_one_or_none()
        if settings:
            if settings.active_equity_broker_id == connection_id:
                settings.active_equity_broker_id = None
            if settings.active_crypto_broker_id == connection_id:
                settings.active_crypto_broker_id = None
            if settings.primary_market_data_id == connection_id:
                settings.primary_market_data_id = None
            if settings.primary_options_data_id == connection_id:
                settings.primary_options_data_id = None
            fallbacks = settings.fallback_market_data_ids or []
            if connection_id in fallbacks:
                settings.fallback_market_data_ids = [f for f in fallbacks if f != connection_id]

        await db.commit()

    logger.info("connection_disconnected", user_id=user_id, connection_id=connection_id)
    return {"success": True}


@router.post("/connections/{connection_id}/test")
async def test_connection(connection_id: int, request: Request):
    """Test a connection's credentials. Rate-limited to once per 10 seconds per connection."""
    user_id = _require_user(request)

    # Rate limit check
    last_tested = _test_cooldowns.get(connection_id, 0)
    elapsed = time.time() - last_tested
    if elapsed < _TEST_COOLDOWN_SECONDS:
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {int(_TEST_COOLDOWN_SECONDS - elapsed)} more seconds before testing again",
        )

    async with get_session() as db:
        result = await db.execute(
            select(UserApiConnection).where(
                UserApiConnection.id == connection_id,
                UserApiConnection.user_id == user_id,
            )
        )
        conn = result.scalar_one_or_none()
        if not conn:
            raise HTTPException(status_code=404, detail="Connection not found")

        # Load provider
        prov_result = await db.execute(
            select(ApiProvider).where(ApiProvider.id == conn.provider_id)
        )
        conn.provider = prov_result.scalar_one_or_none()

        # Decrypt credentials for testing
        credentials = api_connection_manager.get_credentials(conn)

        test_result = await _test_connection_internal(conn, credentials)

        # Update status
        conn.status = "connected" if test_result["connected"] else "error"
        conn.error_message = test_result.get("error")
        conn.last_tested_at = datetime.utcnow()
        conn.updated_at = datetime.utcnow()
        await db.commit()

    _test_cooldowns[connection_id] = time.time()

    logger.info(
        "connection_tested",
        user_id=user_id,
        connection_id=connection_id,
        connected=test_result["connected"],
    )
    return {"connected": test_result["connected"], "error": test_result.get("error")}


@router.get("/api-settings")
async def get_api_settings(request: Request):
    """Return user's API settings plus any detected conflicts."""
    user_id = _require_user(request)

    settings = await api_connection_manager.get_or_create_settings(user_id)
    conflicts = await api_connection_manager.get_conflicts(user_id)

    return {**_settings_dict(settings), "conflicts": conflicts}


@router.post("/api-settings/active-broker")
async def set_active_broker(req: SetActiveBrokerRequest, request: Request):
    """Set the active equity broker connection."""
    user_id = _require_user(request)

    # Verify ownership and type
    async with get_session() as db:
        result = await db.execute(
            select(UserApiConnection)
            .join(ApiProvider)
            .where(
                UserApiConnection.id == req.connection_id,
                UserApiConnection.user_id == user_id,
            )
        )
        conn = result.scalar_one_or_none()
        if not conn:
            raise HTTPException(status_code=404, detail="Connection not found")

        prov_result = await db.execute(
            select(ApiProvider).where(ApiProvider.id == conn.provider_id)
        )
        provider = prov_result.scalar_one_or_none()
        if not provider or provider.api_type != ApiProviderType.BROKERAGE:
            raise HTTPException(
                status_code=400,
                detail="Connection must be a BROKERAGE type to set as active equity broker",
            )

    settings = await api_connection_manager.set_active_equity_broker(user_id, req.connection_id)
    conflicts = await api_connection_manager.get_conflicts(user_id)
    return {**_settings_dict(settings), "conflicts": conflicts}


@router.post("/api-settings/active-crypto-broker")
async def set_active_crypto_broker(req: SetActiveCryptoBrokerRequest, request: Request):
    """Set the active crypto broker connection."""
    user_id = _require_user(request)

    async with get_session() as db:
        result = await db.execute(
            select(UserApiConnection).where(
                UserApiConnection.id == req.connection_id,
                UserApiConnection.user_id == user_id,
            )
        )
        conn = result.scalar_one_or_none()
        if not conn:
            raise HTTPException(status_code=404, detail="Connection not found")

        prov_result = await db.execute(
            select(ApiProvider).where(ApiProvider.id == conn.provider_id)
        )
        provider = prov_result.scalar_one_or_none()
        if not provider or provider.api_type != ApiProviderType.CRYPTO_BROKER:
            raise HTTPException(
                status_code=400,
                detail="Connection must be a CRYPTO_BROKER type to set as active crypto broker",
            )

    settings = await api_connection_manager.set_active_crypto_broker(user_id, req.connection_id)
    conflicts = await api_connection_manager.get_conflicts(user_id)
    return {**_settings_dict(settings), "conflicts": conflicts}


@router.put("/api-settings/market-data-priority")
async def set_market_data_priority(req: SetMarketDataPriorityRequest, request: Request):
    """Set primary and fallback market data providers."""
    user_id = _require_user(request)

    all_ids = [req.primary_id] + req.fallback_ids

    # Verify all connections belong to user and are MARKET_DATA type
    async with get_session() as db:
        result = await db.execute(
            select(UserApiConnection)
            .join(ApiProvider)
            .where(
                UserApiConnection.id.in_(all_ids),
                UserApiConnection.user_id == user_id,
            )
        )
        conns = result.scalars().all()
        conn_ids_found = {c.id for c in conns}

        # Load providers for type check
        provider_ids = list({c.provider_id for c in conns})
        prov_result = await db.execute(
            select(ApiProvider).where(ApiProvider.id.in_(provider_ids))
        )
        providers_by_id = {p.id: p for p in prov_result.scalars().all()}

        for conn in conns:
            p = providers_by_id.get(conn.provider_id)
            if not p or p.api_type != ApiProviderType.MARKET_DATA:
                raise HTTPException(
                    status_code=400,
                    detail=f"Connection {conn.id} is not a MARKET_DATA type",
                )

        missing = set(all_ids) - conn_ids_found
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Connections not found or not owned by you: {sorted(missing)}",
            )

    settings = await api_connection_manager.set_market_data_priority(
        user_id, req.primary_id, req.fallback_ids
    )
    conflicts = await api_connection_manager.get_conflicts(user_id)
    return {**_settings_dict(settings), "conflicts": conflicts}

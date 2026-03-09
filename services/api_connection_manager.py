"""
APIConnectionManager — central service for managing API provider connections.

Handles: credential storage, conflict detection, routing, fallback.
"""

import json
from typing import Optional
import structlog
from sqlalchemy import select
from db.database import get_session
from db.models import UserApiConnection, UserApiSettings, ApiProvider, ApiProviderType
from db.encryption import encrypt_value, decrypt_value

logger = structlog.get_logger(__name__)


class APIConnectionManager:
    """
    Central manager for user API connections.

    Key responsibilities:
    - Store and retrieve encrypted credentials
    - Detect conflicts (multiple active brokers)
    - Route trade execution to correct broker
    - Route market data requests with fallback
    - Route options data requests with fallback
    """

    # -- Conflict detection -----------------------------------------------

    async def get_conflicts(self, user_id: int) -> list[dict]:
        """
        Return list of detected conflicts for this user.

        Current conflict rules:
        - BROKERAGE: multiple connected but none set as active -> conflict
        """
        conflicts = []
        async with get_session() as db:
            # Count connected brokerages
            result = await db.execute(
                select(UserApiConnection)
                .join(ApiProvider)
                .where(
                    UserApiConnection.user_id == user_id,
                    UserApiConnection.status == "connected",
                    ApiProvider.api_type == ApiProviderType.BROKERAGE,
                )
            )
            brokerages = result.scalars().all()

            settings_result = await db.execute(
                select(UserApiSettings).where(UserApiSettings.user_id == user_id)
            )
            settings = settings_result.scalar_one_or_none()

            if len(brokerages) > 1 and (not settings or not settings.active_equity_broker_id):
                conflicts.append({
                    "type": "multiple_brokers",
                    "message": "Multiple brokerages connected. Select one as ACTIVE broker for order execution.",
                    "affected_ids": [b.id for b in brokerages],
                })
        return conflicts

    # -- Credential storage -----------------------------------------------

    async def save_connection(
        self,
        user_id: int,
        provider_id: int,
        credentials: dict,
        is_paper: bool = True,
        nickname: str = None,
    ) -> UserApiConnection:
        """Encrypt and save API credentials for a provider."""
        encrypted = encrypt_value(json.dumps(credentials))
        async with get_session() as db:
            # Upsert: if connection for this user+provider exists, update it
            result = await db.execute(
                select(UserApiConnection).where(
                    UserApiConnection.user_id == user_id,
                    UserApiConnection.provider_id == provider_id,
                )
            )
            conn = result.scalar_one_or_none()
            if conn:
                conn.encrypted_credentials = encrypted
                conn.is_paper = is_paper
                conn.status = "pending"
                conn.error_message = None
                if nickname:
                    conn.nickname = nickname
            else:
                conn = UserApiConnection(
                    user_id=user_id,
                    provider_id=provider_id,
                    encrypted_credentials=encrypted,
                    is_paper=is_paper,
                    nickname=nickname,
                    status="pending",
                )
                db.add(conn)
            await db.commit()
            await db.refresh(conn)
            return conn

    def get_credentials(self, conn: UserApiConnection) -> dict:
        """Decrypt and return credentials dict (never expose to frontend)."""
        return json.loads(decrypt_value(conn.encrypted_credentials))

    # -- Routing: trade execution -----------------------------------------

    async def get_execution_broker(self, user_id: int, asset_type: str = "equity") -> Optional[UserApiConnection]:
        """
        Return the active broker connection for this user and asset type.

        asset_type: "equity" | "crypto"
        """
        async with get_session() as db:
            settings_result = await db.execute(
                select(UserApiSettings).where(UserApiSettings.user_id == user_id)
            )
            settings = settings_result.scalar_one_or_none()
            if not settings:
                return None

            target_id = (
                settings.active_crypto_broker_id
                if asset_type == "crypto"
                else settings.active_equity_broker_id
            )
            if not target_id:
                return None

            result = await db.execute(
                select(UserApiConnection).where(
                    UserApiConnection.id == target_id,
                    UserApiConnection.user_id == user_id,
                    UserApiConnection.status == "connected",
                )
            )
            return result.scalar_one_or_none()

    # -- Routing: market data -----------------------------------------------

    async def get_market_data_providers(self, user_id: int) -> list[UserApiConnection]:
        """
        Return market data providers in priority order: [primary, ...fallbacks].
        """
        async with get_session() as db:
            settings_result = await db.execute(
                select(UserApiSettings).where(UserApiSettings.user_id == user_id)
            )
            settings = settings_result.scalar_one_or_none()

            ordered_ids = []
            if settings:
                if settings.primary_market_data_id:
                    ordered_ids.append(settings.primary_market_data_id)
                ordered_ids.extend(
                    fid for fid in (settings.fallback_market_data_ids or [])
                    if fid != settings.primary_market_data_id
                )

            if not ordered_ids:
                # Auto-select: any connected market data provider
                result = await db.execute(
                    select(UserApiConnection)
                    .join(ApiProvider)
                    .where(
                        UserApiConnection.user_id == user_id,
                        UserApiConnection.status == "connected",
                        ApiProvider.api_type == ApiProviderType.MARKET_DATA,
                    )
                )
                return result.scalars().all()

            # Load in priority order
            result = await db.execute(
                select(UserApiConnection).where(
                    UserApiConnection.id.in_(ordered_ids),
                    UserApiConnection.user_id == user_id,
                    UserApiConnection.status == "connected",
                )
            )
            conns_by_id = {c.id: c for c in result.scalars().all()}
            return [conns_by_id[i] for i in ordered_ids if i in conns_by_id]

    # -- Routing: options data -----------------------------------------------

    async def get_options_data_providers(self, user_id: int) -> list[UserApiConnection]:
        """
        Return options data providers. Prefers OPTIONS_DATA type, falls back to
        connected MARKET_DATA providers that support_options.
        """
        async with get_session() as db:
            settings_result = await db.execute(
                select(UserApiSettings).where(UserApiSettings.user_id == user_id)
            )
            settings = settings_result.scalar_one_or_none()

            primary_id = settings.primary_options_data_id if settings else None

            result = await db.execute(
                select(UserApiConnection)
                .join(ApiProvider)
                .where(
                    UserApiConnection.user_id == user_id,
                    UserApiConnection.status == "connected",
                    ApiProvider.api_type == ApiProviderType.OPTIONS_DATA,
                )
            )
            options_conns = result.scalars().all()

            # Also find market data providers that support options
            result2 = await db.execute(
                select(UserApiConnection)
                .join(ApiProvider)
                .where(
                    UserApiConnection.user_id == user_id,
                    UserApiConnection.status == "connected",
                    ApiProvider.api_type == ApiProviderType.MARKET_DATA,
                    ApiProvider.supports_options == True,
                )
            )
            md_with_options = result2.scalars().all()

            all_providers = options_conns + md_with_options

            # Put primary first if set
            if primary_id:
                primary = next((c for c in all_providers if c.id == primary_id), None)
                rest = [c for c in all_providers if c.id != primary_id]
                return ([primary] + rest) if primary else all_providers

            return all_providers

    # -- Settings management -----------------------------------------------

    async def get_or_create_settings(self, user_id: int) -> UserApiSettings:
        async with get_session() as db:
            result = await db.execute(
                select(UserApiSettings).where(UserApiSettings.user_id == user_id)
            )
            settings = result.scalar_one_or_none()
            if not settings:
                settings = UserApiSettings(user_id=user_id, fallback_market_data_ids=[])
                db.add(settings)
                await db.commit()
                await db.refresh(settings)
            return settings

    async def set_active_equity_broker(self, user_id: int, connection_id: int) -> UserApiSettings:
        async with get_session() as db:
            result = await db.execute(
                select(UserApiSettings).where(UserApiSettings.user_id == user_id)
            )
            settings = result.scalar_one_or_none()
            if not settings:
                settings = UserApiSettings(user_id=user_id, fallback_market_data_ids=[])
                db.add(settings)
            settings.active_equity_broker_id = connection_id
            await db.commit()
            await db.refresh(settings)
            logger.info("active_equity_broker_set", user_id=user_id, connection_id=connection_id)
            return settings

    async def set_active_crypto_broker(self, user_id: int, connection_id: int) -> UserApiSettings:
        async with get_session() as db:
            result = await db.execute(
                select(UserApiSettings).where(UserApiSettings.user_id == user_id)
            )
            settings = result.scalar_one_or_none()
            if not settings:
                settings = UserApiSettings(user_id=user_id, fallback_market_data_ids=[])
                db.add(settings)
            settings.active_crypto_broker_id = connection_id
            await db.commit()
            await db.refresh(settings)
            return settings

    async def set_market_data_priority(
        self, user_id: int, primary_id: int, fallback_ids: list[int]
    ) -> UserApiSettings:
        async with get_session() as db:
            result = await db.execute(
                select(UserApiSettings).where(UserApiSettings.user_id == user_id)
            )
            settings = result.scalar_one_or_none()
            if not settings:
                settings = UserApiSettings(user_id=user_id, fallback_market_data_ids=[])
                db.add(settings)
            settings.primary_market_data_id = primary_id
            settings.fallback_market_data_ids = fallback_ids
            await db.commit()
            await db.refresh(settings)
            return settings


# Module-level singleton
api_connection_manager = APIConnectionManager()

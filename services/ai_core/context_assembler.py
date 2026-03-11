"""Context assembler — gathers context from multiple sources for Cerberus."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class AssembledContext:
    """Full context assembled for a Cerberus turn."""
    system_context: dict = field(default_factory=dict)
    user_context: dict = field(default_factory=dict)
    page_context: dict = field(default_factory=dict)
    live_trading_context: dict = field(default_factory=dict)
    conversation_context: dict = field(default_factory=dict)
    semantic_memory_context: dict = field(default_factory=dict)
    document_context: dict = field(default_factory=dict)
    safety_context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "systemContext": self.system_context,
            "userContext": self.user_context,
            "pageContext": self.page_context,
            "liveTradingContext": self.live_trading_context,
            "conversationContext": self.conversation_context,
            "semanticMemoryContext": self.semantic_memory_context,
            "documentContext": self.document_context,
            "safetyContext": self.safety_context,
        }


class ContextAssembler:
    """Assembles full context for a Cerberus turn from multiple sources."""

    def __init__(self, redis_client=None):
        self._redis = redis_client

    async def assemble(
        self,
        user_id: int,
        thread_id: Optional[str] = None,
        page_context: Optional[dict] = None,
        mode: str = "chat",
        selected_account_id: Optional[str] = None,
        attachment_ids: Optional[list[str]] = None,
    ) -> AssembledContext:
        """Assemble full context for a Cerberus turn."""
        from config.settings import get_settings
        settings = get_settings()

        ctx = AssembledContext()

        # 1. System context
        ctx.system_context = {
            "feature_flags": {
                "cerberus_enabled": settings.feature_cerberus_enabled,
                "research_mode": settings.feature_research_mode_enabled,
                "bot_mutations": settings.feature_bot_mutations_enabled,
                "paper_trade_proposals": settings.feature_paper_trade_proposals_enabled,
                "live_trade_proposals": settings.feature_live_trade_proposals_enabled,
                "slow_expert_mode": settings.feature_slow_expert_mode_enabled,
            },
            "mode": mode,
        }
        ctx.system_context["connected_data"] = await self._get_data_access_context(user_id)

        # 2. User context
        ctx.user_context = await self._get_user_context(user_id)

        # 3. Page context (from frontend)
        ctx.page_context = page_context or {}

        # 4. Live trading context (from Redis or DB)
        ctx.live_trading_context = await self._get_live_trading_context(user_id, selected_account_id)

        # 5. Conversation context
        if thread_id:
            ctx.conversation_context = await self._get_conversation_context(thread_id, user_id)

        # 6. Semantic memory context
        ctx.semantic_memory_context = await self._get_semantic_memory(user_id, mode)

        # 7. Document context
        if attachment_ids:
            ctx.document_context = await self._get_document_context(user_id, attachment_ids)

        # 8. Safety context
        ctx.safety_context = await self._get_safety_context(user_id)

        return ctx

    async def _get_user_context(self, user_id: int) -> dict:
        """Get user profile context (no secrets)."""
        try:
            from db.database import get_session
            from db.models import User
            from sqlalchemy import select

            async with get_session() as session:
                result = await session.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if user:
                    return {
                        "user_id": user.id,
                        "display_name": user.display_name,
                        "is_admin": user.is_admin,
                    }
        except Exception as e:
            logger.warning("user_context_error", error=str(e))
        return {"user_id": user_id}

    async def _get_live_trading_context(self, user_id: int, account_id: Optional[str] = None) -> dict:
        """Get live trading context from Redis or DB."""
        context: dict[str, Any] = {}

        # Try Redis first
        if self._redis:
            try:
                portfolio = await self._redis.get(f"user:{user_id}:portfolio_snapshot")
                if portfolio:
                    import json
                    context["portfolio_snapshot"] = json.loads(portfolio)

                positions = await self._redis.get(f"user:{user_id}:positions_snapshot")
                if positions:
                    import json
                    context["positions"] = json.loads(positions)

                risk = await self._redis.get(f"user:{user_id}:risk_snapshot")
                if risk:
                    import json
                    context["risk_snapshot"] = json.loads(risk)

                bots = await self._redis.get(f"user:{user_id}:active_bots")
                if bots:
                    import json
                    context["active_bots"] = json.loads(bots)
            except Exception as e:
                logger.warning("redis_context_error", error=str(e))

        # Fallback to DB if Redis empty
        if not context.get("portfolio_snapshot"):
            try:
                from db.database import get_session
                from db.cerberus_models import CerberusPortfolioSnapshot
                from sqlalchemy import select

                async with get_session() as session:
                    stmt = select(CerberusPortfolioSnapshot).where(
                        CerberusPortfolioSnapshot.user_id == user_id
                    ).order_by(CerberusPortfolioSnapshot.snapshot_ts.desc()).limit(1)
                    result = await session.execute(stmt)
                    snap = result.scalar_one_or_none()
                    if snap:
                        context["portfolio_snapshot"] = {
                            "cash": float(snap.cash or 0),
                            "equity": float(snap.equity or 0),
                            "day_pnl": float(snap.day_pnl or 0),
                        }
            except Exception as e:
                logger.warning("db_portfolio_context_error", error=str(e))

        return context

    async def _get_conversation_context(self, thread_id: str, user_id: int) -> dict:
        """Get recent conversation messages and thread summary."""
        try:
            from db.database import get_session
            from db.cerberus_models import CerberusConversationThread, CerberusConversationMessage
            from sqlalchemy import select

            async with get_session() as session:
                # Thread summary
                thread_result = await session.execute(
                    select(CerberusConversationThread).where(
                        CerberusConversationThread.id == thread_id,
                        CerberusConversationThread.user_id == user_id,
                    )
                )
                thread = thread_result.scalar_one_or_none()

                # Recent messages (last 20)
                msgs_result = await session.execute(
                    select(CerberusConversationMessage).where(
                        CerberusConversationMessage.thread_id == thread_id,
                        CerberusConversationMessage.user_id == user_id,
                    ).order_by(CerberusConversationMessage.created_at.desc()).limit(20)
                )
                messages = msgs_result.scalars().all()

                return {
                    "thread_id": thread_id,
                    "summary": thread.summary if thread else None,
                    "mode": thread.mode.value if thread and thread.mode else "chat",
                    "recent_messages": [
                        {
                            "role": m.role.value if hasattr(m.role, "value") else m.role,
                            "content": m.content_md[:500] if m.content_md else "",
                            "model": m.model_name,
                        }
                        for m in reversed(messages)
                    ],
                }
        except Exception as e:
            logger.warning("conversation_context_error", error=str(e))
        return {}

    async def _get_semantic_memory(self, user_id: int, mode: str) -> dict:
        """Get relevant semantic memory items."""
        try:
            from db.database import get_session
            from db.cerberus_models import CerberusMemoryItem
            from sqlalchemy import select

            async with get_session() as session:
                stmt = select(CerberusMemoryItem).where(
                    CerberusMemoryItem.user_id == user_id,
                ).order_by(CerberusMemoryItem.created_at.desc()).limit(10)
                result = await session.execute(stmt)
                items = result.scalars().all()

                return {
                    "items": [
                        {"kind": m.kind, "content": m.content[:300]}
                        for m in items
                    ]
                }
        except Exception as e:
            logger.warning("semantic_memory_error", error=str(e))
        return {}

    async def _get_document_context(self, user_id: int, doc_ids: list[str]) -> dict:
        """Get document metadata for attached documents."""
        try:
            from db.database import get_session
            from db.cerberus_models import CerberusDocumentFile
            from sqlalchemy import select

            async with get_session() as session:
                stmt = select(CerberusDocumentFile).where(
                    CerberusDocumentFile.id.in_(doc_ids),
                    CerberusDocumentFile.user_id == user_id,
                )
                result = await session.execute(stmt)
                docs = result.scalars().all()

                return {
                    "documents": [
                        {
                            "id": d.id,
                            "filename": d.original_filename,
                            "status": d.status.value if hasattr(d.status, "value") else d.status,
                            "type": d.doc_type,
                        }
                        for d in docs
                    ]
                }
        except Exception as e:
            logger.warning("document_context_error", error=str(e))
        return {}

    async def _get_safety_context(self, user_id: int) -> dict:
        """Get safety context: active risk limits and circuit breakers."""
        from config.settings import get_settings
        settings = get_settings()
        return {
            "max_position_size_pct": settings.max_position_size_pct,
            "max_portfolio_exposure_pct": settings.max_portfolio_exposure_pct,
            "max_drawdown_pct": settings.max_drawdown_pct,
            "live_trading_enabled": settings.live_trading_enabled,
        }

    async def _get_data_access_context(self, user_id: int) -> dict:
        """Summarize Cerberus data/tool connectivity for prompt conditioning."""
        try:
            from sqlalchemy import func, select

            from db.cerberus_models import CerberusBot
            from db.database import get_session
            from db.models import ApiProvider, UserApiConnection, UserApiSettings

            async with get_session() as session:
                conn_result = await session.execute(
                    select(UserApiConnection, ApiProvider)
                    .join(ApiProvider, UserApiConnection.provider_id == ApiProvider.id)
                    .where(UserApiConnection.user_id == user_id)
                )
                connection_rows = conn_result.all()

                settings_result = await session.execute(
                    select(UserApiSettings).where(UserApiSettings.user_id == user_id)
                )
                settings = settings_result.scalar_one_or_none()

                bot_count_result = await session.execute(
                    select(func.count(CerberusBot.id)).where(CerberusBot.user_id == user_id)
                )
                bot_count = int(bot_count_result.scalar() or 0)

            connections = [
                {
                    "provider": provider.name,
                    "api_type": provider.api_type.value
                    if hasattr(provider.api_type, "value")
                    else str(provider.api_type),
                    "status": connection.status,
                    "id": connection.id,
                }
                for connection, provider in connection_rows
            ]

            def derive_state(connected_count: int, error_count: int) -> str:
                if connected_count > 0:
                    return "connected"
                if error_count > 0:
                    return "error"
                return "not_connected"

            connected_brokers = [
                c for c in connections
                if c["status"] == "connected" and c["api_type"] in {"brokerage", "crypto_broker"}
            ]
            errored_brokers = [
                c for c in connections
                if c["status"] == "error" and c["api_type"] in {"brokerage", "crypto_broker"}
            ]
            connected_market = [
                c for c in connections
                if c["status"] == "connected"
                and c["api_type"] in {"market_data", "brokerage", "crypto_broker"}
            ]
            errored_market = [
                c for c in connections
                if c["status"] == "error"
                and c["api_type"] in {"market_data", "brokerage", "crypto_broker"}
            ]

            portfolio_state = derive_state(len(connected_brokers), len(errored_brokers))
            market_state = derive_state(len(connected_market), len(errored_market))
            risk_state = (
                "connected"
                if portfolio_state == "connected"
                else "error" if portfolio_state == "error" else "not_connected"
            )

            active_broker_id = getattr(settings, "active_equity_broker_id", None)
            primary_market_data_id = getattr(settings, "primary_market_data_id", None)
            active_broker = next(
                (c for c in connections if c["id"] == active_broker_id),
                connected_brokers[0] if connected_brokers else None,
            )
            active_market_data = next(
                (c for c in connections if c["id"] == primary_market_data_id),
                connected_market[0] if connected_market else None,
            )

            return {
                "portfolio_holdings": {
                    "state": portfolio_state,
                    "detail": active_broker["provider"] if active_broker else "No connected broker",
                },
                "market_data": {
                    "state": market_state,
                    "detail": active_market_data["provider"]
                    if active_market_data
                    else "No connected market data source",
                },
                "risk_analytics": {
                    "state": risk_state,
                    "detail": "Portfolio-driven risk analysis"
                    if risk_state == "connected"
                    else "Risk analytics depend on holdings connectivity",
                },
                "bot_registry": {
                    "state": "connected",
                    "detail": f"{bot_count} bot(s) in registry",
                },
                "trade_proposals_enabled": portfolio_state == "connected"
                and market_state == "connected",
            }
        except Exception as e:
            logger.warning("data_access_context_error", error=str(e))
            return {}

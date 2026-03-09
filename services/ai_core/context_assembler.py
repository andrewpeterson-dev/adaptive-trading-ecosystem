"""Context assembler — gathers context from multiple sources for the AI Copilot."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class AssembledContext:
    """Full context assembled for an AI copilot turn."""
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
    """Assembles full context for a copilot turn from multiple sources."""

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
        """Assemble full context for a copilot turn."""
        from config.settings import get_settings
        settings = get_settings()

        ctx = AssembledContext()

        # 1. System context
        ctx.system_context = {
            "feature_flags": {
                "copilot_enabled": settings.feature_copilot_enabled,
                "research_mode": settings.feature_research_mode_enabled,
                "bot_mutations": settings.feature_bot_mutations_enabled,
                "paper_trade_proposals": settings.feature_paper_trade_proposals_enabled,
                "live_trade_proposals": settings.feature_live_trade_proposals_enabled,
                "slow_expert_mode": settings.feature_slow_expert_mode_enabled,
            },
            "mode": mode,
        }

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
                from db.copilot_models import CopilotPortfolioSnapshot
                from sqlalchemy import select

                async with get_session() as session:
                    stmt = select(CopilotPortfolioSnapshot).where(
                        CopilotPortfolioSnapshot.user_id == user_id
                    ).order_by(CopilotPortfolioSnapshot.snapshot_ts.desc()).limit(1)
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
            from db.copilot_models import CopilotConversationThread, CopilotConversationMessage
            from sqlalchemy import select

            async with get_session() as session:
                # Thread summary
                thread_result = await session.execute(
                    select(CopilotConversationThread).where(
                        CopilotConversationThread.id == thread_id,
                        CopilotConversationThread.user_id == user_id,
                    )
                )
                thread = thread_result.scalar_one_or_none()

                # Recent messages (last 20)
                msgs_result = await session.execute(
                    select(CopilotConversationMessage).where(
                        CopilotConversationMessage.thread_id == thread_id,
                    ).order_by(CopilotConversationMessage.created_at.desc()).limit(20)
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
            from db.copilot_models import CopilotMemoryItem
            from sqlalchemy import select

            async with get_session() as session:
                stmt = select(CopilotMemoryItem).where(
                    CopilotMemoryItem.user_id == user_id,
                ).order_by(CopilotMemoryItem.created_at.desc()).limit(10)
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
            from db.copilot_models import CopilotDocumentFile
            from sqlalchemy import select

            async with get_session() as session:
                stmt = select(CopilotDocumentFile).where(
                    CopilotDocumentFile.id.in_(doc_ids),
                    CopilotDocumentFile.user_id == user_id,
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

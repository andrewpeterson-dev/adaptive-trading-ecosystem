"""Memory retrieval — queries memory stores for relevant context."""

from __future__ import annotations

from typing import Optional

import structlog

from db.database import get_session

logger = structlog.get_logger(__name__)


class MemoryRetrieval:
    """Retrieves relevant memory items for context assembly."""

    def __init__(self, redis_client=None):
        self._redis = redis_client

    async def get_operational_context(self, user_id: int) -> dict:
        """Fetch operational context from Redis (hot cache).

        Keys: portfolio snapshot, positions, risk metrics, active bots, UI context.
        """
        if not self._redis:
            return {}

        keys = {
            "portfolio": f"cerberus:user:{user_id}:portfolio",
            "positions": f"cerberus:user:{user_id}:positions",
            "risk": f"cerberus:user:{user_id}:risk",
            "active_bots": f"cerberus:user:{user_id}:active_bots",
            "ui_context": f"cerberus:user:{user_id}:ui_context",
            "market_context": f"cerberus:user:{user_id}:market_context",
        }

        context = {}
        for label, key in keys.items():
            try:
                import json
                raw = await self._redis.get(key)
                if raw:
                    context[label] = json.loads(raw)
            except Exception:
                logger.debug("redis_key_miss", key=key)

        return context

    async def get_recent_messages(
        self, thread_id: str, user_id: int, limit: int = 20,
    ) -> list[dict]:
        """Fetch recent messages from the conversation thread."""
        from db.cerberus_models import CerberusConversationMessage
        from sqlalchemy import select

        async with get_session() as session:
            stmt = (
                select(CerberusConversationMessage)
                .where(
                    CerberusConversationMessage.thread_id == thread_id,
                    CerberusConversationMessage.user_id == user_id,
                )
                .order_by(CerberusConversationMessage.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            messages = result.scalars().all()

        return [
            {
                "role": m.role.value if hasattr(m.role, "value") else m.role,
                "content": m.content_md or "",
            }
            for m in reversed(messages)
        ]

    async def get_thread_summary(self, thread_id: str) -> Optional[str]:
        """Get the latest thread summary from memory items."""
        from db.cerberus_models import CerberusMemoryItem
        from sqlalchemy import select

        async with get_session() as session:
            stmt = (
                select(CerberusMemoryItem)
                .where(
                    CerberusMemoryItem.thread_id == thread_id,
                    CerberusMemoryItem.memory_type == "thread_summary",
                )
                .order_by(CerberusMemoryItem.created_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            item = result.scalar_one_or_none()

        return item.content_text if item else None

    async def search_semantic(
        self, user_id: int, query_embedding: list[float], limit: int = 5,
    ) -> list[dict]:
        """Search semantic memory using pgvector similarity.

        Falls back to text-based search if pgvector is not available.
        """
        from db.cerberus_models import CerberusMemoryItem
        from sqlalchemy import select, text

        async with get_session() as session:
            # Try pgvector cosine similarity if embedding column exists
            try:
                stmt = text("""
                    SELECT id, content_text, memory_type, metadata_json,
                           1 - (embedding <=> :embedding) AS similarity
                    FROM cerberus_memory_items
                    WHERE user_id = :user_id
                      AND embedding IS NOT NULL
                    ORDER BY embedding <=> :embedding
                    LIMIT :limit
                """)
                result = await session.execute(
                    stmt,
                    {
                        "user_id": user_id,
                        "embedding": str(query_embedding),
                        "limit": limit,
                    },
                )
                rows = result.fetchall()
                return [
                    {
                        "id": r[0],
                        "content": r[1],
                        "type": r[2],
                        "metadata": r[3],
                        "similarity": float(r[4]),
                    }
                    for r in rows
                ]
            except Exception:
                # pgvector not available — return empty
                logger.debug("pgvector_not_available_for_semantic_search")
                return []

"""Memory service — stores and retrieves semantic memory items for the cerberus."""
from __future__ import annotations

import uuid
from typing import Optional

import structlog
from sqlalchemy import select, func, desc

from db.database import get_session

logger = structlog.get_logger(__name__)


class MemoryService:
    """Manages cerberus memory items (facts, summaries, preferences, etc.)."""

    async def store_memory(
        self,
        user_id: int,
        kind: str,
        content: str,
        source_table: Optional[str] = None,
        source_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Store a new memory item in cerberus_memory_items."""
        from db.cerberus_models import CerberusMemoryItem

        item_id = str(uuid.uuid4())
        item = CerberusMemoryItem(
            id=item_id,
            user_id=user_id,
            kind=kind,
            content=content,
            source_table=source_table,
            source_id=source_id,
            metadata_json=metadata or {},
        )

        async with get_session() as session:
            session.add(item)

        logger.info(
            "memory_stored",
            user_id=user_id,
            kind=kind,
            item_id=item_id,
        )
        return {
            "id": item_id,
            "kind": kind,
            "content": content,
            "source_table": source_table,
            "source_id": source_id,
        }

    async def get_recent(
        self,
        user_id: int,
        kind: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict]:
        """Get recent memory items, optionally filtered by kind."""
        from db.cerberus_models import CerberusMemoryItem

        async with get_session() as session:
            stmt = (
                select(CerberusMemoryItem)
                .where(CerberusMemoryItem.user_id == user_id)
            )
            if kind:
                stmt = stmt.where(CerberusMemoryItem.kind == kind)
            stmt = stmt.order_by(desc(CerberusMemoryItem.created_at)).limit(limit)

            result = await session.execute(stmt)
            items = result.scalars().all()

        return [
            {
                "id": item.id,
                "kind": item.kind,
                "content": item.content,
                "source_table": item.source_table,
                "source_id": item.source_id,
                "metadata": item.metadata_json,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ]

    async def search_semantic(
        self,
        user_id: int,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """Search memory items by text similarity.

        Uses keyword matching today and can be upgraded to vector similarity
        once embeddings are populated.
        """
        from db.cerberus_models import CerberusMemoryItem

        pattern = f"%{query}%"
        async with get_session() as session:
            stmt = (
                select(CerberusMemoryItem)
                .where(
                    CerberusMemoryItem.user_id == user_id,
                    CerberusMemoryItem.content.ilike(pattern),
                )
                .order_by(desc(CerberusMemoryItem.created_at))
                .limit(top_k)
            )
            result = await session.execute(stmt)
            items = result.scalars().all()

        return [
            {
                "id": item.id,
                "kind": item.kind,
                "content": item.content,
                "source_table": item.source_table,
                "source_id": item.source_id,
                "metadata": item.metadata_json,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ]

    async def store_thread_summary(
        self,
        user_id: int,
        thread_id: str,
        summary: str,
    ) -> dict:
        """Store a conversation thread summary as a memory item."""
        return await self.store_memory(
            user_id=user_id,
            kind="thread_summary",
            content=summary,
            source_table="cerberus_conversation_threads",
            source_id=thread_id,
            metadata={"thread_id": thread_id},
        )

    async def should_summarize(self, thread_id: str) -> bool:
        """Return True if the thread has 20+ messages since last summary."""
        from db.cerberus_models import CerberusConversationMessage, CerberusMemoryItem

        async with get_session() as session:
            # Find the latest summary timestamp for this thread
            summary_stmt = (
                select(func.max(CerberusMemoryItem.created_at))
                .where(
                    CerberusMemoryItem.kind == "thread_summary",
                    CerberusMemoryItem.source_table == "cerberus_conversation_threads",
                    CerberusMemoryItem.source_id == thread_id,
                )
            )
            summary_result = await session.execute(summary_stmt)
            last_summary_at = summary_result.scalar()

            # Count messages since last summary
            msg_stmt = (
                select(func.count())
                .select_from(CerberusConversationMessage)
                .where(CerberusConversationMessage.thread_id == thread_id)
            )
            if last_summary_at:
                msg_stmt = msg_stmt.where(
                    CerberusConversationMessage.created_at > last_summary_at,
                )
            msg_result = await session.execute(msg_stmt)
            count = msg_result.scalar() or 0

        return count >= 20

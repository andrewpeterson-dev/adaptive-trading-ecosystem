"""Memory service — stores and retrieves semantic memory items for the copilot."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

import structlog
from sqlalchemy import select, func, desc

from db.database import get_session

logger = structlog.get_logger(__name__)


class MemoryService:
    """Manages copilot memory items (facts, summaries, preferences, etc.)."""

    async def store_memory(
        self,
        user_id: int,
        kind: str,
        content: str,
        source_table: Optional[str] = None,
        source_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Store a new memory item in copilot_memory_items."""
        from db.copilot_models import CopilotMemoryItem

        item_id = str(uuid.uuid4())
        item = CopilotMemoryItem(
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
        from db.copilot_models import CopilotMemoryItem

        async with get_session() as session:
            stmt = (
                select(CopilotMemoryItem)
                .where(CopilotMemoryItem.user_id == user_id)
            )
            if kind:
                stmt = stmt.where(CopilotMemoryItem.kind == kind)
            stmt = stmt.order_by(desc(CopilotMemoryItem.created_at)).limit(limit)

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

        Currently uses SQL LIKE as a placeholder.  Will be replaced with
        pgvector cosine similarity once embeddings are populated.
        """
        from db.copilot_models import CopilotMemoryItem

        pattern = f"%{query}%"
        async with get_session() as session:
            stmt = (
                select(CopilotMemoryItem)
                .where(
                    CopilotMemoryItem.user_id == user_id,
                    CopilotMemoryItem.content.ilike(pattern),
                )
                .order_by(desc(CopilotMemoryItem.created_at))
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
            source_table="copilot_conversation_threads",
            source_id=thread_id,
            metadata={"thread_id": thread_id},
        )

    async def should_summarize(self, thread_id: str) -> bool:
        """Return True if the thread has 20+ messages since last summary."""
        from db.copilot_models import CopilotConversationMessage, CopilotMemoryItem

        async with get_session() as session:
            # Find the latest summary timestamp for this thread
            summary_stmt = (
                select(func.max(CopilotMemoryItem.created_at))
                .where(
                    CopilotMemoryItem.kind == "thread_summary",
                    CopilotMemoryItem.source_table == "copilot_conversation_threads",
                    CopilotMemoryItem.source_id == thread_id,
                )
            )
            summary_result = await session.execute(summary_stmt)
            last_summary_at = summary_result.scalar()

            # Count messages since last summary
            msg_stmt = (
                select(func.count())
                .select_from(CopilotConversationMessage)
                .where(CopilotConversationMessage.thread_id == thread_id)
            )
            if last_summary_at:
                msg_stmt = msg_stmt.where(
                    CopilotConversationMessage.created_at > last_summary_at,
                )
            msg_result = await session.execute(msg_stmt)
            count = msg_result.scalar() or 0

        return count >= 20

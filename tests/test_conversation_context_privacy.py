"""Regression test for conversation-context user isolation."""

import asyncio
import uuid
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from db.cerberus_models import (
    CerberusConversationMessage,
    CerberusConversationThread,
    ConversationMode,
    MessageRole,
)
from db.database import Base
from db.models import User
from services.ai_core.context_assembler import ContextAssembler


def test_conversation_context_filters_messages_to_current_user(monkeypatch):
    async def _run() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            owner = User(email="owner@example.com", password_hash="hash", display_name="Owner")
            attacker = User(email="attacker@example.com", password_hash="hash", display_name="Attacker")
            session.add_all([owner, attacker])
            await session.flush()

            thread_id = str(uuid.uuid4())
            session.add(
                CerberusConversationThread(
                    id=thread_id,
                    user_id=owner.id,
                    mode=ConversationMode.CHAT,
                )
            )
            session.add_all(
                [
                    CerberusConversationMessage(
                        id=str(uuid.uuid4()),
                        thread_id=thread_id,
                        user_id=owner.id,
                        role=MessageRole.USER,
                        content_md="owner message",
                    ),
                    CerberusConversationMessage(
                        id=str(uuid.uuid4()),
                        thread_id=thread_id,
                        user_id=attacker.id,
                        role=MessageRole.USER,
                        content_md="attacker message",
                    ),
                ]
            )
            await session.commit()

        @asynccontextmanager
        async def _mock_get_session():
            async with session_factory() as session:
                yield session

        import db.database

        monkeypatch.setattr(db.database, "get_session", _mock_get_session)

        assembler = ContextAssembler()
        context = await assembler._get_conversation_context(thread_id, owner.id)

        assert [message["content"] for message in context["recent_messages"]] == ["owner message"]

        await engine.dispose()

    asyncio.run(_run())

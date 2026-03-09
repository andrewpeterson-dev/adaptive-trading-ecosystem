"""Tests for the AI chat API routes (api/routes/ai_chat.py)."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base
from db.models import User  # noqa: F401
from db.cerberus_models import (
    CerberusConversationThread,
    CerberusConversationMessage,
    ConversationMode,
    MessageRole,
)

TEST_DB_URL = "sqlite+aiosqlite:///"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(session_factory):
    async with session_factory() as sess:
        yield sess


async def _seed_user(session: AsyncSession) -> int:
    from db.models import User
    user = User(email="chat@example.com", password_hash="hash", display_name="ChatUser")
    session.add(user)
    await session.flush()
    return user.id


async def _seed_thread(session: AsyncSession, user_id: int) -> str:
    thread_id = str(uuid.uuid4())
    thread = CerberusConversationThread(
        id=thread_id,
        user_id=user_id,
        title="Test Thread",
        mode=ConversationMode.CHAT,
    )
    session.add(thread)
    await session.flush()
    return thread_id


async def _seed_messages(session: AsyncSession, thread_id: str, user_id: int, count: int = 3):
    for i in range(count):
        msg = CerberusConversationMessage(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            user_id=user_id,
            role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
            content_md=f"Message {i}",
            model_name="gpt-5.4" if i % 2 == 1 else None,
        )
        session.add(msg)
    await session.flush()


def _build_app(session_factory) -> FastAPI:
    """Build a test FastAPI app with the AI chat router and a mock auth middleware."""
    from api.routes.ai_chat import router

    app = FastAPI()

    @app.middleware("http")
    async def mock_auth(request: Request, call_next):
        request.state.user_id = 1  # Fixed user_id for testing
        return await call_next(request)

    # Patch get_session for list_threads and get_thread_messages
    @asynccontextmanager
    async def _mock_get_session():
        async with session_factory() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise

    app.include_router(router, prefix="/api/ai")
    return app, _mock_get_session


# ---------------------------------------------------------------------------
# Chat endpoint tests
# ---------------------------------------------------------------------------

class TestChatEndpoint:
    @pytest.mark.asyncio
    async def test_chat_returns_thread_and_turn_id(self, session, session_factory):
        uid = await _seed_user(session)
        await session.commit()

        # Mock the ChatController
        mock_result = MagicMock()
        mock_result.thread_id = str(uuid.uuid4())
        mock_result.turn_id = str(uuid.uuid4())
        mock_result.to_message_dict.return_value = {
            "turnId": mock_result.turn_id,
            "markdown": "Hello! How can I help?",
            "citations": [],
            "structuredTradeSignals": [],
            "charts": [],
            "uiCommands": [],
            "warnings": [],
        }

        mock_controller = MagicMock()
        mock_controller.handle_turn = AsyncMock(return_value=mock_result)

        app, mock_get_session = _build_app(session_factory)

        with (
            patch("api.routes.ai_chat._get_controller", return_value=mock_controller),
            patch("api.routes.ai_chat.get_session" if False else "db.database.get_session", mock_get_session),
        ):
            # Override user_id in the middleware to match seeded user
            @app.middleware("http")
            async def set_uid(request, call_next):
                request.state.user_id = uid
                return await call_next(request)

            client = TestClient(app)
            response = client.post("/api/ai/chat", json={
                "message": "Hello",
                "mode": "chat",
            })

        assert response.status_code == 200
        data = response.json()
        assert "threadId" in data
        assert "turnId" in data
        assert "streamChannel" in data
        assert "message" in data

    @pytest.mark.asyncio
    async def test_chat_calls_controller_handle_turn(self, session, session_factory):
        uid = await _seed_user(session)
        await session.commit()

        mock_result = MagicMock()
        mock_result.thread_id = "thread-1"
        mock_result.turn_id = "turn-1"
        mock_result.to_message_dict.return_value = {"markdown": "response"}

        mock_controller = MagicMock()
        mock_controller.handle_turn = AsyncMock(return_value=mock_result)

        app, mock_get_session = _build_app(session_factory)

        with patch("api.routes.ai_chat._get_controller", return_value=mock_controller):
            client = TestClient(app)
            response = client.post("/api/ai/chat", json={
                "message": "What is my portfolio?",
                "mode": "chat",
                "allowSlowExpertMode": False,
            })

        assert response.status_code == 200
        mock_controller.handle_turn.assert_called_once()
        call_kwargs = mock_controller.handle_turn.call_args
        assert call_kwargs.kwargs["message"] == "What is my portfolio?"
        assert call_kwargs.kwargs["mode"] == "chat"


# ---------------------------------------------------------------------------
# Threads listing tests
# ---------------------------------------------------------------------------

class TestThreadsListing:
    @pytest.mark.asyncio
    async def test_list_threads_returns_list(self, session, session_factory):
        uid = await _seed_user(session)
        await _seed_thread(session, uid)
        await _seed_thread(session, uid)
        await session.commit()

        app, mock_get_session = _build_app(session_factory)

        # Override middleware to use correct user_id
        @app.middleware("http")
        async def set_uid(request, call_next):
            request.state.user_id = uid
            return await call_next(request)

        with patch("db.database.get_session", mock_get_session):
            client = TestClient(app)
            response = client.get("/api/ai/threads")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_list_threads_empty(self, session, session_factory):
        uid = await _seed_user(session)
        await session.commit()

        app, mock_get_session = _build_app(session_factory)

        @app.middleware("http")
        async def set_uid(request, call_next):
            request.state.user_id = uid
            return await call_next(request)

        with patch("db.database.get_session", mock_get_session):
            client = TestClient(app)
            response = client.get("/api/ai/threads")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_thread_response_shape(self, session, session_factory):
        uid = await _seed_user(session)
        await _seed_thread(session, uid)
        await session.commit()

        app, mock_get_session = _build_app(session_factory)

        @app.middleware("http")
        async def set_uid(request, call_next):
            request.state.user_id = uid
            return await call_next(request)

        with patch("db.database.get_session", mock_get_session):
            client = TestClient(app)
            response = client.get("/api/ai/threads")

        data = response.json()
        thread = data[0]
        assert "id" in thread
        assert "title" in thread
        assert "mode" in thread
        assert "createdAt" in thread
        assert "updatedAt" in thread


# ---------------------------------------------------------------------------
# Thread messages tests
# ---------------------------------------------------------------------------

class TestThreadMessages:
    @pytest.mark.asyncio
    async def test_get_thread_messages(self, session, session_factory):
        uid = await _seed_user(session)
        thread_id = await _seed_thread(session, uid)
        await _seed_messages(session, thread_id, uid, count=5)
        await session.commit()

        app, mock_get_session = _build_app(session_factory)

        @app.middleware("http")
        async def set_uid(request, call_next):
            request.state.user_id = uid
            return await call_next(request)

        with patch("db.database.get_session", mock_get_session):
            client = TestClient(app)
            response = client.get(f"/api/ai/threads/{thread_id}/messages")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 5

    @pytest.mark.asyncio
    async def test_message_response_shape(self, session, session_factory):
        uid = await _seed_user(session)
        thread_id = await _seed_thread(session, uid)
        await _seed_messages(session, thread_id, uid, count=1)
        await session.commit()

        app, mock_get_session = _build_app(session_factory)

        @app.middleware("http")
        async def set_uid(request, call_next):
            request.state.user_id = uid
            return await call_next(request)

        with patch("db.database.get_session", mock_get_session):
            client = TestClient(app)
            response = client.get(f"/api/ai/threads/{thread_id}/messages")

        data = response.json()
        msg = data[0]
        assert "id" in msg
        assert "role" in msg
        assert "contentMd" in msg
        assert "createdAt" in msg

    @pytest.mark.asyncio
    async def test_messages_limit(self, session, session_factory):
        uid = await _seed_user(session)
        thread_id = await _seed_thread(session, uid)
        await _seed_messages(session, thread_id, uid, count=10)
        await session.commit()

        app, mock_get_session = _build_app(session_factory)

        @app.middleware("http")
        async def set_uid(request, call_next):
            request.state.user_id = uid
            return await call_next(request)

        with patch("db.database.get_session", mock_get_session):
            client = TestClient(app)
            response = client.get(f"/api/ai/threads/{thread_id}/messages?limit=3")

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 3

    @pytest.mark.asyncio
    async def test_messages_empty_thread(self, session, session_factory):
        uid = await _seed_user(session)
        thread_id = await _seed_thread(session, uid)
        await session.commit()

        app, mock_get_session = _build_app(session_factory)

        @app.middleware("http")
        async def set_uid(request, call_next):
            request.state.user_id = uid
            return await call_next(request)

        with patch("db.database.get_session", mock_get_session):
            client = TestClient(app)
            response = client.get(f"/api/ai/threads/{thread_id}/messages")

        assert response.status_code == 200
        assert response.json() == []

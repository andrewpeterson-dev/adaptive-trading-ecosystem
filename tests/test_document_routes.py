from __future__ import annotations

from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from config.settings import get_settings
from db.cerberus_models import CerberusDocumentFile
from db.database import Base
from db.models import User
from services.ai_core.documents.upload import MAX_DIRECT_UPLOAD_BYTES

TEST_DB_URL = "sqlite+aiosqlite:///"


@pytest.fixture
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


@pytest.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def session(session_factory):
    async with session_factory() as sess:
        yield sess


async def _seed_user(session: AsyncSession) -> int:
    user = User(email="documents@example.com", password_hash="hash", display_name="Docs")
    session.add(user)
    await session.flush()
    return user.id


def _build_app(session_factory, user_id: int):
    from api.routes.documents import router

    app = FastAPI()

    @app.middleware("http")
    async def mock_auth(request: Request, call_next):
        request.state.user_id = user_id
        return await call_next(request)

    @asynccontextmanager
    async def _mock_get_session():
        async with session_factory() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise

    app.include_router(router, prefix="/api/documents")
    return app, _mock_get_session


class TestDocumentRoutes:
    @pytest.mark.anyio
    async def test_upload_rejects_unsupported_mime_type(self, session, session_factory):
        user_id = await _seed_user(session)
        await session.commit()
        app, mock_get_session = _build_app(session_factory, user_id)

        settings = get_settings()
        old_jwt_secret = settings.jwt_secret
        settings.jwt_secret = "test-jwt-secret-for-document-routes"
        try:
            from unittest.mock import patch

            with patch("services.ai_core.documents.upload.get_session", mock_get_session):
                client = TestClient(app)
                response = client.post(
                    "/api/documents/upload",
                    json={"filename": "payload.exe", "mimeType": "application/x-msdownload"},
                )
        finally:
            settings.jwt_secret = old_jwt_secret

        assert response.status_code == 400
        assert response.json()["detail"] == "Unsupported file type"

    @pytest.mark.anyio
    async def test_upload_sanitizes_filename_and_infers_supported_mime(self, session, session_factory):
        user_id = await _seed_user(session)
        await session.commit()
        app, mock_get_session = _build_app(session_factory, user_id)

        settings = get_settings()
        old_jwt_secret = settings.jwt_secret
        settings.jwt_secret = "test-jwt-secret-for-document-routes"
        try:
            from unittest.mock import patch

            with patch("services.ai_core.documents.upload.get_session", mock_get_session):
                client = TestClient(app)
                response = client.post(
                    "/api/documents/upload",
                    json={"filename": "../Quarterly Report.PDF", "mimeType": "application/octet-stream"},
                )
        finally:
            settings.jwt_secret = old_jwt_secret

        assert response.status_code == 200
        payload = response.json()
        assert payload["uploadUrl"].startswith("/api/documents/upload/")

        result = await session.execute(select(CerberusDocumentFile))
        document = result.scalar_one()
        assert document.original_filename == "Quarterly Report.PDF"
        assert document.mime_type == "application/pdf"
        assert document.storage_key.endswith(".pdf")

    @pytest.mark.anyio
    async def test_direct_upload_rejects_oversized_payload(self, session, session_factory):
        user_id = await _seed_user(session)
        await session.commit()
        app, mock_get_session = _build_app(session_factory, user_id)

        settings = get_settings()
        old_jwt_secret = settings.jwt_secret
        settings.jwt_secret = "test-jwt-secret-for-document-routes"
        try:
            from unittest.mock import patch

            with patch("services.ai_core.documents.upload.get_session", mock_get_session):
                client = TestClient(app)
                create_response = client.post(
                    "/api/documents/upload",
                    json={"filename": "notes.txt", "mimeType": "text/plain"},
                )

                upload_url = create_response.json()["uploadUrl"]
                parsed = urlparse(upload_url)
                token = parse_qs(parsed.query)["token"][0]
                response = client.put(
                    parsed.path,
                    params={"token": token},
                    data=b"x" * (MAX_DIRECT_UPLOAD_BYTES + 1),
                    headers={"Content-Type": "application/octet-stream"},
                )
        finally:
            settings.jwt_secret = old_jwt_secret

        assert create_response.status_code == 200
        assert response.status_code == 400
        assert "Upload exceeds" in response.json()["detail"]

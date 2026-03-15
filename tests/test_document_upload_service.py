from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from config.settings import get_settings
from db.cerberus_models import CerberusDocumentFile
from db.database import Base
from db.models import User
from services.ai_core.documents import upload as upload_module
from services.ai_core.documents.upload import DocumentUploadService

TEST_DB_URL = "sqlite+aiosqlite:///"


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
    user = User(email="documents@example.com", password_hash="hash", display_name="Docs")
    session.add(user)
    await session.flush()
    return user.id


def _patch_get_session(session_factory):
    @asynccontextmanager
    async def _mock_get_session():
        async with session_factory() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise

    return _mock_get_session


@pytest.mark.asyncio
async def test_create_upload_sanitizes_filename_and_persists_metadata(session, session_factory, monkeypatch):
    user_id = await _seed_user(session)
    await session.commit()

    settings = get_settings()
    old_jwt_secret = settings.jwt_secret
    old_s3_bucket = settings.s3_bucket
    settings.jwt_secret = "unit-test-secret-0123456789abcdef"
    settings.s3_bucket = ""

    monkeypatch.setattr(upload_module, "get_session", _patch_get_session(session_factory))
    service = DocumentUploadService()

    try:
        payload = await service.create_upload(
            user_id=user_id,
            filename="../Quarterly Report.PDF",
            mime_type="application/pdf",
        )
    finally:
        settings.jwt_secret = old_jwt_secret
        settings.s3_bucket = old_s3_bucket

    assert payload["filename"] == "Quarterly Report.PDF"
    assert payload["mimeType"] == "application/pdf"

    result = await session.execute(select(CerberusDocumentFile))
    doc = result.scalar_one()
    assert doc.original_filename == "Quarterly Report.PDF"
    assert doc.mime_type == "application/pdf"
    assert doc.storage_key.endswith(".pdf")


@pytest.mark.asyncio
async def test_create_upload_rejects_unsupported_mime_type(monkeypatch, session_factory):
    monkeypatch.setattr(upload_module, "get_session", _patch_get_session(session_factory))
    service = DocumentUploadService()

    with pytest.raises(ValueError, match="Unsupported mime type"):
        await service.create_upload(
            user_id=1,
            filename="notes.txt",
            mime_type="application/octet-stream+binary",
        )


@pytest.mark.asyncio
async def test_store_local_upload_rejects_oversized_content(session, session_factory, monkeypatch, tmp_path):
    user_id = await _seed_user(session)
    document = CerberusDocumentFile(
        id="doc-1",
        user_id=user_id,
        original_filename="notes.txt",
        mime_type="text/plain",
        storage_key="documents/1/doc-1.txt",
        status="pending",
    )
    session.add(document)
    await session.commit()

    monkeypatch.setattr(upload_module, "get_session", _patch_get_session(session_factory))
    monkeypatch.setattr(upload_module, "_LOCAL_UPLOAD_DIR", Path(tmp_path))
    service = DocumentUploadService()

    with pytest.raises(ValueError, match="Upload exceeds 10 MB limit"):
        await service.store_local_upload(
            document_id="doc-1",
            user_id=user_id,
            content=b"x" * (10 * 1024 * 1024 + 1),
        )

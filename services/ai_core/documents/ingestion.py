"""Document ingestion pipeline — parse, chunk, embed, and store document chunks."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog
from sqlalchemy import delete, select

from config.settings import get_settings
from db.database import get_session

logger = structlog.get_logger(__name__)

# Local upload directory (mirrors upload.py)
_LOCAL_UPLOAD_DIR = Path("uploads/documents")


class DocumentIngestionService:
    """Full ingestion pipeline: fetch file -> parse -> chunk -> embed -> store."""

    def __init__(self):
        self._settings = get_settings()

    async def ingest(self, document_id: str, user_id: int) -> dict:
        """Run the full ingestion pipeline for a document.

        Steps:
          1. Fetch file (from local storage or S3)
          2. Parse text from the file
          3. Split text into chunks
          4. Generate embeddings for each chunk
          5. Store chunks in the database
          6. Update document status to 'indexed' or 'failed'
        """
        from db.cerberus_models import (
            CerberusDocumentFile,
            CerberusDocumentChunk,
            DocumentStatus,
        )

        try:
            # 1. Fetch the document record
            async with get_session() as session:
                stmt = select(CerberusDocumentFile).where(
                    CerberusDocumentFile.id == document_id,
                    CerberusDocumentFile.user_id == user_id,
                )
                result = await session.execute(stmt)
                doc = result.scalar_one_or_none()

            if not doc:
                raise ValueError(f"Document {document_id} not found")

            storage_key = doc.storage_key
            mime_type = doc.mime_type or "text/plain"

            # 2. Get the file path
            filepath = await self._fetch_file(storage_key)

            # 3. Parse
            from services.ai_core.documents.parsers import parse_document

            text = parse_document(filepath, mime_type)

            if not text.strip():
                raise ValueError("Document produced no extractable text")

            # 4. Chunk
            from services.ai_core.documents.chunker import chunk_document

            chunks = chunk_document(text)

            # 5. Embed (best-effort; skip if API key not configured)
            embeddings: list[Optional[list[float]]] = [None] * len(chunks)
            if self._settings.openai_api_key:
                try:
                    from services.ai_core.memory.embeddings import EmbeddingService

                    embedding_svc = EmbeddingService()
                    chunk_texts = [c["content"] for c in chunks]
                    embeddings = await embedding_svc.embed(chunk_texts)
                except Exception:
                    logger.warning(
                        "embedding_skipped",
                        document_id=document_id,
                        reason="embedding_error",
                    )

            # 6. Store chunks
            async with get_session() as session:
                await session.execute(
                    delete(CerberusDocumentChunk).where(
                        CerberusDocumentChunk.document_id == document_id,
                        CerberusDocumentChunk.user_id == user_id,
                    )
                )
                for chunk_data, embedding in zip(chunks, embeddings):
                    chunk_record = CerberusDocumentChunk(
                        id=str(uuid.uuid4()),
                        document_id=document_id,
                        user_id=user_id,
                        chunk_index=chunk_data["chunk_index"],
                        page_number=chunk_data.get("estimated_page"),
                        heading=chunk_data.get("heading"),
                        content=chunk_data["content"],
                        metadata_json={
                            "estimated_page": chunk_data.get("estimated_page"),
                            "heading": chunk_data.get("heading"),
                        },
                        embedding_json=json.dumps(embedding) if embedding else None,
                    )
                    session.add(chunk_record)

            # 7. Update document status
            async with get_session() as session:
                stmt = select(CerberusDocumentFile).where(
                    CerberusDocumentFile.id == document_id,
                    CerberusDocumentFile.user_id == user_id,
                )
                result = await session.execute(stmt)
                doc = result.scalar_one()
                doc.status = DocumentStatus.INDEXED
                doc.indexed_at = datetime.utcnow()

            logger.info(
                "document_ingested",
                document_id=document_id,
                chunk_count=len(chunks),
            )
            return {
                "document_id": document_id,
                "status": "indexed",
                "chunk_count": len(chunks),
            }

        except Exception as exc:
            logger.exception("ingestion_failed", document_id=document_id)
            # Mark document as failed
            try:
                from db.cerberus_models import CerberusDocumentFile, DocumentStatus

                async with get_session() as session:
                    stmt = select(CerberusDocumentFile).where(
                        CerberusDocumentFile.id == document_id,
                        CerberusDocumentFile.user_id == user_id,
                    )
                    result = await session.execute(stmt)
                    doc = result.scalar_one_or_none()
                    if doc:
                        doc.status = DocumentStatus.FAILED
                        doc.metadata_json = {
                            **(doc.metadata_json or {}),
                            "error": str(exc),
                        }
            except Exception:
                logger.exception("failed_to_update_status", document_id=document_id)
            raise

    async def _fetch_file(self, storage_key: str) -> str:
        """Return the local filesystem path for the document.

        Downloads from S3 if configured, otherwise uses local storage.
        """
        if self._settings.s3_bucket:
            return await self._download_from_s3(storage_key)
        else:
            local_path = _LOCAL_UPLOAD_DIR / storage_key
            if not local_path.exists():
                raise FileNotFoundError(f"Local file not found: {local_path}")
            return str(local_path)

    async def _download_from_s3(self, storage_key: str) -> str:
        """Download a file from S3 to a temporary local path."""
        import tempfile

        import boto3

        s3_client = boto3.client(
            "s3",
            region_name=self._settings.s3_region,
            aws_access_key_id=self._settings.s3_access_key,
            aws_secret_access_key=self._settings.s3_secret_key,
            endpoint_url=self._settings.s3_endpoint_url or None,
        )

        suffix = Path(storage_key).suffix
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        s3_client.download_file(
            self._settings.s3_bucket,
            storage_key,
            tmp.name,
        )
        return tmp.name

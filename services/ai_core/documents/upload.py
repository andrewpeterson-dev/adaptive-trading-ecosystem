"""Document upload service — creates records and storage paths for uploaded files."""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog
from sqlalchemy import select

from config.settings import get_settings
from db.database import get_session

logger = structlog.get_logger(__name__)

# Local upload directory for dev (when S3 is not configured)
_LOCAL_UPLOAD_DIR = Path("uploads/documents")


class DocumentUploadService:
    """Manages document upload lifecycle."""

    def __init__(self):
        self._settings = get_settings()

    async def create_upload(
        self,
        user_id: int,
        filename: str,
        mime_type: Optional[str] = None,
    ) -> dict:
        """Create a document record and return an upload destination.

        In production, returns a presigned S3 URL.
        In dev (no S3 configured), returns a local file path.
        """
        from db.copilot_models import CopilotDocumentFile

        doc_id = str(uuid.uuid4())
        ext = Path(filename).suffix
        storage_key = f"documents/{user_id}/{doc_id}{ext}"

        doc = CopilotDocumentFile(
            id=doc_id,
            user_id=user_id,
            original_filename=filename,
            mime_type=mime_type,
            storage_key=storage_key,
            status="pending",
        )

        async with get_session() as session:
            session.add(doc)

        # Determine upload destination
        if self._settings.s3_bucket:
            upload_url = await self._generate_presigned_url(storage_key)
        else:
            # Local dev: ensure directory exists and return local path
            local_path = _LOCAL_UPLOAD_DIR / storage_key
            local_path.parent.mkdir(parents=True, exist_ok=True)
            upload_url = str(local_path)

        logger.info(
            "upload_created",
            document_id=doc_id,
            user_id=user_id,
            filename=filename,
        )

        return {
            "document_id": doc_id,
            "upload_url": upload_url,
            "storage_key": storage_key,
        }

    async def finalize_upload(self, document_id: str, user_id: int) -> dict:
        """Mark a document as processing and trigger ingestion."""
        from db.copilot_models import CopilotDocumentFile, DocumentStatus

        async with get_session() as session:
            stmt = select(CopilotDocumentFile).where(
                CopilotDocumentFile.id == document_id,
                CopilotDocumentFile.user_id == user_id,
            )
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()

            if not doc:
                raise ValueError(f"Document {document_id} not found")

            doc.status = DocumentStatus.PROCESSING

        logger.info(
            "upload_finalized",
            document_id=document_id,
            user_id=user_id,
        )

        # Trigger ingestion (inline for now; move to Celery task later)
        from services.ai_core.documents.ingestion import DocumentIngestionService

        ingestion = DocumentIngestionService()
        await ingestion.ingest(document_id, user_id)

        return {"document_id": document_id, "status": "processing"}

    async def _generate_presigned_url(self, storage_key: str) -> str:
        """Generate a presigned S3 PUT URL for the given storage key."""
        try:
            import boto3

            s3_client = boto3.client(
                "s3",
                region_name=self._settings.s3_region,
                aws_access_key_id=self._settings.s3_access_key,
                aws_secret_access_key=self._settings.s3_secret_key,
                endpoint_url=self._settings.s3_endpoint_url or None,
            )
            url = s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self._settings.s3_bucket,
                    "Key": storage_key,
                },
                ExpiresIn=3600,
            )
            return url
        except Exception:
            logger.exception("presigned_url_error", storage_key=storage_key)
            raise

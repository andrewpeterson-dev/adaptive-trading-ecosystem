"""Document upload service — creates records and storage paths for uploaded files."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import jwt
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
        from db.cerberus_models import CerberusDocumentFile

        doc_id = str(uuid.uuid4())
        ext = Path(filename).suffix
        storage_key = f"documents/{user_id}/{doc_id}{ext}"

        doc = CerberusDocumentFile(
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
            upload_url = self._generate_local_upload_url(document_id=doc_id, user_id=user_id)

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
            "documentId": doc_id,
            "uploadUrl": upload_url,
        }

    async def finalize_upload(self, document_id: str, user_id: int) -> dict:
        """Mark a document as processing so ingestion can begin."""
        from db.cerberus_models import CerberusDocumentFile, DocumentStatus

        async with get_session() as session:
            stmt = select(CerberusDocumentFile).where(
                CerberusDocumentFile.id == document_id,
                CerberusDocumentFile.user_id == user_id,
            )
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()

            if not doc:
                raise ValueError(f"Document {document_id} not found")

            if doc.status == DocumentStatus.INDEXED:
                logger.info("upload_finalize_skipped", document_id=document_id, user_id=user_id, reason="already_indexed")
                return {"document_id": document_id, "status": "indexed"}
            if doc.status == DocumentStatus.PROCESSING:
                logger.info("upload_finalize_skipped", document_id=document_id, user_id=user_id, reason="already_processing")
                return {"document_id": document_id, "status": "processing"}

            doc.status = DocumentStatus.PROCESSING

        logger.info(
            "upload_finalized",
            document_id=document_id,
            user_id=user_id,
        )

        return {"document_id": document_id, "status": "processing"}

    async def ingest_upload(self, document_id: str, user_id: int) -> dict:
        """Run ingestion for a finalized upload."""
        from services.ai_core.documents.ingestion import DocumentIngestionService

        ingestion = DocumentIngestionService()
        return await ingestion.ingest(document_id, user_id)

    def _generate_local_upload_url(self, *, document_id: str, user_id: int) -> str:
        token = jwt.encode(
            {
                "sub": "document-upload",
                "document_id": document_id,
                "user_id": user_id,
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            self._settings.jwt_secret,
            algorithm="HS256",
        )
        return f"/api/documents/upload/{document_id}/content?token={token}"

    def verify_local_upload_token(self, *, document_id: str, token: str) -> int:
        try:
            payload = jwt.decode(token, self._settings.jwt_secret, algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise ValueError("Invalid upload token") from exc

        if payload.get("sub") != "document-upload":
            raise ValueError("Invalid upload token")
        if payload.get("document_id") != document_id:
            raise ValueError("Upload token does not match document")

        user_id = payload.get("user_id")
        if user_id is None:
            raise ValueError("Invalid upload token")
        return int(user_id)

    async def store_local_upload(self, *, document_id: str, user_id: int, content: bytes) -> dict:
        """Persist a direct-uploaded file to local storage when S3 is unavailable."""
        from db.cerberus_models import CerberusDocumentFile

        async with get_session() as session:
            result = await session.execute(
                select(CerberusDocumentFile).where(
                    CerberusDocumentFile.id == document_id,
                    CerberusDocumentFile.user_id == user_id,
                )
            )
            doc = result.scalar_one_or_none()
            if not doc:
                raise ValueError(f"Document {document_id} not found")

        local_path = _LOCAL_UPLOAD_DIR / doc.storage_key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(content)

        logger.info(
            "local_upload_stored",
            document_id=document_id,
            user_id=user_id,
            bytes=len(content),
            path=str(local_path),
        )
        return {"document_id": document_id, "stored": True}

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

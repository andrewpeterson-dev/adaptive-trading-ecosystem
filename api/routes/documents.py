"""Document upload and search endpoints."""
from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete

logger = structlog.get_logger(__name__)
router = APIRouter()


class UploadRequest(BaseModel):
    filename: str
    mimeType: str


class SearchRequest(BaseModel):
    query: str
    documentIds: list[str] = Field(default_factory=list)
    topK: int = 8


@router.post("/upload")
async def upload_document(request: Request, body: UploadRequest):
    """Request a presigned upload URL for a document."""
    from services.ai_core.documents.upload import DocumentUploadService

    user_id = request.state.user_id
    filename = body.filename.strip()
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")

    service = DocumentUploadService()
    result = await service.create_upload(user_id, filename, body.mimeType)
    logger.info("document_upload_requested", user_id=user_id, filename=filename)
    return result


@router.put("/upload/{document_id}/content")
async def upload_document_content(
    document_id: str,
    token: str = Query(..., min_length=16),
    content: bytes = Body(...),
):
    """Accept direct uploads when S3 is not configured."""
    from services.ai_core.documents.upload import DocumentUploadService

    service = DocumentUploadService()
    if service._settings.s3_bucket:
        raise HTTPException(status_code=400, detail="Direct upload is disabled when S3 storage is configured")

    try:
        user_id = service.verify_local_upload_token(document_id=document_id, token=token)
        if not content:
            raise HTTPException(status_code=400, detail="Upload body is empty")
        await service.store_local_upload(document_id=document_id, user_id=user_id, content=content)
        return {"documentId": document_id, "stored": True}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


async def _run_document_ingestion(document_id: str, user_id: int) -> None:
    from services.ai_core.documents.upload import DocumentUploadService

    service = DocumentUploadService()
    try:
        await service.ingest_upload(document_id, user_id)
    except Exception:
        logger.exception("document_ingestion_background_failed", document_id=document_id, user_id=user_id)


@router.post("/{document_id}/finalize")
async def finalize_upload(
    request: Request,
    document_id: str,
    background_tasks: BackgroundTasks,
):
    """Finalize an upload and trigger ingestion."""
    from services.ai_core.documents.upload import DocumentUploadService

    user_id = request.state.user_id
    service = DocumentUploadService()

    try:
        result = await service.finalize_upload(document_id, user_id)
        if result.get("status") == "processing":
            background_tasks.add_task(_run_document_ingestion, document_id, user_id)
        logger.info(
            "document_upload_finalized",
            document_id=document_id,
            user_id=user_id,
            status=result.get("status"),
        )
        return {"status": result.get("status", "processing"), "documentId": document_id}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{document_id}/status")
async def document_status(request: Request, document_id: str):
    """Check document ingestion status."""
    from db.database import get_session
    from db.cerberus_models import CerberusDocumentFile
    from sqlalchemy import select

    user_id = request.state.user_id
    async with get_session() as session:
        result = await session.execute(
            select(CerberusDocumentFile).where(
                CerberusDocumentFile.id == document_id,
                CerberusDocumentFile.user_id == user_id,
            )
        )
        doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "id": doc.id,
        "filename": doc.original_filename,
        "status": doc.status.value if doc.status else None,
        "indexedAt": doc.indexed_at.isoformat() if doc.indexed_at else None,
    }


@router.post("/search")
async def search_documents(request: Request, body: SearchRequest):
    """Search document chunks by text similarity."""
    from db.database import get_session
    from db.cerberus_models import CerberusDocumentChunk
    from sqlalchemy import select

    user_id = request.state.user_id
    query = body.query.strip()
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="query must be at least 2 characters")

    top_k = max(1, min(int(body.topK or 8), 25))
    document_ids = [doc_id for doc_id in dict.fromkeys(body.documentIds) if doc_id]
    if len(document_ids) > 50:
        raise HTTPException(status_code=400, detail="Too many documentIds supplied")

    async with get_session() as session:
        stmt = select(CerberusDocumentChunk).where(
            CerberusDocumentChunk.user_id == user_id,
            CerberusDocumentChunk.content.ilike(f"%{query}%"),
        )
        if document_ids:
            stmt = stmt.where(
                CerberusDocumentChunk.document_id.in_(document_ids)
            )
        stmt = stmt.order_by(
            CerberusDocumentChunk.document_id.asc(),
            CerberusDocumentChunk.chunk_index.asc(),
        ).limit(top_k)
        result = await session.execute(stmt)
        chunks = result.scalars().all()

    logger.info(
        "document_search_completed",
        user_id=user_id,
        top_k=top_k,
        documents=len(document_ids),
        hits=len(chunks),
    )
    return {
        "chunks": [
            {
                "id": c.id,
                "documentId": c.document_id,
                "chunkIndex": c.chunk_index,
                "pageNumber": c.page_number,
                "heading": c.heading,
                "content": c.content[:500],
                "metadata": c.metadata_json,
            }
            for c in chunks
        ]
    }

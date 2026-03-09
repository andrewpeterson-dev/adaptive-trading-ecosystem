"""Document upload and search endpoints."""
from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

logger = structlog.get_logger(__name__)
router = APIRouter()


class UploadRequest(BaseModel):
    filename: str
    mimeType: str


class SearchRequest(BaseModel):
    query: str
    documentIds: Optional[list[str]] = None
    topK: int = 8


@router.post("/upload")
async def upload_document(request: Request, body: UploadRequest):
    """Request a presigned upload URL for a document."""
    from services.ai_core.documents.upload import DocumentUploadService

    user_id = request.state.user_id
    service = DocumentUploadService()
    result = await service.create_upload(user_id, body.filename, body.mimeType)
    return result


@router.post("/{document_id}/finalize")
async def finalize_upload(request: Request, document_id: str):
    """Finalize an upload and trigger ingestion."""
    from services.ai_core.documents.upload import DocumentUploadService

    user_id = request.state.user_id
    service = DocumentUploadService()

    try:
        await service.finalize_upload(document_id, user_id)
        return {"status": "processing", "documentId": document_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{document_id}/status")
async def document_status(request: Request, document_id: str):
    """Check document ingestion status."""
    from db.database import get_session
    from db.copilot_models import CopilotDocumentFile
    from sqlalchemy import select

    user_id = request.state.user_id
    async with get_session() as session:
        result = await session.execute(
            select(CopilotDocumentFile).where(
                CopilotDocumentFile.id == document_id,
                CopilotDocumentFile.user_id == user_id,
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
    from db.copilot_models import CopilotDocumentChunk
    from sqlalchemy import select

    user_id = request.state.user_id

    async with get_session() as session:
        stmt = select(CopilotDocumentChunk).where(
            CopilotDocumentChunk.user_id == user_id,
            CopilotDocumentChunk.content.ilike(f"%{body.query}%"),
        )
        if body.documentIds:
            stmt = stmt.where(
                CopilotDocumentChunk.document_id.in_(body.documentIds)
            )
        stmt = stmt.limit(body.topK)
        result = await session.execute(stmt)
        chunks = result.scalars().all()

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

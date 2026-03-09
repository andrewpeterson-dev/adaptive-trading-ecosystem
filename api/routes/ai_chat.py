"""AI Copilot chat API routes."""
from __future__ import annotations

import json
from typing import Optional

import structlog
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)
router = APIRouter()

_controller = None


def _get_controller():
    global _controller
    if _controller is None:
        from services.ai_core.chat_controller import ChatController

        _controller = ChatController()
    return _controller


class ChatRequest(BaseModel):
    threadId: Optional[str] = None
    mode: str = "chat"
    message: str
    pageContext: Optional[dict] = None
    attachments: Optional[list[str]] = None
    selectedAccountId: Optional[str] = None
    allowSlowExpertMode: bool = False


class ChatResponse(BaseModel):
    threadId: str
    turnId: str
    streamChannel: str


@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    """Initiate a copilot chat turn. Returns thread ID and stream channel."""
    user_id = request.state.user_id
    controller = _get_controller()

    result = await controller.handle_turn(
        user_id=user_id,
        message=body.message,
        thread_id=body.threadId,
        mode=body.mode,
        page_context=body.pageContext,
        attachments=body.attachments,
        selected_account_id=body.selectedAccountId,
        allow_slow_expert=body.allowSlowExpertMode,
    )

    return {
        "threadId": result.thread_id,
        "turnId": result.turn_id,
        "streamChannel": f"/api/ai/stream/{result.thread_id}",
        "message": result.to_message_dict(),
    }


@router.websocket("/stream/{thread_id}")
async def stream(websocket: WebSocket, thread_id: str):
    """WebSocket endpoint for streaming copilot responses."""
    await websocket.accept()

    try:
        while True:
            # Receive chat request from WebSocket
            data = await websocket.receive_json()

            user_id = data.get("userId")
            if not user_id:
                await websocket.send_json(
                    {"type": "error", "data": {"message": "Missing userId"}}
                )
                continue

            message = data.get("message", "")
            mode = data.get("mode", "chat")
            page_context = data.get("pageContext")
            attachments = data.get("attachments")

            controller = _get_controller()

            async for event in controller.stream_turn(
                user_id=user_id,
                message=message,
                thread_id=thread_id,
                mode=mode,
                page_context=page_context,
                attachments=attachments,
            ):
                await websocket.send_json(event)

    except WebSocketDisconnect:
        logger.info("websocket_disconnected", thread_id=thread_id)
    except Exception as e:
        logger.error("websocket_error", thread_id=thread_id, error=str(e))
        try:
            await websocket.send_json(
                {"type": "error", "data": {"message": str(e)}}
            )
        except Exception:
            pass


@router.get("/threads")
async def list_threads(request: Request, limit: int = 20):
    """List conversation threads for the current user."""
    from db.database import get_session
    from db.copilot_models import CopilotConversationThread
    from sqlalchemy import select

    user_id = request.state.user_id
    async with get_session() as session:
        stmt = (
            select(CopilotConversationThread)
            .where(CopilotConversationThread.user_id == user_id)
            .order_by(CopilotConversationThread.updated_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        threads = result.scalars().all()

    return [
        {
            "id": t.id,
            "title": t.title,
            "mode": t.mode.value if t.mode else None,
            "latestPage": t.latest_page,
            "latestSymbol": t.latest_symbol,
            "createdAt": t.created_at.isoformat() if t.created_at else None,
            "updatedAt": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in threads
    ]


@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(request: Request, thread_id: str, limit: int = 50):
    """Get messages for a conversation thread."""
    from db.database import get_session
    from db.copilot_models import CopilotConversationMessage
    from sqlalchemy import select

    user_id = request.state.user_id
    async with get_session() as session:
        stmt = (
            select(CopilotConversationMessage)
            .where(
                CopilotConversationMessage.thread_id == thread_id,
                CopilotConversationMessage.user_id == user_id,
            )
            .order_by(CopilotConversationMessage.created_at.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        messages = result.scalars().all()

    return [
        {
            "id": m.id,
            "role": m.role.value if m.role else None,
            "contentMd": m.content_md,
            "structuredJson": m.structured_json,
            "modelName": m.model_name,
            "citations": m.citations_json or [],
            "toolCalls": m.tool_calls_json or [],
            "createdAt": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]

"""Cerberus chat API routes."""
from __future__ import annotations

from typing import Optional

import jwt
import structlog
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from config.settings import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter()

_controller = None


def _get_controller():
    global _controller
    if _controller is None:
        from services.ai_core.chat_controller import ChatController

        _controller = ChatController()
    return _controller


def _get_websocket_user_id(websocket: WebSocket) -> Optional[int]:
    token = websocket.query_params.get("token") or websocket.cookies.get("auth_token")

    auth_header = websocket.headers.get("authorization", "")
    if not token and auth_header.startswith("Bearer "):
        token = auth_header[7:]

    if not token:
        return None

    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
        user_id = payload.get("user_id")
        return int(user_id) if user_id is not None else None
    except (jwt.InvalidTokenError, TypeError, ValueError):
        return None


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
    """Initiate a Cerberus chat turn. Returns thread ID and stream channel."""
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
    """WebSocket endpoint for streaming Cerberus responses."""
    user_id = _get_websocket_user_id(websocket)
    if user_id is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    try:
        while True:
            # Receive chat request from WebSocket
            data = await websocket.receive_json()

            message = data.get("message", "")
            if not message:
                await websocket.send_json(
                    {"type": "error", "data": {"message": "Missing message"}}
                )
                continue

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
    from db.cerberus_models import CerberusConversationThread
    from sqlalchemy import select

    user_id = request.state.user_id
    async with get_session() as session:
        stmt = (
            select(CerberusConversationThread)
            .where(CerberusConversationThread.user_id == user_id)
            .order_by(CerberusConversationThread.updated_at.desc())
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
    from db.cerberus_models import CerberusConversationMessage
    from sqlalchemy import select

    user_id = request.state.user_id
    async with get_session() as session:
        stmt = (
            select(CerberusConversationMessage)
            .where(
                CerberusConversationMessage.thread_id == thread_id,
                CerberusConversationMessage.user_id == user_id,
            )
            .order_by(CerberusConversationMessage.created_at.asc())
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

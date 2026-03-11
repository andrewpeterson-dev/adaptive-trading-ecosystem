"""Cerberus chat API routes."""
from __future__ import annotations

from typing import Optional

import jwt
import structlog
from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator

from services.security.jwt_utils import JWTConfigurationError, decode_jwt

logger = structlog.get_logger(__name__)
router = APIRouter()
_MAX_THREAD_LIMIT = 100
_MAX_MESSAGE_LIMIT = 200
_ALLOWED_CHAT_MODES = {
    "chat",
    "analysis",
    "trade",
    "backtest",
    "build",
    "portfolio",
    "research",
    "strategy",
}

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
        payload = decode_jwt(token)
        user_id = payload.get("user_id")
        return int(user_id) if user_id is not None else None
    except JWTConfigurationError:
        logger.error("ai_chat_websocket_auth_unavailable")
        return None
    except (jwt.InvalidTokenError, TypeError, ValueError):
        return None


class ChatRequest(BaseModel):
    threadId: Optional[str] = None
    mode: str = "chat"
    message: str = Field(min_length=1, max_length=20_000)
    pageContext: Optional[dict] = None
    attachments: Optional[list[str]] = None
    selectedAccountId: Optional[str] = None
    allowSlowExpertMode: bool = False

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in _ALLOWED_CHAT_MODES:
            raise ValueError(f"Unsupported mode: {value}")
        return normalized

    @field_validator("message", mode="before")
    @classmethod
    def normalize_message(cls, value):
        return str(value).strip()

    @field_validator("attachments")
    @classmethod
    def normalize_attachments(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return None
        normalized = [str(attachment).strip() for attachment in value if str(attachment).strip()]
        return normalized or None


class ChatResponse(BaseModel):
    threadId: str
    turnId: str
    streamChannel: str


@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    """Initiate a Cerberus chat turn. Returns thread ID and stream channel."""
    user_id = request.state.user_id
    controller = _get_controller()
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    try:
        result = await controller.handle_turn(
            user_id=user_id,
            message=message,
            thread_id=body.threadId,
            mode=body.mode,
            page_context=body.pageContext,
            attachments=body.attachments,
            selected_account_id=body.selectedAccountId,
            allow_slow_expert=body.allowSlowExpertMode,
        )
    except LookupError as exc:
        logger.warning("chat_thread_not_found", user_id=user_id, thread_id=body.threadId)
        raise HTTPException(status_code=404, detail=str(exc))

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

            message = str(data.get("message", "")).strip()
            if not message:
                await websocket.send_json(
                    {"type": "error", "data": {"message": "Missing message"}}
                )
                continue

            mode = str(data.get("mode", "chat")).strip().lower()
            if mode not in _ALLOWED_CHAT_MODES:
                await websocket.send_json(
                    {"type": "error", "data": {"message": "Unsupported mode"}}
                )
                continue
            page_context = data.get("pageContext")
            attachments = data.get("attachments")

            controller = _get_controller()

            try:
                async for event in controller.stream_turn(
                    user_id=user_id,
                    message=message,
                    thread_id=thread_id,
                    mode=mode,
                    page_context=page_context,
                    attachments=attachments,
                ):
                    await websocket.send_json(event)
            except LookupError:
                await websocket.send_json(
                    {"type": "error", "data": {"message": "Thread not found"}}
                )

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
async def list_threads(
    request: Request,
    limit: int = Query(default=20, ge=1, le=_MAX_THREAD_LIMIT),
):
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
async def get_thread_messages(
    request: Request,
    thread_id: str,
    limit: int = Query(default=50, ge=1, le=_MAX_MESSAGE_LIMIT),
):
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

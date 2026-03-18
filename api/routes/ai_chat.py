"""Cerberus chat API routes."""
from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator

from config.settings import get_settings
from services.security.rate_limit import RateLimitExceeded, rate_limiter
from services.security.request_auth import (
    AuthenticationError,
    AuthenticationUnavailableError,
    authenticate_token,
)
from services.security.request_origin import websocket_origin_allowed

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


def _client_ip(request_like: Request | WebSocket) -> str:
    settings = get_settings()
    if settings.trust_proxy_headers:
        forwarded = request_like.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()

    client = getattr(request_like, "client", None)
    return getattr(client, "host", None) or "unknown"


def _apply_rate_limit(bucket: str, key: str, *, limit: int, window_seconds: int) -> None:
    try:
        rate_limiter.check(bucket, key, limit=limit, window_seconds=window_seconds)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Try again in {exc.retry_after} seconds.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc


async def _get_websocket_user_id(websocket: WebSocket) -> Optional[int]:
    token = (websocket.query_params.get("token") or "").strip()
    allowed_scopes = {"websocket"} if token else {"access", "websocket"}
    auth_header = websocket.headers.get("authorization", "")
    if not token and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    if not token:
        return None

    try:
        authenticated = await authenticate_token(token, allowed_scopes=allowed_scopes)
        return authenticated.user.id
    except AuthenticationUnavailableError:
        logger.error("ai_chat_websocket_auth_unavailable")
        return None
    except AuthenticationError as exc:
        logger.warning("ai_chat_websocket_auth_failed", reason=exc.reason)
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
    message: Optional[dict] = None


@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    """Initiate a Cerberus chat turn. Returns thread ID and stream channel."""
    user_id = request.state.user_id
    _apply_rate_limit("ai:chat:user", str(user_id), limit=30, window_seconds=60)
    _apply_rate_limit("ai:chat:ip", _client_ip(request), limit=60, window_seconds=60)
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
    except Exception as exc:
        logger.error(
            "chat_turn_failed",
            user_id=user_id,
            mode=body.mode,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Chat processing failed: {str(exc)[:200]}",
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
    if not websocket_origin_allowed(websocket):
        await websocket.close(code=4403)
        return

    user_id = await _get_websocket_user_id(websocket)
    if user_id is None:
        await websocket.close(code=4401)
        return

    # Verify thread ownership before accepting the connection
    from db.database import get_session
    from db.cerberus_models import CerberusConversationThread
    from sqlalchemy import select as sa_select

    async with get_session() as session:
        stmt = sa_select(CerberusConversationThread).where(
            CerberusConversationThread.id == thread_id,
            CerberusConversationThread.user_id == user_id,
        )
        result = await session.execute(stmt)
        thread = result.scalar_one_or_none()
        if not thread:
            # Thread doesn't exist or doesn't belong to this user
            await websocket.close(code=4403)
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

            try:
                _apply_rate_limit("ai:stream:user", str(user_id), limit=30, window_seconds=60)
                _apply_rate_limit("ai:stream:ip", _client_ip(websocket), limit=60, window_seconds=60)
            except HTTPException as exc:
                await websocket.send_json(
                    {"type": "error", "data": {"message": exc.detail}}
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

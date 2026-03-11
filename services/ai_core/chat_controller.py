"""Cerberus chat controller — main orchestration."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import AsyncIterator, Optional

import structlog
from sqlalchemy import select

from config.settings import get_settings
from db.database import get_session
from db.cerberus_models import (
    CerberusConversationThread,
    CerberusConversationMessage,
    CerberusAIToolCall,
    CerberusUIContextEvent,
)
from services.ai_core.context_assembler import ContextAssembler
from services.ai_core.model_router import ModelRouter
from services.ai_core.prompt_builder import PromptBuilder
from services.ai_core.safety_guard import SafetyGuard, SafetyViolation
from services.ai_core.tools.executor import ToolExecutor
from services.ai_core.tools.registry import get_registry
from services.ai_core.providers.base import ProviderMessage, ProviderToolDef, StreamChunk
from services.ai_core.citation_assembler import CitationAssembler
from services.ai_core.ui_command_formatter import format_ui_commands

logger = structlog.get_logger(__name__)


class ChatTurnResult:
    """Result of a complete chat turn."""

    def __init__(self):
        self.thread_id: str = ""
        self.turn_id: str = str(uuid.uuid4())
        self.content: str = ""
        self.tool_calls: list[dict] = []
        self.citations: list[dict] = []
        self.charts: list[dict] = []
        self.ui_commands: list[dict] = []
        self.trade_signals: list[dict] = []
        self.warnings: list[str] = []
        self.model_name: str = ""
        self.provider_name: str = ""

    def to_message_dict(self) -> dict:
        return {
            "turnId": self.turn_id,
            "markdown": self.content,
            "citations": self.citations,
            "structuredTradeSignals": self.trade_signals,
            "charts": self.charts,
            "uiCommands": self.ui_commands,
            "warnings": self.warnings,
        }


class ChatController:
    """Orchestrates a complete Cerberus chat turn."""

    def __init__(self, redis_client=None):
        self._router = ModelRouter()
        self._context_assembler = ContextAssembler(redis_client=redis_client)
        self._prompt_builder = PromptBuilder()
        self._safety = SafetyGuard()
        self._tool_executor = ToolExecutor(redis_client=redis_client)
        self._citation_assembler = CitationAssembler()
        self._redis = redis_client

    async def handle_turn(
        self,
        user_id: int,
        message: str,
        thread_id: Optional[str] = None,
        mode: str = "chat",
        page_context: Optional[dict] = None,
        attachments: Optional[list[str]] = None,
        selected_account_id: Optional[str] = None,
        allow_slow_expert: bool = False,
    ) -> ChatTurnResult:
        """Handle a complete chat turn (non-streaming)."""
        result = ChatTurnResult()

        # 1. Validate input
        message = self._safety.validate_message_input(message)
        self._safety.check_feature_enabled("cerberus")
        self._safety.check_rate_limit(user_id)

        # 2. Get or create thread
        thread_id = await self._ensure_thread(user_id, thread_id, mode)
        result.thread_id = thread_id

        # 3. Store user message
        await self._store_message(thread_id, user_id, "user", message)

        # 4. Store page context
        if page_context:
            await self._store_page_context(user_id, thread_id, page_context)

        # 5. Assemble context
        context = await self._context_assembler.assemble(
            user_id=user_id,
            thread_id=thread_id,
            page_context=page_context,
            mode=mode,
            selected_account_id=selected_account_id,
            attachment_ids=attachments,
        )

        # 6. Route to model
        has_documents = bool(attachments)
        explicit_research = mode == "research"
        registry = get_registry()
        tool_defs = registry.list_for_model()

        routing = self._router.route(
            mode=mode,
            message=message,
            has_tools=len(tool_defs) > 0,
            has_documents=has_documents,
            has_sensitive_data=True,
            tool_count=len(tool_defs),
            explicit_research=explicit_research,
            allow_slow_expert=allow_slow_expert,
        )
        result.model_name = routing.model
        result.provider_name = routing.provider_name
        logger.info(
            "routed_to_model",
            model=routing.model,
            provider=routing.provider_name,
            reason=routing.reason,
        )

        # 7. Build messages
        history = self._extract_history(context)
        messages = self._prompt_builder.build_messages(message, context, history)

        # 8. Convert to provider format
        provider_messages = [
            ProviderMessage(role=m["role"], content=m["content"]) for m in messages
        ]
        provider_tools = [
            ProviderToolDef(
                name=t.name, description=t.description, parameters=t.input_schema,
            )
            for t in tool_defs
        ]

        # 9. Call model
        try:
            response = await routing.provider.complete(
                messages=provider_messages,
                model=routing.model,
                tools=provider_tools if provider_tools else None,
                store=routing.store,
            )
        except Exception as e:
            logger.error(
                "model_call_failed",
                provider=routing.provider_name,
                error=str(e),
            )
            # Fallback to Anthropic
            if routing.provider_name != "anthropic":
                fallback = self._router.route(
                    mode=mode, message=message, openai_failed=True,
                )
                response = await fallback.provider.complete(
                    messages=provider_messages,
                    model=fallback.model,
                    tools=provider_tools if provider_tools else None,
                )
                result.model_name = fallback.model
                result.provider_name = fallback.provider_name
                result.warnings.append("Primary model unavailable, used fallback")
            else:
                raise

        # 10. Process tool calls
        if response.tool_calls:
            for tc in response.tool_calls:
                tool_name = tc["function"]["name"]
                try:
                    tool_input = (
                        json.loads(tc["function"]["arguments"])
                        if isinstance(tc["function"]["arguments"], str)
                        else tc["function"]["arguments"]
                    )
                except (json.JSONDecodeError, TypeError):
                    tool_input = {}

                tool_result = await self._tool_executor.execute(
                    tool_name=tool_name,
                    input_data=tool_input,
                    user_id=user_id,
                    thread_id=thread_id,
                )
                result.tool_calls.append({
                    "tool_name": tool_name,
                    "input": tool_input,
                    "output": tool_result,
                })

                # Log tool call
                await self._store_tool_call(
                    thread_id=thread_id,
                    user_id=user_id,
                    tool_name=tool_name,
                    input_data=tool_input,
                    output_data=tool_result,
                    latency_ms=tool_result.get("latency_ms", 0),
                    provider_request_id=response.provider_request_id,
                )

        # 11. Sanitize output
        content = self._safety.validate_output(response.content)
        result.content = content

        # 12. Extract structured data from response
        result.ui_commands = format_ui_commands(self._extract_ui_commands(content))
        result.citations = self._citation_assembler.extract_citations(
            content, result.tool_calls,
        )

        # 13. Store assistant message
        await self._store_message(
            thread_id,
            user_id,
            "assistant",
            content,
            model_name=result.model_name,
            provider_name=result.provider_name,
            structured_json=result.to_message_dict(),
            citations_json=result.citations,
            tool_calls_json=result.tool_calls,
        )

        return result

    async def stream_turn(
        self,
        user_id: int,
        message: str,
        thread_id: Optional[str] = None,
        mode: str = "chat",
        page_context: Optional[dict] = None,
        attachments: Optional[list[str]] = None,
        selected_account_id: Optional[str] = None,
        allow_slow_expert: bool = False,
    ) -> AsyncIterator[dict]:
        """Handle a streaming chat turn. Yields event dicts for WebSocket."""
        # Validate
        message = self._safety.validate_message_input(message)
        self._safety.check_feature_enabled("cerberus")

        thread_id = await self._ensure_thread(user_id, thread_id, mode)
        turn_id = str(uuid.uuid4())

        yield {
            "type": "assistant.delta",
            "data": {"threadId": thread_id, "turnId": turn_id},
        }

        await self._store_message(thread_id, user_id, "user", message)

        if page_context:
            await self._store_page_context(user_id, thread_id, page_context)

        context = await self._context_assembler.assemble(
            user_id=user_id,
            thread_id=thread_id,
            page_context=page_context,
            mode=mode,
            selected_account_id=selected_account_id,
            attachment_ids=attachments,
        )

        registry = get_registry()
        tool_defs = registry.list_for_model()
        routing = self._router.route(
            mode=mode,
            message=message,
            has_tools=len(tool_defs) > 0,
            has_documents=bool(attachments),
            has_sensitive_data=True,
            tool_count=len(tool_defs),
            explicit_research=mode == "research",
            allow_slow_expert=allow_slow_expert,
        )

        history = self._extract_history(context)
        messages = self._prompt_builder.build_messages(message, context, history)
        provider_messages = [
            ProviderMessage(role=m["role"], content=m["content"]) for m in messages
        ]
        provider_tools = [
            ProviderToolDef(
                name=t.name, description=t.description, parameters=t.input_schema,
            )
            for t in tool_defs
        ]

        # Stream response
        full_content = ""
        try:
            async for chunk in routing.provider.stream(
                messages=provider_messages,
                model=routing.model,
                tools=provider_tools if provider_tools else None,
                store=routing.store,
            ):
                if chunk.delta_text:
                    full_content += chunk.delta_text
                    yield {
                        "type": "assistant.delta",
                        "data": {"text": chunk.delta_text},
                    }
                if chunk.finish_reason:
                    break
        except Exception as e:
            logger.error("stream_error", error=str(e))
            yield {"type": "error", "data": {"message": str(e)}}
            return

        # Sanitize and store
        full_content = self._safety.validate_output(full_content)
        ui_commands = format_ui_commands(self._extract_ui_commands(full_content))
        citations = self._citation_assembler.extract_citations(full_content, [])

        if ui_commands:
            yield {"type": "ui.command", "data": {"commands": ui_commands}}

        await self._store_message(
            thread_id,
            user_id,
            "assistant",
            full_content,
            model_name=routing.model,
            provider_name=routing.provider_name,
            citations_json=citations,
        )

        yield {
            "type": "assistant.message",
            "data": {
                "turnId": turn_id,
                "markdown": full_content,
                "citations": citations,
                "uiCommands": ui_commands,
                "charts": [],
                "structuredTradeSignals": [],
                "warnings": [],
            },
        }
        yield {"type": "done", "data": {}}

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _ensure_thread(
        self, user_id: int, thread_id: Optional[str], mode: str,
    ) -> str:
        if thread_id:
            async with get_session() as session:
                result = await session.execute(
                    select(CerberusConversationThread).where(
                        CerberusConversationThread.id == thread_id,
                        CerberusConversationThread.user_id == user_id,
                    )
                )
                existing_thread = result.scalar_one_or_none()
            if not existing_thread:
                raise LookupError(f"Thread {thread_id} not found")
            return existing_thread.id

        try:
            thread_mode = ConversationMode(mode)
        except ValueError:
            thread_mode = ConversationMode.CHAT

        new_id = str(uuid.uuid4())
        async with get_session() as session:
            thread = CerberusConversationThread(
                id=new_id, user_id=user_id, mode=thread_mode,
            )
            session.add(thread)
        return new_id

    async def _store_message(
        self,
        thread_id: str,
        user_id: int,
        role: str,
        content: str,
        model_name: Optional[str] = None,
        provider_name: Optional[str] = None,
        structured_json: Optional[dict] = None,
        citations_json: Optional[list] = None,
        tool_calls_json: Optional[list] = None,
    ) -> str:
        msg_id = str(uuid.uuid4())
        async with get_session() as session:
            msg = CerberusConversationMessage(
                id=msg_id,
                thread_id=thread_id,
                user_id=user_id,
                role=role,
                content_md=content,
                model_name=model_name,
                provider_name=provider_name,
                structured_json=structured_json,
                citations_json=citations_json,
                tool_calls_json=tool_calls_json,
            )
            session.add(msg)
            result = await session.execute(
                select(CerberusConversationThread).where(
                    CerberusConversationThread.id == thread_id,
                    CerberusConversationThread.user_id == user_id,
                )
            )
            thread = result.scalar_one_or_none()
            if thread:
                thread.updated_at = datetime.utcnow()
        return msg_id

    async def _store_page_context(
        self, user_id: int, thread_id: str, page_context: dict,
    ) -> None:
        async with get_session() as session:
            event = CerberusUIContextEvent(
                user_id=user_id,
                thread_id=thread_id,
                current_page=page_context.get("currentPage"),
                route=page_context.get("route"),
                visible_components=page_context.get("visibleComponents", []),
                focused_component=page_context.get("focusedComponent"),
                selected_symbol=page_context.get("selectedSymbol"),
                selected_account_id=page_context.get("selectedAccountId"),
                selected_bot_id=page_context.get("selectedBotId"),
                component_state=page_context.get("componentState", {}),
            )
            session.add(event)

    async def _store_tool_call(
        self,
        thread_id: str,
        user_id: int,
        tool_name: str,
        input_data: dict,
        output_data: dict,
        latency_ms: int,
        provider_request_id: str = "",
    ) -> None:
        async with get_session() as session:
            tc = CerberusAIToolCall(
                thread_id=thread_id,
                user_id=user_id,
                tool_name=tool_name,
                tool_version="1.0",
                input_json=input_data,
                output_json=output_data,
                status="completed" if output_data.get("success") else "failed",
                latency_ms=latency_ms,
                error_text=output_data.get("error"),
                provider_request_id=provider_request_id,
            )
            session.add(tc)

    def _extract_history(self, context) -> list[dict]:
        conv = context.conversation_context
        return conv.get("recent_messages", [])

    def _extract_ui_commands(self, content: str) -> list[dict]:
        """Extract UI commands from markdown content (JSON code blocks tagged as ui_command)."""
        commands: list[dict] = []
        pattern = r"```ui_command\s*\n(.*?)\n```"
        for match in re.finditer(pattern, content, re.DOTALL):
            try:
                cmd = json.loads(match.group(1))
                if isinstance(cmd, list):
                    commands.extend(cmd)
                elif isinstance(cmd, dict):
                    commands.append(cmd)
            except json.JSONDecodeError:
                pass
        return commands

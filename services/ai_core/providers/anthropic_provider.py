"""Anthropic provider using native Claude API (not OpenAI compatibility layer)."""
from __future__ import annotations

from typing import AsyncIterator

import structlog

from config.settings import get_settings
from .base import (
    BaseProvider, ProviderMessage, ProviderToolDef,
    ProviderResponse, StreamChunk,
)

logger = structlog.get_logger(__name__)


class AnthropicProvider(BaseProvider):
    """Anthropic provider using native Claude API with streaming and tool calling."""

    provider_name = "anthropic"

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.anthropic_api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    def _format_messages(self, messages: list[ProviderMessage]) -> tuple[str | None, list[dict]]:
        """Split system message from conversation messages."""
        system_prompt = None
        formatted = []
        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
                continue
            d: dict = {"role": msg.role}
            if msg.role == "tool" and msg.tool_call_id:
                d["content"] = [{"type": "tool_result", "tool_use_id": msg.tool_call_id, "content": msg.content}]
            else:
                d["content"] = msg.content
            formatted.append(d)
        return system_prompt, formatted

    def _format_tools(self, tools: list[ProviderToolDef] | None) -> list[dict] | None:
        if not tools:
            return None
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

    async def complete(
        self,
        messages: list[ProviderMessage],
        model: str,
        tools: list[ProviderToolDef] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: dict | None = None,
        store: bool = True,
        **kwargs,
    ) -> ProviderResponse:
        client = self._get_client()
        system_prompt, formatted_msgs = self._format_messages(messages)

        params: dict = {
            "model": model,
            "messages": formatted_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_prompt:
            params["system"] = system_prompt
        if tools:
            params["tools"] = self._format_tools(tools)

        logger.info("anthropic_complete", model=model)
        response = await client.messages.create(**params)

        content = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "function": {"name": block.name, "arguments": str(block.input)},
                })

        return ProviderResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=response.stop_reason or "end_turn",
            usage={"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens},
            model=model,
            provider_request_id=response.id,
        )

    async def stream(
        self,
        messages: list[ProviderMessage],
        model: str,
        tools: list[ProviderToolDef] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: dict | None = None,
        store: bool = True,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        client = self._get_client()
        system_prompt, formatted_msgs = self._format_messages(messages)

        params: dict = {
            "model": model,
            "messages": formatted_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_prompt:
            params["system"] = system_prompt
        if tools:
            params["tools"] = self._format_tools(tools)

        logger.info("anthropic_stream", model=model)
        async with client.messages.stream(**params) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        yield StreamChunk(delta_text=event.delta.text)
                elif event.type == "message_stop":
                    msg = stream.current_message_snapshot
                    yield StreamChunk(
                        finish_reason="end_turn",
                        usage={"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens} if msg.usage else None,
                        provider_request_id=msg.id,
                    )

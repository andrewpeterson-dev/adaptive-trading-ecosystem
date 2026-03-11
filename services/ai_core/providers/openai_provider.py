"""OpenAI provider using the Responses API."""
from __future__ import annotations

import asyncio
from typing import AsyncIterator

import httpx
import structlog

from config.settings import get_settings
from .base import (
    BaseProvider, ProviderMessage, ProviderToolDef,
    ProviderResponse, StreamChunk,
)

logger = structlog.get_logger(__name__)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 529}


class OpenAIProvider(BaseProvider):
    """OpenAI provider using Responses API with streaming and tool calling."""

    provider_name = "openai"

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.openai_api_key
        self._client: "openai.AsyncOpenAI | None" = None

    def _get_client(self):
        if self._client is None:
            import openai
            self._client = openai.AsyncOpenAI(api_key=self._api_key)
        return self._client

    def _format_messages(self, messages: list[ProviderMessage]) -> list[dict]:
        formatted = []
        for msg in messages:
            d = {"role": msg.role, "content": msg.content}
            if msg.name:
                d["name"] = msg.name
            if msg.tool_call_id:
                d["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                d["tool_calls"] = msg.tool_calls
            formatted.append(d)
        return formatted

    def _format_tools(self, tools: list[ProviderToolDef] | None) -> list[dict] | None:
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
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
        params: dict = {
            "model": model,
            "input": self._format_messages(messages),
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "store": store,
        }
        if tools:
            params["tools"] = self._format_tools(tools)
        if response_format:
            params["text"] = {"format": response_format}

        logger.info("openai_complete", model=model, store=store)
        settings = get_settings()
        max_retries = settings.llm_max_retries
        last_exc = None
        for attempt in range(max_retries + 1):
            try:
                response = await client.responses.create(**params)
                break
            except Exception as e:
                last_exc = e
                status = getattr(e, "status_code", 0) or 0
                if status not in _RETRYABLE_STATUS_CODES and "rate" not in str(e).lower():
                    raise
                if attempt < max_retries:
                    delay = 2 ** attempt
                    logger.warning("openai_retry", attempt=attempt + 1, delay=delay, error=str(e))
                    await asyncio.sleep(delay)
                else:
                    raise
        else:
            raise last_exc  # type: ignore[misc]

        content = ""
        tool_calls = []
        for item in response.output:
            if item.type == "message":
                for block in item.content:
                    if hasattr(block, "text"):
                        content += block.text
            elif item.type == "function_call":
                tool_calls.append({
                    "id": item.call_id,
                    "function": {"name": item.name, "arguments": item.arguments},
                })

        return ProviderResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason="stop",
            usage={"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens} if response.usage else {},
            model=model,
            provider_request_id=response.id or "",
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
        params: dict = {
            "model": model,
            "input": self._format_messages(messages),
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "store": store,
            "stream": True,
        }
        if tools:
            params["tools"] = self._format_tools(tools)
        if response_format:
            params["text"] = {"format": response_format}

        logger.info("openai_stream", model=model, store=store)
        async with client.responses.stream(**params) as stream:
            async for event in stream:
                if hasattr(event, "delta") and event.delta:
                    yield StreamChunk(delta_text=event.delta)
                elif hasattr(event, "type") and event.type == "response.completed":
                    resp = event.response
                    yield StreamChunk(
                        finish_reason="stop",
                        usage={"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens} if resp.usage else None,
                        provider_request_id=resp.id or "",
                    )

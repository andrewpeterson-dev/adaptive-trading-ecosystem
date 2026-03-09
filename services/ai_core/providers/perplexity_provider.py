"""Perplexity provider for real-time search and deep research."""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx
import structlog

from config.settings import get_settings
from .base import (
    BaseProvider, ProviderMessage, ProviderToolDef,
    ProviderResponse, StreamChunk,
)

logger = structlog.get_logger(__name__)

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


class PerplexityProvider(BaseProvider):
    """Perplexity provider for search and deep research. Not for portfolio/trade truth."""

    provider_name = "perplexity"

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.perplexity_api_key

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
        formatted = [{"role": m.role, "content": m.content} for m in messages]
        payload = {
            "model": model,
            "messages": formatted,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        logger.info("perplexity_complete", model=model)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                PERPLEXITY_API_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]

        return ProviderResponse(
            content=choice["message"]["content"],
            tool_calls=[],
            finish_reason=choice.get("finish_reason", "stop"),
            usage=data.get("usage", {}),
            model=model,
            provider_request_id=data.get("id", ""),
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
        formatted = [{"role": m.role, "content": m.content} for m in messages]
        payload = {
            "model": model,
            "messages": formatted,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        logger.info("perplexity_stream", model=model)
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST",
                PERPLEXITY_API_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:]
                    if raw == "[DONE]":
                        yield StreamChunk(finish_reason="stop")
                        return
                    data = json.loads(raw)
                    choice = data["choices"][0]
                    delta = choice.get("delta", {})
                    yield StreamChunk(
                        delta_text=delta.get("content", ""),
                        finish_reason=choice.get("finish_reason"),
                        provider_request_id=data.get("id", ""),
                    )

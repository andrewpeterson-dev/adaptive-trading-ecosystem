"""Base provider interface for AI model adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ProviderMessage:
    """Normalized message format across providers."""
    role: str  # system, user, assistant, tool
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict] | None = None


@dataclass
class ProviderToolDef:
    """Normalized tool definition for providers."""
    name: str
    description: str
    parameters: dict  # JSON Schema


@dataclass
class StreamChunk:
    """A single chunk from a streaming response."""
    delta_text: str = ""
    delta_tool_calls: list[dict] | None = None
    finish_reason: str | None = None
    usage: dict | None = None
    provider_request_id: str | None = None


@dataclass
class ProviderResponse:
    """Complete (non-streaming) response from a provider."""
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict = field(default_factory=dict)
    model: str = ""
    provider_request_id: str = ""


class BaseProvider(ABC):
    """Abstract base for AI model providers."""

    provider_name: str = "base"

    @abstractmethod
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
        """Non-streaming completion."""
        ...

    @abstractmethod
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
        """Streaming completion. Yields StreamChunk objects."""
        ...

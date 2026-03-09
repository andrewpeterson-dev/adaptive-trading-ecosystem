"""Base tool definitions and contracts for the Cerberus tool system."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, List, Optional

from pydantic import BaseModel


class ToolCategory(str, Enum):
    PORTFOLIO = "portfolio"
    TRADING = "trading"
    MARKET = "market"
    RISK = "risk"
    RESEARCH = "research"
    ANALYTICS = "analytics"
    UI = "ui"


class ToolSideEffect(str, Enum):
    READ = "read"
    WRITE = "write"
    DANGEROUS = "dangerous"


@dataclass
class ToolDefinition:
    """Complete tool definition with metadata, schema, and handler."""
    name: str
    version: str
    description: str
    category: ToolCategory
    side_effect: ToolSideEffect
    requires_confirmation: bool = False
    timeout_ms: int = 5000
    cache_ttl_s: Optional[int] = None
    input_schema: dict = field(default_factory=dict)  # JSON Schema
    output_schema: dict = field(default_factory=dict)  # JSON Schema
    permissions: List[str] = field(default_factory=list)
    handler: Optional[Callable[..., Coroutine[Any, Any, dict]]] = None

    def to_provider_format(self) -> dict:
        """Convert to the format expected by LLM providers (function calling)."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema,
        }


class ToolInput(BaseModel):
    """Base class for tool inputs — subclassed per tool."""
    class Config:
        extra = "forbid"


class ToolOutput(BaseModel):
    """Base class for tool outputs."""
    success: bool = True
    data: Any = None
    error: Optional[str] = None

    class Config:
        extra = "allow"

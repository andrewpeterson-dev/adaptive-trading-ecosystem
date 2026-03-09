"""Singleton tool registry for AI Copilot tools."""

from __future__ import annotations

import structlog

from .base import ToolDefinition, ToolCategory, ToolSideEffect

logger = structlog.get_logger(__name__)


class ToolRegistry:
    """Registry of all available copilot tools. Singleton pattern."""

    _instance: "ToolRegistry | None" = None
    _tools: dict[str, ToolDefinition]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition."""
        if tool.name in self._tools:
            logger.warning("tool_already_registered", name=tool.name)
        self._tools[tool.name] = tool
        logger.info("tool_registered", name=tool.name, category=tool.category.value)

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_all(self) -> list[ToolDefinition]:
        """List all registered tools."""
        return list(self._tools.values())

    def list_by_category(self, category: ToolCategory) -> list[ToolDefinition]:
        """List tools filtered by category."""
        return [t for t in self._tools.values() if t.category == category]

    def list_for_model(self, include_dangerous: bool = False) -> list[ToolDefinition]:
        """List tools suitable for model consumption (excludes dangerous by default)."""
        tools = self._tools.values()
        if not include_dangerous:
            tools = [t for t in tools if t.side_effect != ToolSideEffect.DANGEROUS]
        return list(tools)

    def list_read_only(self) -> list[ToolDefinition]:
        """List read-only tools (safe for caching)."""
        return [t for t in self._tools.values() if t.side_effect == ToolSideEffect.READ]

    def to_provider_format(self, include_dangerous: bool = False) -> list[dict]:
        """Convert all tools to the format expected by LLM providers."""
        return [t.to_provider_format() for t in self.list_for_model(include_dangerous)]

    def clear(self) -> None:
        """Clear all registrations (for testing)."""
        self._tools.clear()

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None


def get_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    return ToolRegistry()

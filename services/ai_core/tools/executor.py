"""Tool executor with validation, caching, logging, and timeout handling."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from typing import Any

import structlog

from config.settings import get_settings
from .base import ToolDefinition, ToolSideEffect
from .registry import get_registry

logger = structlog.get_logger(__name__)


class ToolExecutionError(Exception):
    """Raised when a tool execution fails."""
    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' failed: {message}")


class ToolExecutor:
    """Executes tools with validation, caching, logging, and timeout handling."""

    def __init__(self, redis_client=None):
        self._registry = get_registry()
        self._redis = redis_client

    async def execute(
        self,
        tool_name: str,
        input_data: dict,
        user_id: int,
        thread_id: str | None = None,
        permissions: list[str] | None = None,
    ) -> dict:
        """Execute a tool by name with full validation and logging pipeline.

        Returns dict with: success, data, error, latency_ms, tool_call_id
        """
        tool_call_id = str(uuid.uuid4())
        start_time = time.monotonic()

        tool = self._registry.get(tool_name)
        if not tool:
            return self._error_result(tool_call_id, tool_name, f"Unknown tool: {tool_name}", start_time)

        # Permission check
        if tool.permissions and permissions is not None:
            missing = set(tool.permissions) - set(permissions)
            if missing:
                return self._error_result(
                    tool_call_id, tool_name,
                    f"Missing permissions: {missing}", start_time
                )

        # Check cache for read-only tools
        if tool.side_effect == ToolSideEffect.READ and tool.cache_ttl_s and self._redis:
            cached = await self._check_cache(tool_name, input_data, user_id)
            if cached is not None:
                logger.info("tool_cache_hit", tool=tool_name, user_id=user_id)
                return {
                    "success": True,
                    "data": cached,
                    "error": None,
                    "latency_ms": int((time.monotonic() - start_time) * 1000),
                    "tool_call_id": tool_call_id,
                    "cached": True,
                }

        # Execute with timeout
        if not tool.handler:
            return self._error_result(tool_call_id, tool_name, "No handler registered", start_time)

        try:
            timeout_s = tool.timeout_ms / 1000.0
            result = await asyncio.wait_for(
                tool.handler(**input_data, user_id=user_id),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError:
            return self._error_result(
                tool_call_id, tool_name,
                f"Timeout after {tool.timeout_ms}ms", start_time
            )
        except Exception as e:
            logger.error("tool_execution_error", tool=tool_name, error=str(e))
            return self._error_result(tool_call_id, tool_name, str(e), start_time)

        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Cache result if applicable
        if tool.side_effect == ToolSideEffect.READ and tool.cache_ttl_s and self._redis:
            await self._set_cache(tool_name, input_data, user_id, result, tool.cache_ttl_s)

        logger.info(
            "tool_executed",
            tool=tool_name,
            user_id=user_id,
            latency_ms=latency_ms,
            success=True,
        )

        return {
            "success": True,
            "data": result,
            "error": None,
            "latency_ms": latency_ms,
            "tool_call_id": tool_call_id,
            "cached": False,
        }

    def _error_result(self, tool_call_id: str, tool_name: str, error: str, start_time: float) -> dict:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        logger.warning("tool_execution_failed", tool=tool_name, error=error, latency_ms=latency_ms)
        return {
            "success": False,
            "data": None,
            "error": error,
            "latency_ms": latency_ms,
            "tool_call_id": tool_call_id,
            "cached": False,
        }

    def _cache_key(self, tool_name: str, input_data: dict, user_id: int) -> str:
        input_hash = hashlib.sha256(json.dumps(input_data, sort_keys=True).encode()).hexdigest()[:16]
        return f"toolcache:{user_id}:{tool_name}:{input_hash}"

    async def _check_cache(self, tool_name: str, input_data: dict, user_id: int) -> Any | None:
        try:
            key = self._cache_key(tool_name, input_data, user_id)
            raw = await self._redis.get(key)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning("tool_cache_error", tool=tool_name, error=str(e))
        return None

    async def _set_cache(self, tool_name: str, input_data: dict, user_id: int, result: Any, ttl_s: int) -> None:
        try:
            key = self._cache_key(tool_name, input_data, user_id)
            await self._redis.setex(key, ttl_s, json.dumps(result))
        except Exception as e:
            logger.warning("tool_cache_set_error", tool=tool_name, error=str(e))

"""
LLM Router — Ollama-first routing with Claude fallback.
Transparently routes LLM requests to the best available backend.
"""

import time
from typing import Awaitable, Callable, Optional

import structlog

from config.settings import Settings, get_settings
from intelligence.ollama_client import OllamaClient

logger = structlog.get_logger(__name__)


class LLMRouter:
    """Routes LLM requests: try Ollama first, fall back to Claude."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        ollama_client: Optional[OllamaClient] = None,
        claude_fallback_fn: Optional[Callable[..., Awaitable[str]]] = None,
    ):
        self.settings = settings or get_settings()
        self.ollama = ollama_client or OllamaClient()
        self.claude_fallback_fn = claude_fallback_fn
        self._stats = {
            "total_requests": 0,
            "ollama_served": 0,
            "claude_served": 0,
            "ollama_failures": 0,
        }

    async def route(
        self,
        prompt: str,
        system: Optional[str] = None,
    ) -> dict:
        """
        Route a prompt to the best available LLM backend.
        Returns { response, backend, latency_ms }.
        """
        self._stats["total_requests"] += 1
        start = time.monotonic()

        # Try Ollama first if enabled
        if self.settings.ollama_enabled:
            try:
                available = await self.ollama.is_available()
                if available:
                    response = await self.ollama.generate(
                        prompt=prompt,
                        system=system,
                    )
                    latency_ms = round((time.monotonic() - start) * 1000, 1)
                    self._stats["ollama_served"] += 1
                    logger.info("llm_routed", backend="ollama", latency_ms=latency_ms)
                    return {
                        "response": response,
                        "backend": "ollama",
                        "latency_ms": latency_ms,
                    }
            except Exception as e:
                self._stats["ollama_failures"] += 1
                logger.warning("ollama_failed_falling_back", error=str(e))

        # Fall back to Claude
        if self.claude_fallback_fn is None:
            raise RuntimeError(
                "No Claude fallback configured and Ollama unavailable"
            )

        try:
            response = await self.claude_fallback_fn(prompt, system)
        except Exception:
            raise

        latency_ms = round((time.monotonic() - start) * 1000, 1)
        self._stats["claude_served"] += 1
        logger.info("llm_routed", backend="claude", latency_ms=latency_ms)
        return {
            "response": response,
            "backend": "claude",
            "latency_ms": latency_ms,
        }

    async def get_status(self) -> dict:
        """Return router status and backend availability."""
        ollama_available = False
        if self.settings.ollama_enabled:
            ollama_available = await self.ollama.is_available()

        primary = "ollama" if (self.settings.ollama_enabled and ollama_available) else "claude"
        fallback = "claude" if primary == "ollama" else "none"

        return {
            "primary": primary,
            "fallback": fallback,
            "ollama_available": ollama_available,
            "stats": {
                **self._stats,
                "ollama_client": self.ollama.get_stats(),
            },
        }

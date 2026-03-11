"""
Ollama HTTP client for local LLM inference.
Wraps the Ollama REST API for generate and chat endpoints.
"""

import time
from typing import Optional

import httpx
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


class OllamaClient:
    """Async client for the Ollama local LLM server."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.default_model = default_model or settings.ollama_model
        self.timeout_seconds = timeout_seconds or settings.ollama_timeout_seconds
        self._client: httpx.AsyncClient | None = None
        self._stats = {
            "total_calls": 0,
            "successes": 0,
            "failures": 0,
            "total_latency_ms": 0.0,
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Return a reusable async HTTP client (connection pooling)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=float(self.timeout_seconds),
            )
        return self._client

    async def close(self):
        """Close the HTTP client. Call on shutdown."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @property
    def avg_latency_ms(self) -> float:
        if self._stats["successes"] == 0:
            return 0.0
        return round(self._stats["total_latency_ms"] / self._stats["successes"], 1)

    async def is_available(self) -> bool:
        """Check if the Ollama server is reachable."""
        try:
            client = await self._get_client()
            resp = await client.get("/api/tags")
            return resp.status_code == 200
        except Exception:
            return False

    async def health_check(self) -> dict:
        """Return detailed health info for the Ollama server."""
        start = time.monotonic()
        try:
            client = await self._get_client()
            resp = await client.get("/api/tags")
            latency_ms = round((time.monotonic() - start) * 1000, 1)

            if resp.status_code != 200:
                return {
                    "available": False,
                    "latency_ms": latency_ms,
                    "model_loaded": False,
                    "error": f"HTTP {resp.status_code}",
                }

            data = resp.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            model_loaded = any(
                self.default_model in m for m in models
            )

            return {
                "available": True,
                "latency_ms": latency_ms,
                "model_loaded": model_loaded,
                "models": models,
                "error": None,
            }
        except Exception as e:
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            return {
                "available": False,
                "latency_ms": latency_ms,
                "model_loaded": False,
                "error": str(e),
            }

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """Generate a completion using Ollama's /api/generate endpoint."""
        model = model or self.default_model
        self._stats["total_calls"] += 1
        start = time.monotonic()

        payload: dict = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        try:
            client = await self._get_client()
            resp = await client.post("/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()

            latency_ms = round((time.monotonic() - start) * 1000, 1)
            self._stats["successes"] += 1
            self._stats["total_latency_ms"] += latency_ms

            logger.info(
                "ollama_generate_ok",
                model=model,
                latency_ms=latency_ms,
                response_len=len(data.get("response", "")),
            )
            return data.get("response", "")

        except Exception as e:
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            self._stats["failures"] += 1
            logger.warning(
                "ollama_generate_failed",
                model=model,
                latency_ms=latency_ms,
                error=str(e),
            )
            raise

    async def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
    ) -> str:
        """Send a chat completion request using Ollama's /api/chat endpoint."""
        model = model or self.default_model
        self._stats["total_calls"] += 1
        start = time.monotonic()

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        try:
            client = await self._get_client()
            resp = await client.post("/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

            latency_ms = round((time.monotonic() - start) * 1000, 1)
            self._stats["successes"] += 1
            self._stats["total_latency_ms"] += latency_ms

            content = data.get("message", {}).get("content", "")
            logger.info(
                "ollama_chat_ok",
                model=model,
                latency_ms=latency_ms,
                response_len=len(content),
            )
            return content

        except Exception as e:
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            self._stats["failures"] += 1
            logger.warning(
                "ollama_chat_failed",
                model=model,
                latency_ms=latency_ms,
                error=str(e),
            )
            raise

    def get_stats(self) -> dict:
        """Return client statistics."""
        return {
            "total_calls": self._stats["total_calls"],
            "successes": self._stats["successes"],
            "failures": self._stats["failures"],
            "avg_latency_ms": self.avg_latency_ms,
        }

"""Tests for the LLM router (Ollama-first with Claude fallback)."""

import os

os.environ.setdefault("ALPACA_API_KEY", "test")
os.environ.setdefault("ALPACA_SECRET_KEY", "test")

from unittest.mock import AsyncMock, MagicMock

import pytest

from intelligence.llm_router import LLMRouter


@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.ollama_enabled = True
    s.ollama_base_url = "http://localhost:11434"
    s.ollama_model = "llama3.1:8b"
    s.ollama_timeout_seconds = 30
    return s


@pytest.fixture
def mock_ollama():
    client = MagicMock()
    client.is_available = AsyncMock(return_value=True)
    client.generate = AsyncMock(return_value="Ollama says bullish")
    client.get_stats = MagicMock(return_value={"total_calls": 0, "successes": 0, "failures": 0, "avg_latency_ms": 0})
    return client


@pytest.fixture
def mock_claude():
    return AsyncMock(return_value="Claude says bearish")


class TestRouteToOllama:
    async def test_routes_to_ollama_when_available(self, mock_settings, mock_ollama, mock_claude):
        router = LLMRouter(
            settings=mock_settings,
            ollama_client=mock_ollama,
            claude_fallback_fn=mock_claude,
        )
        result = await router.route("Analyze AAPL")
        assert result["backend"] == "ollama"
        assert result["response"] == "Ollama says bullish"
        assert result["latency_ms"] >= 0
        mock_ollama.is_available.assert_awaited_once()
        mock_ollama.generate.assert_awaited_once()
        mock_claude.assert_not_awaited()


class TestFallbackToClaude:
    async def test_falls_back_when_ollama_fails(self, mock_settings, mock_ollama, mock_claude):
        mock_ollama.generate = AsyncMock(side_effect=RuntimeError("Ollama crashed"))
        router = LLMRouter(
            settings=mock_settings,
            ollama_client=mock_ollama,
            claude_fallback_fn=mock_claude,
        )
        result = await router.route("Analyze AAPL")
        assert result["backend"] == "claude"
        assert result["response"] == "Claude says bearish"

    async def test_falls_back_when_ollama_unavailable(self, mock_settings, mock_ollama, mock_claude):
        mock_ollama.is_available = AsyncMock(return_value=False)
        router = LLMRouter(
            settings=mock_settings,
            ollama_client=mock_ollama,
            claude_fallback_fn=mock_claude,
        )
        result = await router.route("Analyze AAPL")
        assert result["backend"] == "claude"
        assert result["response"] == "Claude says bearish"


class TestRouteDirectToClaude:
    async def test_skips_ollama_when_disabled(self, mock_settings, mock_ollama, mock_claude):
        mock_settings.ollama_enabled = False
        router = LLMRouter(
            settings=mock_settings,
            ollama_client=mock_ollama,
            claude_fallback_fn=mock_claude,
        )
        result = await router.route("Analyze AAPL")
        assert result["backend"] == "claude"
        mock_ollama.is_available.assert_not_awaited()


class TestBothFail:
    async def test_raises_when_both_fail(self, mock_settings, mock_ollama):
        mock_ollama.generate = AsyncMock(side_effect=RuntimeError("Ollama down"))
        mock_claude = AsyncMock(side_effect=RuntimeError("Claude down"))
        router = LLMRouter(
            settings=mock_settings,
            ollama_client=mock_ollama,
            claude_fallback_fn=mock_claude,
        )
        with pytest.raises(RuntimeError, match="Claude down"):
            await router.route("Analyze AAPL")

    async def test_raises_when_no_claude_and_ollama_off(self, mock_settings, mock_ollama):
        mock_settings.ollama_enabled = False
        router = LLMRouter(
            settings=mock_settings,
            ollama_client=mock_ollama,
            claude_fallback_fn=None,
        )
        with pytest.raises(RuntimeError, match="No Claude fallback"):
            await router.route("Analyze AAPL")


class TestRouterStats:
    async def test_stats_track_ollama(self, mock_settings, mock_ollama, mock_claude):
        router = LLMRouter(
            settings=mock_settings,
            ollama_client=mock_ollama,
            claude_fallback_fn=mock_claude,
        )
        await router.route("prompt1")
        await router.route("prompt2")
        assert router._stats["total_requests"] == 2
        assert router._stats["ollama_served"] == 2
        assert router._stats["claude_served"] == 0

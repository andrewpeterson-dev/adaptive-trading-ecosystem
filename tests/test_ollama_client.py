"""Tests for the Ollama HTTP client."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

os.environ.setdefault("ALPACA_API_KEY", "test")
os.environ.setdefault("ALPACA_SECRET_KEY", "test")


def _make_settings():
    return MagicMock(
        ollama_base_url="http://localhost:11434",
        ollama_model="llama3.1:8b",
        ollama_timeout_seconds=30,
    )


def _build_client():
    with patch("intelligence.ollama_client.get_settings", return_value=_make_settings()):
        from intelligence.ollama_client import OllamaClient

        return OllamaClient()


def _mock_httpx_client(mock_client_cls, *, get_response=None, get_side_effect=None, post_response=None, post_side_effect=None):
    mock_client = MagicMock()
    mock_client.is_closed = False
    mock_client.aclose = AsyncMock()
    mock_client.get = AsyncMock(return_value=get_response, side_effect=get_side_effect)
    mock_client.post = AsyncMock(return_value=post_response, side_effect=post_side_effect)
    mock_client_cls.return_value = mock_client
    return mock_client


class TestIsAvailable:
    async def test_available_when_server_up(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        client = _build_client()

        with patch("intelligence.ollama_client.httpx.AsyncClient") as mock_client_cls:
            _mock_httpx_client(mock_client_cls, get_response=mock_response)

            result = await client.is_available()

        assert result is True

    async def test_unavailable_when_server_down(self):
        client = _build_client()

        with patch("intelligence.ollama_client.httpx.AsyncClient") as mock_client_cls:
            _mock_httpx_client(
                mock_client_cls,
                get_side_effect=httpx.ConnectError("Connection refused"),
            )

            result = await client.is_available()

        assert result is False


class TestGenerate:
    async def test_generate_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "AAPL looks bullish"}
        mock_response.raise_for_status = MagicMock()
        client = _build_client()

        with patch("intelligence.ollama_client.httpx.AsyncClient") as mock_client_cls:
            _mock_httpx_client(mock_client_cls, post_response=mock_response)

            result = await client.generate("Analyze AAPL")

        assert result == "AAPL looks bullish"
        assert client._stats["successes"] == 1

    async def test_generate_timeout(self):
        client = _build_client()

        with patch("intelligence.ollama_client.httpx.AsyncClient") as mock_client_cls:
            _mock_httpx_client(
                mock_client_cls,
                post_side_effect=httpx.ReadTimeout("Timeout"),
            )

            with patch("intelligence.ollama_client.time.monotonic", side_effect=[0.0, 0.1]):
                try:
                    await client.generate("Analyze AAPL")
                except httpx.ReadTimeout:
                    pass
                else:  # pragma: no cover - defensive
                    raise AssertionError("Expected httpx.ReadTimeout")

        assert client._stats["failures"] == 1


class TestStats:
    async def test_stats_track_calls(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "ok"}
        mock_response.raise_for_status = MagicMock()
        client = _build_client()

        with patch("intelligence.ollama_client.httpx.AsyncClient") as mock_client_cls:
            _mock_httpx_client(mock_client_cls, post_response=mock_response)

            await client.generate("prompt1")
            await client.generate("prompt2")

        stats = client.get_stats()
        assert stats["total_calls"] == 2
        assert stats["successes"] == 2
        assert stats["failures"] == 0
        assert stats["avg_latency_ms"] >= 0

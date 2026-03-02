"""Tests for the Ollama HTTP client."""

import os

os.environ.setdefault("ALPACA_API_KEY", "test")
os.environ.setdefault("ALPACA_SECRET_KEY", "test")

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


class TestIsAvailable:
    async def test_available_when_server_up(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("intelligence.ollama_client.get_settings") as mock_gs:
            mock_gs.return_value = MagicMock(
                ollama_base_url="http://localhost:11434",
                ollama_model="llama3.1:8b",
                ollama_timeout_seconds=30,
            )
            from intelligence.ollama_client import OllamaClient

            client = OllamaClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.is_available()
            assert result is True

    async def test_unavailable_when_server_down(self):
        with patch("intelligence.ollama_client.get_settings") as mock_gs:
            mock_gs.return_value = MagicMock(
                ollama_base_url="http://localhost:11434",
                ollama_model="llama3.1:8b",
                ollama_timeout_seconds=30,
            )
            from intelligence.ollama_client import OllamaClient

            client = OllamaClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.is_available()
            assert result is False


class TestGenerate:
    async def test_generate_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "AAPL looks bullish"}
        mock_response.raise_for_status = MagicMock()

        with patch("intelligence.ollama_client.get_settings") as mock_gs:
            mock_gs.return_value = MagicMock(
                ollama_base_url="http://localhost:11434",
                ollama_model="llama3.1:8b",
                ollama_timeout_seconds=30,
            )
            from intelligence.ollama_client import OllamaClient

            client = OllamaClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_ctx = AsyncMock()
            mock_ctx.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.generate("Analyze AAPL")
            assert result == "AAPL looks bullish"
            assert client._stats["successes"] == 1

    async def test_generate_timeout(self):
        with patch("intelligence.ollama_client.get_settings") as mock_gs:
            mock_gs.return_value = MagicMock(
                ollama_base_url="http://localhost:11434",
                ollama_model="llama3.1:8b",
                ollama_timeout_seconds=30,
            )
            from intelligence.ollama_client import OllamaClient

            client = OllamaClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_ctx = AsyncMock()
            mock_ctx.post = AsyncMock(side_effect=httpx.ReadTimeout("Timeout"))
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(httpx.ReadTimeout):
                await client.generate("Analyze AAPL")
            assert client._stats["failures"] == 1


class TestStats:
    async def test_stats_track_calls(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "ok"}
        mock_response.raise_for_status = MagicMock()

        with patch("intelligence.ollama_client.get_settings") as mock_gs:
            mock_gs.return_value = MagicMock(
                ollama_base_url="http://localhost:11434",
                ollama_model="llama3.1:8b",
                ollama_timeout_seconds=30,
            )
            from intelligence.ollama_client import OllamaClient

            client = OllamaClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_ctx = AsyncMock()
            mock_ctx.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await client.generate("prompt1")
            await client.generate("prompt2")

        stats = client.get_stats()
        assert stats["total_calls"] == 2
        assert stats["successes"] == 2
        assert stats["failures"] == 0
        assert stats["avg_latency_ms"] >= 0

"""Tests for the LLM watchdog decorator."""

import asyncio
import os

os.environ.setdefault("ALPACA_API_KEY", "test")
os.environ.setdefault("ALPACA_SECRET_KEY", "test")

from unittest.mock import MagicMock, patch

import pytest

from monitor.llm_watchdog import LLMWatchdog


@pytest.fixture
def watchdog():
    with patch("monitor.llm_watchdog.get_settings") as mock_gs:
        mock_gs.return_value = MagicMock(llm_timeout_seconds=2)
        return LLMWatchdog(timeout_seconds=2, max_retries=1)


class TestWatchDecoratorTimeout:
    async def test_timeout_raises(self, watchdog):
        @watchdog.watch
        async def slow_llm_call():
            await asyncio.sleep(10)
            return "done"

        with pytest.raises(asyncio.TimeoutError):
            await slow_llm_call()

        assert watchdog._stats["timeouts"] >= 1

    async def test_fast_call_succeeds(self, watchdog):
        @watchdog.watch
        async def fast_call():
            return "result"

        result = await fast_call()
        assert result == "result"
        assert watchdog._stats["successful"] == 1
        assert watchdog._stats["timeouts"] == 0

    async def test_retry_on_failure(self, watchdog):
        call_count = 0

        @watchdog.watch
        async def flaky_call():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First attempt fails")
            return "ok"

        result = await flaky_call()
        assert result == "ok"
        assert call_count == 2

    async def test_exhausts_retries(self, watchdog):
        @watchdog.watch
        async def always_fails():
            raise RuntimeError("Always broken")

        with pytest.raises(RuntimeError, match="Always broken"):
            await always_fails()

        assert watchdog._stats["failures"] >= 1


class TestStatsTracking:
    async def test_stats_after_calls(self, watchdog):
        @watchdog.watch
        async def good_call():
            return "ok"

        await good_call()
        await good_call()

        stats = watchdog.get_stats()
        assert stats["total_calls"] == 2
        assert stats["successful"] == 2
        assert stats["success_rate"] == 1.0
        assert stats["avg_latency_ms"] >= 0

    async def test_reset_stats(self, watchdog):
        @watchdog.watch
        async def good_call():
            return "ok"

        await good_call()
        watchdog.reset_stats()
        stats = watchdog.get_stats()
        assert stats["total_calls"] == 0
        assert stats["successful"] == 0

    async def test_mixed_stats(self, watchdog):
        @watchdog.watch
        async def good_call():
            return "ok"

        @watchdog.watch
        async def bad_call():
            raise RuntimeError("fail")

        await good_call()
        with pytest.raises(RuntimeError):
            await bad_call()

        stats = watchdog.get_stats()
        assert stats["total_calls"] == 2
        assert stats["successful"] == 1
        assert stats["failures"] >= 1
        assert stats["success_rate"] == 0.5

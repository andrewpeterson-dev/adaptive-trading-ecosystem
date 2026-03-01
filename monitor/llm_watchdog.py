"""
LLM Watchdog — monitors LLM calls for stalls, timeouts, and failures.
Wraps async LLM calls with timeout enforcement and retry logic.
"""

import asyncio
import time
from functools import wraps

import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


class LLMWatchdog:
    """Monitor LLM calls for stalls and failures."""

    def __init__(self, timeout_seconds: int = 0, max_retries: int = 1):
        settings = get_settings()
        self.timeout = timeout_seconds or settings.llm_timeout_seconds
        self.max_retries = max_retries
        self._stats = {
            "total_calls": 0,
            "successful": 0,
            "timeouts": 0,
            "failures": 0,
            "total_latency_ms": 0,
        }

    def watch(self, func):
        """Decorator to wrap async LLM calls with timeout and retry."""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            self._stats["total_calls"] += 1
            start = time.monotonic()

            last_error = None
            for attempt in range(self.max_retries + 1):
                try:
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=self.timeout,
                    )
                    latency_ms = round((time.monotonic() - start) * 1000)
                    self._stats["successful"] += 1
                    self._stats["total_latency_ms"] += latency_ms

                    logger.debug(
                        "llm_call_ok",
                        func=func.__name__,
                        attempt=attempt + 1,
                        latency_ms=latency_ms,
                    )
                    return result

                except asyncio.TimeoutError:
                    self._stats["timeouts"] += 1
                    last_error = asyncio.TimeoutError(
                        f"{func.__name__} timed out after {self.timeout}s (attempt {attempt + 1})"
                    )
                    logger.warning(
                        "llm_call_timeout",
                        func=func.__name__,
                        timeout=self.timeout,
                        attempt=attempt + 1,
                    )
                    if attempt == self.max_retries:
                        self._log_stall(func.__name__, self.timeout)
                        raise last_error

                except Exception as e:
                    self._stats["failures"] += 1
                    last_error = e
                    logger.warning(
                        "llm_call_failed",
                        func=func.__name__,
                        error=str(e),
                        attempt=attempt + 1,
                    )
                    if attempt == self.max_retries:
                        raise

            raise last_error  # Should not reach here, but safety net

        return wrapper

    def _log_stall(self, func_name: str, timeout: float):
        """Log a stall event for alerting."""
        logger.error(
            "llm_stall_detected",
            func=func_name,
            timeout_seconds=timeout,
            total_timeouts=self._stats["timeouts"],
        )

    def get_stats(self) -> dict:
        """Return watchdog statistics."""
        total = self._stats["total_calls"]
        successful = self._stats["successful"]
        avg_latency = (
            round(self._stats["total_latency_ms"] / successful)
            if successful > 0
            else 0
        )

        return {
            "total_calls": total,
            "successful": successful,
            "timeouts": self._stats["timeouts"],
            "failures": self._stats["failures"],
            "success_rate": round(successful / total, 3) if total > 0 else 1.0,
            "avg_latency_ms": avg_latency,
        }

    def reset_stats(self):
        """Reset all statistics."""
        self._stats = {
            "total_calls": 0,
            "successful": 0,
            "timeouts": 0,
            "failures": 0,
            "total_latency_ms": 0,
        }

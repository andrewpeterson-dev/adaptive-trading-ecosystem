"""Small in-memory rate limiter with per-key windows."""

from __future__ import annotations

import time
from collections import defaultdict

_STALE_BUCKET_TTL_SECONDS = 24 * 60 * 60
_CLEANUP_INTERVAL_SECONDS = 300


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = 0.0

    def check(self, bucket: str, key: str, *, limit: int, window_seconds: int) -> None:
        now = time.time()
        if now - self._last_cleanup >= _CLEANUP_INTERVAL_SECONDS:
            self._cleanup(now)
        bucket_key = f"{bucket}:{key}"
        timestamps = [ts for ts in self._buckets[bucket_key] if now - ts < window_seconds]
        if len(timestamps) >= limit:
            retry_after = max(1, int(window_seconds - (now - timestamps[0])))
            raise RateLimitExceeded(retry_after=retry_after)
        timestamps.append(now)
        self._buckets[bucket_key] = timestamps

    def clear(self) -> None:
        self._buckets.clear()
        self._last_cleanup = 0.0

    def _cleanup(self, now: float) -> None:
        cutoff = now - _STALE_BUCKET_TTL_SECONDS
        for bucket_key, timestamps in list(self._buckets.items()):
            fresh = [ts for ts in timestamps if ts >= cutoff]
            if fresh:
                self._buckets[bucket_key] = fresh
            else:
                del self._buckets[bucket_key]
        self._last_cleanup = now


class RateLimitExceeded(RuntimeError):
    def __init__(self, *, retry_after: int) -> None:
        super().__init__("Rate limit exceeded")
        self.retry_after = retry_after


rate_limiter = InMemoryRateLimiter()

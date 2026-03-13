"""Small in-memory rate limiter with per-key windows."""

from __future__ import annotations

import time
from collections import defaultdict


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def check(self, bucket: str, key: str, *, limit: int, window_seconds: int) -> None:
        now = time.time()
        bucket_key = f"{bucket}:{key}"
        timestamps = [ts for ts in self._buckets[bucket_key] if now - ts < window_seconds]
        if len(timestamps) >= limit:
            retry_after = max(1, int(window_seconds - (now - timestamps[0])))
            raise RateLimitExceeded(retry_after=retry_after)
        timestamps.append(now)
        self._buckets[bucket_key] = timestamps


class RateLimitExceeded(RuntimeError):
    def __init__(self, *, retry_after: int) -> None:
        super().__init__("Rate limit exceeded")
        self.retry_after = retry_after


rate_limiter = InMemoryRateLimiter()

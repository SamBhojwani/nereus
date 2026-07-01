"""
A tiny in-process, per-IP rate limiter.

Why this exists: every endpoint fans out to rate-limited free tiers (NewsData, YouTube,
and the LLM's per-day token budget — the binding constraint of the whole app). Without a
limiter, a single client in a loop can drain the shared daily budget in seconds and take
the demo down for everyone. A fixed-window counter per IP is crude but exactly right for
v1 (one process, one region); swap for Redis if this ever runs multi-instance.

Deliberately dependency-free and self-contained, like app/cache.py.
"""
from __future__ import annotations

import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(self, *, max_requests: int, window_seconds: float):
        self._max = max_requests
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str) -> tuple[bool, float]:
        """Register a hit for `key`. Returns (allowed, retry_after_seconds).

        Runs entirely between awaits on the event loop, so the plain dict/deque need no
        lock. Old timestamps are pruned lazily on each call, so memory tracks active IPs.
        """
        now = time.monotonic()
        cutoff = now - self._window
        bucket = self._hits.setdefault(key, deque())
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= self._max:
            retry_after = self._window - (now - bucket[0])
            return False, max(0.0, retry_after)

        bucket.append(now)
        return True, 0.0

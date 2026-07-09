"""
A tiny in-memory TTL cache.

Caching is architecture in Nereus, not an afterthought: every free API (news, YouTube,
the LLM) is rate-limited, so repeat searches must not re-hit them. In v1 an in-process
dict + TTL is plenty (BUILD_BRIEF). The interface is deliberately small so it can be
swapped for Redis later without callers changing.

Stores fully-built results keyed by a string. The retrieval+classification pipeline is
cached as a unit, so a cache hit skips BOTH the source APIs and the LLM.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Optional


class TTLCache:
    def __init__(self, *, default_ttl: float = 300.0):
        self._default_ttl = default_ttl
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.monotonic() >= expires_at:
                self._store.pop(key, None)
                return None
            return value

    async def get_with_staleness(
        self, key: str, *, max_stale: float = 0.0
    ) -> Optional[tuple[Any, bool]]:
        """Return (value, is_fresh), or None if absent/too old.

        Unlike `get`, an expired entry is NOT evicted immediately: within `max_stale`
        seconds past expiry it is returned with is_fresh=False, so callers can serve it
        instantly while they rebuild in the background (stale-while-revalidate). This is
        what keeps a visitor from ever waiting on the full retrieve+classify pipeline
        just because a TTL lapsed a minute before they arrived.
        """
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            age_past_expiry = time.monotonic() - expires_at
            if age_past_expiry < 0:
                return value, True
            if age_past_expiry < max_stale:
                return value, False
            self._store.pop(key, None)
            return None

    async def set(self, key: str, value: Any, *, ttl: float | None = None) -> None:
        async with self._lock:
            self._store[key] = (time.monotonic() + (ttl or self._default_ttl), value)

    async def get_or_set(
        self,
        key: str,
        producer: Callable[[], Awaitable[Any]],
        *,
        ttl: float | None = None,
    ) -> Any:
        """Return the cached value, or run `producer()`, cache it, and return it."""
        cached = await self.get(key)
        if cached is not None:
            return cached
        value = await producer()
        await self.set(key, value, ttl=ttl)
        return value

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

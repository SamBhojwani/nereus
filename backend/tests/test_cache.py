"""TTLCache — including the stale-while-revalidate read used by the API layer."""
from __future__ import annotations

import asyncio

from app.cache import TTLCache


async def test_fresh_hit():
    c = TTLCache()
    await c.set("k", "v", ttl=60)
    assert await c.get("k") == "v"
    assert await c.get_with_staleness("k", max_stale=60) == ("v", True)


async def test_miss_returns_none():
    c = TTLCache()
    assert await c.get("nope") is None
    assert await c.get_with_staleness("nope", max_stale=60) is None


async def test_stale_entry_served_within_window():
    c = TTLCache()
    await c.set("k", "v", ttl=0.01)
    await asyncio.sleep(0.03)
    # plain get: expired -> gone
    # stale-aware get: still served, flagged not-fresh
    assert await c.get_with_staleness("k", max_stale=60) == ("v", False)


async def test_stale_entry_evicted_past_window():
    c = TTLCache()
    await c.set("k", "v", ttl=0.01)
    await asyncio.sleep(0.03)
    assert await c.get_with_staleness("k", max_stale=0.001) is None
    # and it was evicted, not just hidden
    assert await c.get_with_staleness("k", max_stale=60) is None


async def test_plain_get_still_evicts_expired():
    c = TTLCache()
    await c.set("k", "v", ttl=0.01)
    await asyncio.sleep(0.03)
    assert await c.get("k") is None

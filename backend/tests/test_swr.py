"""The stale-while-revalidate request path: a stale hit returns instantly and
triggers exactly one background rebuild."""
from __future__ import annotations

import asyncio

import app.main as m
from app.models import ContentItem, SourceType, Stance, Classification


def _items(tag: str) -> list[ContentItem]:
    return [ContentItem(
        id=tag, source_type=SourceType.NEWS, title=tag, url=f"https://x.com/{tag}",
        classification=Classification(stance=Stance.FACTUAL, confidence=0.9),
    )]


async def test_stale_hit_returns_old_and_refreshes(monkeypatch):
    key = "search::swr-test::all"
    calls = 0

    async def fake_pipeline(query, sources):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)  # simulate slow retrieve+classify
        return _items("new")

    monkeypatch.setattr(m, "_retrieve_and_classify", fake_pipeline)
    await m.cache.set(key, _items("old"), ttl=0.01)
    await asyncio.sleep(0.03)  # let it go stale

    result = await m._cached_pipeline(key, "swr-test", None, ttl=60)
    assert result[0].id == "old"          # served instantly, no waiting on the rebuild
    assert calls in (0, 1)                # refresh may still be starting

    await asyncio.sleep(0.1)              # let the background refresh finish
    assert calls == 1                     # exactly one rebuild (in-flight guard)
    refreshed = await m.cache.get(key)
    assert refreshed[0].id == "new"       # cache now holds the fresh result

    # next call is a fresh hit — no second rebuild
    result2 = await m._cached_pipeline(key, "swr-test", None, ttl=60)
    assert result2[0].id == "new"
    assert calls == 1


async def test_true_miss_builds_inline(monkeypatch):
    key = "search::swr-miss::all"

    async def fake_pipeline(query, sources):
        return _items("built")

    monkeypatch.setattr(m, "_retrieve_and_classify", fake_pipeline)
    result = await m._cached_pipeline(key, "swr-miss", None, ttl=60)
    assert result[0].id == "built"
    assert (await m.cache.get(key))[0].id == "built"

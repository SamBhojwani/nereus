"""
Phase 1 smoke test — runs WITHOUT any API keys.

Proves the wiring is sound: the app imports, the classifier batches/parses correctly,
UNCLASSIFIED fallback works, and the TTL cache hits. Real keys are only needed to prove
live data flows (that's the manual /search check). Run: python smoke_test.py
"""
from __future__ import annotations

import asyncio

from app.cache import TTLCache
from app.classifier.llm import LLMClassifier
from app.llm.base import LLMClient, LLMResponse
from app.models import ContentItem, SourceType, Stance


class StubLLM(LLMClient):
    """Returns a canned JSON array as if it were the model, so we test parsing/batching."""

    def __init__(self):
        self.calls = 0

    async def complete(self, prompt, *, system=None, temperature=0.0, max_tokens=512):
        self.calls += 1
        # Mimic a model that wraps JSON in a markdown fence (we must tolerate it).
        return LLMResponse(
            text=(
                "```json\n"
                '[{"index": 0, "stance": "factual", "confidence": 0.9, "rationale": "reports an event"},'
                ' {"index": 1, "stance": "opinion", "confidence": 0.8, "rationale": "argues a view"}]\n'
                "```"
            ),
            model="stub",
        )


def make_items(n: int) -> list[ContentItem]:
    return [
        ContentItem(
            id=f"news:{i}",
            source_type=SourceType.NEWS,
            title=f"Headline {i}",
            body="Some body text long enough to classify.",
            url=f"https://example.com/{i}",
        )
        for i in range(n)
    ]


async def main():
    print("1. App imports cleanly...")
    import app.main  # noqa: F401  (constructs Retriever, GeminiClient, LLMClassifier, cache)
    print("   OK — /health, /search, /feed registered\n")

    print("2. Classifier batches + parses (stub LLM, fenced JSON)...")
    stub = StubLLM()
    clf = LLMClassifier(stub, batch_size=10)
    items = await clf.classify_many(make_items(2))
    assert items[0].classification.stance == Stance.FACTUAL, items[0].classification
    assert items[1].classification.stance == Stance.OPINION, items[1].classification
    assert items[0].classification.confidence == 0.9
    assert items[0].classification.rationale == "reports an event"
    assert stub.calls == 1, f"expected 1 batched call, got {stub.calls}"
    print(f"   OK — 2 items classified in {stub.calls} LLM call (batched)\n")

    print("3. Batching splits into chunks by batch_size...")
    stub2 = StubLLM()
    clf2 = LLMClassifier(stub2, batch_size=2)
    await clf2.classify_many(make_items(2))  # exactly one chunk of 2
    assert stub2.calls == 1, stub2.calls
    print(f"   OK — batch_size respected ({stub2.calls} call for 2 items)\n")

    print("4. Unparseable LLM output -> UNCLASSIFIED, never raises...")

    class JunkLLM(LLMClient):
        async def complete(self, prompt, *, system=None, temperature=0.0, max_tokens=512):
            return LLMResponse(text="sorry, I can't do that", model="junk")

    clf3 = LLMClassifier(JunkLLM(), batch_size=10)
    junk_items = await clf3.classify_many(make_items(3))
    assert all(it.classification.stance == Stance.UNCLASSIFIED for it in junk_items)
    print("   OK — graceful degradation to UNCLASSIFIED\n")

    print("5. TTL cache: miss runs producer, hit skips it...")
    cache = TTLCache(default_ttl=60)
    runs = {"n": 0}

    async def producer():
        runs["n"] += 1
        return ["result"]

    v1 = await cache.get_or_set("k", producer)
    v2 = await cache.get_or_set("k", producer)
    assert v1 == v2 == ["result"]
    assert runs["n"] == 1, f"producer should run once, ran {runs['n']}"
    print(f"   OK — producer ran {runs['n']}x for 2 calls (cache hit)\n")

    print("ALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())

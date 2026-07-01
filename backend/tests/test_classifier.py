"""Classifier behavior: JSON tolerance, batch index mapping, and the rule that
classification must NEVER crash a request — any failure degrades to UNCLASSIFIED."""
from __future__ import annotations

import pytest

from app.classifier.llm import LLMClassifier, _first_json
from app.llm.base import LLMClient, LLMResponse
from app.models import ContentItem, SourceType, Stance


class ScriptedLLM(LLMClient):
    """Returns whatever text you queue; raises if told to."""
    def __init__(self, text: str = "", *, raises: Exception | None = None):
        self.text = text
        self.raises = raises
        self.calls = 0

    async def complete(self, prompt, *, system=None, temperature=0.0, max_tokens=512):
        self.calls += 1
        if self.raises:
            raise self.raises
        return LLMResponse(text=self.text, model="scripted")


def _item(i: int, title: str = "t") -> ContentItem:
    return ContentItem(id=f"id{i}", source_type=SourceType.NEWS, title=title,
                       body="body", url=f"https://example.com/{i}")


def test_first_json_tolerates_markdown_fences():
    assert _first_json('```json\n{"stance": "factual"}\n```') == {"stance": "factual"}


def test_first_json_tolerates_surrounding_prose():
    assert _first_json('Sure! Here you go: [{"index": 0}] hope that helps') == [{"index": 0}]


def test_first_json_returns_none_on_garbage():
    assert _first_json("not json at all") is None
    assert _first_json("") is None


async def test_batch_maps_results_by_declared_index():
    # Deliberately out of order — mapping must follow the "index" field, not position.
    payload = (
        '[{"index": 1, "stance": "opinion", "confidence": 0.9},'
        ' {"index": 0, "stance": "factual", "confidence": 0.8}]'
    )
    clf = LLMClassifier(ScriptedLLM(payload), batch_size=10)
    items = await clf.classify_many([_item(0), _item(1)])
    assert items[0].classification.stance is Stance.FACTUAL
    assert items[1].classification.stance is Stance.OPINION


async def test_missing_index_stays_unclassified():
    # Model only returned one of two items — the other must not crash or mislabel.
    clf = LLMClassifier(ScriptedLLM('[{"index": 0, "stance": "factual", "confidence": 1.0}]'),
                        batch_size=10)
    items = await clf.classify_many([_item(0), _item(1)])
    assert items[0].classification.stance is Stance.FACTUAL
    assert items[1].classification.stance is Stance.UNCLASSIFIED


async def test_llm_exception_degrades_not_raises():
    clf = LLMClassifier(ScriptedLLM(raises=RuntimeError("boom")), batch_size=10)
    items = await clf.classify_many([_item(0), _item(1), _item(2)])
    assert all(it.classification.stance is Stance.UNCLASSIFIED for it in items)


async def test_confidence_is_clamped():
    clf = LLMClassifier(ScriptedLLM('[{"index":0,"stance":"factual","confidence":9.9}]'),
                        batch_size=10)
    items = await clf.classify_many([_item(0)])
    assert 0.0 <= items[0].classification.confidence <= 1.0


async def test_empty_input_returns_empty():
    clf = LLMClassifier(ScriptedLLM("[]"))
    assert await clf.classify_many([]) == []

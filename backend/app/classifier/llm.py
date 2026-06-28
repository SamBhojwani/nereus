"""
LLMClassifier: the v1 fact-vs-opinion classifier, implemented as an LLM prompt.

It satisfies the Classifier interface, so a fine-tuned model can replace it later
(Phase 6) and the evaluation harness (Phase 2) scores either one identically.

Two design points that matter:
  - We keep the `rationale` the model gives — it's needed for Phase 2 error analysis
    and for the "why" shown on cards in the UI.
  - `classify_many()` BATCHES several items into one LLM call. That batching is the
    single biggest lever for staying inside the free-tier request cap (BUILD_BRIEF),
    turning ~N calls into ~N/batch_size calls.

Robustness rule: classification must never crash a request. Any parse/LLM failure
degrades an item to UNCLASSIFIED rather than raising.
"""
from __future__ import annotations

import json
import os
import re

from app.classifier.base import Classifier
from app.llm.base import LLMClient
from app.models import Classification, ContentItem, Stance

DEFAULT_BATCH_SIZE = 10

SYSTEM_PROMPT = (
    "You are a precise media classifier. For each piece of text you judge whether it "
    "is FACTUAL (reports verifiable events, data, or statements, in a neutral register) "
    "or OPINION (argues a position, predicts, editorializes, or expresses sentiment). "
    "Judge the dominant character of the text as a whole. Respond with JSON only — no prose, "
    "no markdown fences."
)

_SINGLE_INSTRUCTION = (
    "Classify the following item. Respond with a single JSON object of the form:\n"
    '{{"stance": "factual" | "opinion", "confidence": <0.0-1.0>, "rationale": "<one short sentence>"}}\n\n'
    "ITEM:\n{text}"
)

_BATCH_INSTRUCTION = (
    "Classify EACH of the {n} numbered items below. Respond with a JSON array of objects, "
    "one per item, in the same order, each of the form:\n"
    '{{"index": <int>, "stance": "factual" | "opinion", "confidence": <0.0-1.0>, '
    '"rationale": "<one short sentence>"}}\n'
    "Return exactly {n} objects and nothing else.\n\n"
    "ITEMS:\n{block}"
)


class LLMClassifier(Classifier):
    def __init__(self, llm: LLMClient, *, batch_size: int | None = None):
        self._llm = llm
        env_bs = os.getenv("CLASSIFY_BATCH_SIZE")
        self._batch_size = batch_size or (int(env_bs) if env_bs else DEFAULT_BATCH_SIZE)

    async def classify(self, item: ContentItem) -> Classification:
        text = item.text_for_classification()
        if not text:
            return Classification(stance=Stance.UNCLASSIFIED, rationale="empty item")
        try:
            resp = await self._llm.complete(
                _SINGLE_INSTRUCTION.format(text=_truncate(text)),
                system=SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=256,
            )
            obj = _first_json(resp.text)
            return _to_classification(obj) if obj is not None else _unparseable()
        except Exception:
            return _unparseable()

    async def classify_many(self, items: list[ContentItem]) -> list[ContentItem]:
        """Batch items into chunks; one LLM call per chunk. Order-preserving."""
        for start in range(0, len(items), self._batch_size):
            chunk = items[start : start + self._batch_size]
            results = await self._classify_chunk(chunk)
            for item, classification in zip(chunk, results):
                item.classification = classification
        return items

    async def _classify_chunk(self, chunk: list[ContentItem]) -> list[Classification]:
        if not chunk:
            return []
        # Single item: the array prompt is wasteful — use the single path.
        if len(chunk) == 1:
            return [await self.classify(chunk[0])]

        block = "\n\n".join(
            f"[{i}] {_truncate(it.text_for_classification()) or '(empty)'}"
            for i, it in enumerate(chunk)
        )
        try:
            resp = await self._llm.complete(
                _BATCH_INSTRUCTION.format(n=len(chunk), block=block),
                system=SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=128 * len(chunk),
            )
            parsed = _first_json(resp.text)
        except Exception:
            parsed = None

        # Map results back by their declared index; anything missing stays UNCLASSIFIED.
        out: list[Classification] = [_unparseable() for _ in chunk]
        if isinstance(parsed, list):
            for entry in parsed:
                if not isinstance(entry, dict):
                    continue
                idx = entry.get("index")
                if isinstance(idx, int) and 0 <= idx < len(chunk):
                    out[idx] = _to_classification(entry)
        return out


# --- helpers ----------------------------------------------------------------

_MAX_CHARS = 1500  # keep per-item text bounded so a batch fits the token budget


def _truncate(text: str) -> str:
    return text[:_MAX_CHARS]


def _unparseable() -> Classification:
    return Classification(stance=Stance.UNCLASSIFIED, rationale="classifier returned no usable result")


def _to_classification(obj: dict) -> Classification:
    raw = str(obj.get("stance", "")).strip().lower()
    stance = {"factual": Stance.FACTUAL, "opinion": Stance.OPINION}.get(raw, Stance.UNCLASSIFIED)
    try:
        conf = float(obj.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    rationale = obj.get("rationale")
    return Classification(
        stance=stance,
        confidence=conf,
        rationale=str(rationale) if rationale is not None else None,
    )


def _first_json(text: str):
    """
    Pull the first JSON value out of an LLM response, tolerating markdown fences
    and surrounding prose. Returns a dict/list, or None if nothing parses.
    """
    if not text:
        return None
    # Strip ```json ... ``` fences if present.
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    candidate = candidate.strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    # Fallback: grab the first {...} or [...] span and try that.
    match = re.search(r"(\{.*\}|\[.*\])", candidate, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None

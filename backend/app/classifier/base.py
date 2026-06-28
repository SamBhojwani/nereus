"""
Classifier: the fact-vs-opinion contract.

v1 implementation prompts an LLM. A future implementation could be a fine-tuned
DistilBERT. Because both satisfy THIS interface, swapping them is a one-line change
and your evaluation harness can score either one the same way.

Keep this interface tiny and stable — it's the spine of the whole "AI" in the project.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import Classification, ContentItem


class Classifier(ABC):
    @abstractmethod
    async def classify(self, item: ContentItem) -> Classification:
        """Judge a single item. Reads item.text_for_classification()."""
        ...

    async def classify_many(self, items: list[ContentItem]) -> list[ContentItem]:
        """
        Default: classify each item and attach the result.
        Override this to BATCH (one LLM call for several short items) — that batching
        is the main lever for staying inside free-tier request limits.
        """
        for item in items:
            item.classification = await self.classify(item)
        return items

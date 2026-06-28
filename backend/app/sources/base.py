"""
SourceProvider: the contract every content source obeys.

The pipeline only ever talks to this interface, never to a concrete source.
That's what lets you:
  - add a new source (just write a new subclass),
  - swap a source's internals (REST API today, vector retrieval later),
  - test the pipeline with a fake source,
all WITHOUT touching the classifier, ranking, API layer, or frontend.

Each provider's one job: take a query, return normalized ContentItem objects.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import ContentItem, SourceType


class SourceProvider(ABC):
    """Base class for all content sources (news, Reddit, YouTube, ...)."""

    #: Which SourceType this provider emits. Set by each subclass.
    source_type: SourceType

    @abstractmethod
    async def fetch(self, query: str, *, limit: int = 20) -> list[ContentItem]:
        """
        Return up to `limit` items matching `query`, already mapped into the
        normalized ContentItem shape. Implementations should:
          - call their underlying API/feed,
          - map each raw record to ContentItem (id prefixed with the source, e.g. "news:..."),
          - leave `classification` at its default (the classifier stage fills it in),
          - never raise on an empty result — return [] instead.
        """
        ...

    def healthcheck(self) -> bool:
        """
        Cheap 'are my credentials/config present?' check. Override where useful.
        Lets the app report which sources are live without making a real call.
        """
        return True

"""
retrieve(): the single, named retrieval step — and the most important "open door".

v1 (now):      fan out to the registered SourceProviders, merge their results.
Phase 4 (RAG): replace the BODY of this function with
                 embed(query) -> vector-store search -> dedup -> return,
               and NOTHING else in the app changes, because every caller depends
               only on this signature: (query) -> list[ContentItem].

Keep the signature stable. Change only what's inside.
"""
from __future__ import annotations

import asyncio

from app.models import ContentItem, SourceType
from app.sources.base import SourceProvider


class Retriever:
    def __init__(self, providers: list[SourceProvider]):
        self._providers = providers

    async def retrieve(
        self,
        query: str,
        *,
        sources: list[SourceType] | None = None,
        per_source: int = 20,
    ) -> list[ContentItem]:
        """Gather items for `query` from all (or selected) sources, concurrently."""
        active = [
            p for p in self._providers
            if sources is None or p.source_type in sources
        ]
        if not active:
            return []

        results = await asyncio.gather(
            *(p.fetch(query, limit=per_source) for p in active),
            return_exceptions=True,  # one dead source must not kill the request
        )

        items: list[ContentItem] = []
        for r in results:
            if isinstance(r, Exception):
                continue  # TODO: log the failing source
            items.extend(r)

        # Phase 4 will add semantic dedup here. For now, a cheap exact-URL dedup.
        seen: set[str] = set()
        deduped: list[ContentItem] = []
        for it in items:
            if it.url in seen:
                continue
            seen.add(it.url)
            deduped.append(it)
        return deduped

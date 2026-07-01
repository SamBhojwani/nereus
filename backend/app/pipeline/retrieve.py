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
import difflib
import re

from app.models import ContentItem, SourceType
from app.sources.base import SourceProvider

# Cap the items that leave retrieval. This bounds the classification cost per request —
# the binding constraint is the LLM's per-minute token budget, and 30 diverse items keeps
# a search inside one window while still filling the grid. Override with RETRIEVE_MAX_ITEMS.
DEFAULT_MAX_ITEMS = 30
# Two titles at/above this similarity are treated as the same story (near-dup dedup).
_TITLE_SIMILARITY = 0.82


class Retriever:
    def __init__(self, providers: list[SourceProvider]):
        self._providers = providers

    async def retrieve(
        self,
        query: str,
        *,
        sources: list[SourceType] | None = None,
        per_source: int = 20,
        max_items: int = DEFAULT_MAX_ITEMS,
    ) -> list[ContentItem]:
        """Gather items for `query` from all (or selected) sources, concurrently,
        then interleave for source diversity, dedup, and cap the total."""
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

        per_source_items = [r for r in results if not isinstance(r, Exception)]
        interleaved = _round_robin(per_source_items)
        return _dedup(interleaved)[:max_items]


def _round_robin(lists: list[list[ContentItem]]) -> list[ContentItem]:
    """Interleave sources so a later per-source cap keeps the mix balanced (otherwise
    the first source could fill the whole cap and crowd the others out)."""
    out: list[ContentItem] = []
    for i in range(max((len(l) for l in lists), default=0)):
        for l in lists:
            if i < len(l):
                out.append(l[i])
    return out


def _norm_title(title: str | None) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (title or "").lower()).strip()


def _dedup(items: list[ContentItem]) -> list[ContentItem]:
    """Drop exact-URL repeats and near-identical titles (e.g. the same wire story
    republished, or a channel's hourly 'Top Headlines' posts). Phase 4 swaps this for
    semantic dedup; order-preserving, keeps the first occurrence."""
    seen_urls: set[str] = set()
    kept: list[ContentItem] = []
    kept_titles: list[str] = []
    for it in items:
        # Drop anything that isn't a plain http(s) link — a bad/hostile source URL must
        # never reach the client's href (defense in depth with the frontend guard).
        if not it.url.lower().startswith(("http://", "https://")):
            continue
        if it.url in seen_urls:
            continue
        nt = _norm_title(it.title)
        if nt and any(
            difflib.SequenceMatcher(None, nt, kt).ratio() >= _TITLE_SIMILARITY
            for kt in kept_titles
        ):
            continue
        seen_urls.add(it.url)
        kept.append(it)
        if nt:
            kept_titles.append(nt)
    return kept

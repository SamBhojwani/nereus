"""
Nereus API — the clean JSON boundary.

The frontend (React now, maybe a mobile app later) is a THIN consumer of these
endpoints. All real work — retrieval, classification, dedup, caching — happens here and
is returned as plain ContentItem JSON. That boundary is what keeps the "scale to mobile
later" door open: any client just calls these endpoints.

Run locally:  uvicorn app.main:app --reload
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()  # read backend/.env before anything else constructs a client

from app.cache import TTLCache
from app.classifier.llm import LLMClassifier
from app.llm.factory import make_llm
from app.models import ContentItem, SourceType
from app.pipeline.retrieve import Retriever
from app.sources.news import NewsDataSource

# --- wiring (the only place concrete implementations are named) ---------------
# Add RedditSource() and YouTubeSource() here in Phase 3 — nothing downstream changes.
PROVIDERS = [
    NewsDataSource(),
]
retriever = Retriever(PROVIDERS)

# Phase 1: the classifier is an LLM behind the swappable LLMClient seam.
# Provider is chosen by LLM_PROVIDER (gemini|groq) — see app/llm/factory.py.
llm = make_llm()
classifier = LLMClassifier(llm)

# Caching is load-bearing: a hit skips BOTH the source APIs and the LLM.
cache = TTLCache()
_TTL_SEARCH = float(os.getenv("CACHE_TTL_SEARCH", "300"))
_TTL_FEED = float(os.getenv("CACHE_TTL_FEED", "900"))
_FEED_QUERY = "top news today"
# ------------------------------------------------------------------------------

app = FastAPI(title="Nereus API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten to your frontend origin before deploy
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _retrieve_and_classify(
    query: str, sources: list[SourceType] | None
) -> list[ContentItem]:
    items = await retriever.retrieve(query, sources=sources)
    return await classifier.classify_many(items)


def _cache_key(query: str, sources: list[SourceType] | None) -> str:
    src = ",".join(sorted(s.value for s in sources)) if sources else "all"
    return f"{query.strip().lower()}::{src}"


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "sources": {p.source_type.value: p.healthcheck() for p in PROVIDERS},
        "classifier": {"llm": llm.healthcheck(), "model": getattr(llm, "_model_name", None)},
    }


@app.get("/search", response_model=list[ContentItem])
async def search(
    q: str = Query(..., min_length=1, description="Topic to search for"),
    sources: list[SourceType] | None = Query(None, description="Filter to these sources"),
) -> list[ContentItem]:
    return await cache.get_or_set(
        f"search::{_cache_key(q, sources)}",
        lambda: _retrieve_and_classify(q, sources),
        ttl=_TTL_SEARCH,
    )


@app.get("/feed", response_model=list[ContentItem])
async def feed() -> list[ContentItem]:
    # v1 default feed = a fixed topic set; personalize later.
    return await cache.get_or_set(
        f"feed::{_cache_key(_FEED_QUERY, None)}",
        lambda: _retrieve_and_classify(_FEED_QUERY, None),
        ttl=_TTL_FEED,
    )

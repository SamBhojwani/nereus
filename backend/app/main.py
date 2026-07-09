"""
Nereus API — the clean JSON boundary.

The frontend (React now, maybe a mobile app later) is a THIN consumer of these
endpoints. All real work — retrieval, classification, dedup, caching — happens here and
is returned as plain ContentItem JSON. That boundary is what keeps the "scale to mobile
later" door open: any client just calls these endpoints.

Run locally:  uvicorn app.main:app --reload
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()  # read backend/.env before anything else constructs a client

from app.cache import TTLCache
from app.classifier.llm import LLMClassifier
from app.llm.factory import make_llm
from app.models import ContentItem, SourceType, Stance
from app.pipeline.retrieve import Retriever
from app.ratelimit import SlidingWindowLimiter
from app.sources.news import NewsDataSource
from app.sources.reddit import RedditSource
from app.sources.youtube import YouTubeSource

# --- wiring (the only place concrete implementations are named) ---------------
# Each source is one line here; nothing downstream (classifier, cache, API, UI) changes.
# A source with no credentials just returns [] and reports down in /health.
PROVIDERS = [
    NewsDataSource(),
    RedditSource(),
    YouTubeSource(),
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
# When classification wholesale fails (LLM rate-limited/down), the items are fine but
# every badge is UNCLASSIFIED. Cache that only briefly so results self-heal the moment
# the token budget returns, instead of serving dead badges for the full TTL.
_TTL_DEGRADED = float(os.getenv("CACHE_TTL_DEGRADED", "30"))
# How long past expiry a cached result may still be served while a background refresh
# runs (stale-while-revalidate). Feed content ages gracefully; a wait does not.
_STALE_WINDOW = float(os.getenv("CACHE_STALE_WINDOW", "21600"))
_FEED_QUERY = "top news today"
_MAX_QUERY_LEN = 200  # a topic search; anything longer is abuse and wastes token budget

# CORS: default to the local dev origins; in prod set CORS_ORIGINS to your deployed
# frontend URL(s), comma-separated. "*" stays available as an explicit opt-out only.
_CORS_ORIGINS = [
    o.strip() for o in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if o.strip()
]

# Per-IP rate limit on the expensive endpoints — protects the shared free-tier budgets.
_rate_limiter = SlidingWindowLimiter(
    max_requests=int(os.getenv("RATE_LIMIT_REQUESTS", "20")),
    window_seconds=float(os.getenv("RATE_LIMIT_WINDOW", "60")),
)
_RATE_LIMITED_PATHS = ("/search", "/feed")
# ------------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Warm the default feed in the background at boot. A cold-started container (e.g.
    # a slept HF Space) begins the retrieve+classify work immediately instead of making
    # the first visitor pay for it. Fire-and-forget: a warm failure must never block
    # startup — the request path builds the feed itself if this didn't finish.
    warm = asyncio.create_task(
        _refresh_in_background(
            f"feed::{_cache_key(_FEED_QUERY, None)}", _FEED_QUERY, None, _TTL_FEED
        )
    )
    yield
    warm.cancel()


app = FastAPI(title="Nereus API", version="0.1.0", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["GET"],        # read-only API; no need to allow the rest
    allow_headers=["*"],
)


def _client_ip(request: Request) -> str:
    # Behind a proxy (Render/Fly/etc.), the real client is the first X-Forwarded-For hop.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path in _RATE_LIMITED_PATHS:
        allowed, retry_after = _rate_limiter.check(_client_ip(request))
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={"Retry-After": str(int(retry_after) + 1)},
            )
    return await call_next(request)


async def _retrieve_and_classify(
    query: str, sources: list[SourceType] | None
) -> list[ContentItem]:
    items = await retriever.retrieve(query, sources=sources)
    return await classifier.classify_many(items)


def _cache_key(query: str, sources: list[SourceType] | None) -> str:
    src = ",".join(sorted(s.value for s in sources)) if sources else "all"
    return f"{query.strip().lower()}::{src}"


def _mostly_classified(items: list[ContentItem]) -> bool:
    """True if at least half the items got a real stance — i.e. classification worked."""
    if not items:
        return False
    ok = sum(1 for it in items if it.classification.stance is not Stance.UNCLASSIFIED)
    return ok >= len(items) / 2


_refreshing: set[str] = set()  # keys with a background rebuild in flight


async def _produce_and_cache(
    key: str, query: str, sources: list[SourceType] | None, ttl: float
) -> list[ContentItem]:
    items = await _retrieve_and_classify(query, sources)
    await cache.set(key, items, ttl=ttl if _mostly_classified(items) else _TTL_DEGRADED)
    return items


async def _refresh_in_background(
    key: str, query: str, sources: list[SourceType] | None, ttl: float
) -> None:
    try:
        await _produce_and_cache(key, query, sources, ttl)
    except Exception:
        pass  # a failed refresh just means we try again on a later request
    finally:
        _refreshing.discard(key)


async def _cached_pipeline(
    key: str, query: str, sources: list[SourceType] | None, ttl: float
) -> list[ContentItem]:
    """Cache the retrieve+classify unit, stale-while-revalidate style.

    Fresh hit  -> return it.
    Stale hit  -> return it IMMEDIATELY and rebuild in the background, so a lapsed TTL
                  costs the visitor nothing (the pipeline can take 4-30s; minutes-old
                  news served for those seconds is the right trade).
    Miss       -> build inline (only the very first request ever pays full price).

    Degraded results (classification mostly failed) still get only a short TTL so they
    self-heal quickly.
    """
    entry = await cache.get_with_staleness(key, max_stale=_STALE_WINDOW)
    if entry is not None:
        items, fresh = entry
        if not fresh and key not in _refreshing:
            _refreshing.add(key)
            asyncio.create_task(_refresh_in_background(key, query, sources, ttl))
        return items
    return await _produce_and_cache(key, query, sources, ttl)


@app.get("/")
async def root() -> dict:
    # Friendly landing for anyone who hits the bare API URL (e.g. the HF Space page).
    return {
        "name": "Nereus API",
        "description": "Fact-vs-opinion classification over live news, Reddit, and YouTube.",
        "endpoints": {"health": "/health", "search": "/search?q=...", "feed": "/feed", "docs": "/docs"},
    }


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "sources": {p.source_type.value: p.healthcheck() for p in PROVIDERS},
        "classifier": {"llm": llm.healthcheck(), "model": getattr(llm, "_model_name", None)},
    }


@app.get("/search", response_model=list[ContentItem])
async def search(
    q: str = Query(..., min_length=1, max_length=_MAX_QUERY_LEN, description="Topic to search for"),
    sources: list[SourceType] | None = Query(None, description="Filter to these sources"),
) -> list[ContentItem]:
    return await _cached_pipeline(
        f"search::{_cache_key(q, sources)}", q, sources, _TTL_SEARCH
    )


@app.get("/feed", response_model=list[ContentItem])
async def feed() -> list[ContentItem]:
    # v1 default feed = a fixed topic set; personalize later.
    return await _cached_pipeline(
        f"feed::{_cache_key(_FEED_QUERY, None)}", _FEED_QUERY, None, _TTL_FEED
    )

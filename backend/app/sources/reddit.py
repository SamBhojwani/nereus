"""
Reddit source -> ContentItem, with two paths behind one class:

  - **RSS (default, no credentials):** Reddit's public search RSS feed. Needs no app,
    no OAuth, no moderation use case — works today. Lighter data (no score/comments).
  - **OAuth Data API (automatic when creds are set):** richer data (score, comments,
    thumbnails). Requires REDDIT_CLIENT_ID/SECRET from an approved Data API app.

`fetch()` picks the OAuth path if credentials are present, else RSS. So the moment an
approved app's keys land in .env, this upgrades itself — no code change.

Reddit gives Nereus the opinion-heavy class the classifier needs (news skews factual).
A descriptive REDDIT_USER_AGENT is required either way — Reddit blocks generic agents.
"""
from __future__ import annotations

import html
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from app.models import ContentItem, SourceType
from app.sources.base import SourceProvider

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
OAUTH_SEARCH_URL = "https://oauth.reddit.com/search"
RSS_SEARCH_URL = "https://www.reddit.com/search.rss"
ATOM = {"a": "http://www.w3.org/2005/Atom"}


class RedditSource(SourceProvider):
    source_type = SourceType.REDDIT

    def __init__(self, client_id: str | None = None, client_secret: str | None = None,
                 user_agent: str | None = None):
        self._id = client_id or os.getenv("REDDIT_CLIENT_ID")
        self._secret = client_secret or os.getenv("REDDIT_CLIENT_SECRET")
        self._ua = user_agent or os.getenv("REDDIT_USER_AGENT") or "nereus/0.1 (public RSS)"
        self._token: str | None = None
        self._token_expiry: float = 0.0

    def _has_oauth(self) -> bool:
        return bool(self._id and self._secret)

    def healthcheck(self) -> bool:
        # Always available: OAuth if configured, else public RSS.
        return True

    async def fetch(self, query: str, *, limit: int = 20) -> list[ContentItem]:
        try:
            async with httpx.AsyncClient(timeout=10, headers={"User-Agent": self._ua}) as client:
                if self._has_oauth():
                    return await self._fetch_oauth(client, query, limit)
                return await self._fetch_rss(client, query, limit)
        except (httpx.HTTPError, ValueError, ET.ParseError):
            return []  # a dead source must never crash the pipeline

    # --- public RSS path (no credentials) ------------------------------------

    async def _fetch_rss(self, client: httpx.AsyncClient, query: str, limit: int) -> list[ContentItem]:
        resp = await client.get(
            RSS_SEARCH_URL,
            # type=link restricts to posts (drops subreddit/user matches from search)
            params={"q": query, "sort": "relevance", "limit": limit, "type": "link"},
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)

        items: list[ContentItem] = []
        for entry in root.findall("a:entry", ATOM)[:limit]:
            link_el = entry.find("a:link", ATOM)
            url = link_el.get("href") if link_el is not None else None
            if not url:
                continue
            cat = entry.find("a:category", ATOM)
            author_el = entry.find("a:author/a:name", ATOM)
            handle = author_el.text if author_el is not None else None  # "/u/name"
            items.append(
                ContentItem(
                    id=f"reddit:{entry.findtext('a:id', default=url, namespaces=ATOM)}",
                    source_type=self.source_type,
                    title=entry.findtext("a:title", default=None, namespaces=ATOM),
                    body=_selftext_from_content(entry.findtext("a:content", default="", namespaces=ATOM)),
                    url=url,
                    author=(cat.get("label") if cat is not None else None),  # "r/subreddit"
                    author_handle=handle.lstrip("/") if handle else None,    # "u/name"
                    published_at=_parse_iso(
                        entry.findtext("a:published", default=None, namespaces=ATOM)
                        or entry.findtext("a:updated", default=None, namespaces=ATOM)
                    ),
                )
            )
        return items

    # --- OAuth Data API path (when creds are present) ------------------------

    async def _get_token(self, client: httpx.AsyncClient) -> str | None:
        if self._token and time.monotonic() < self._token_expiry:
            return self._token
        resp = await client.post(
            TOKEN_URL, data={"grant_type": "client_credentials"},
            auth=(self._id, self._secret),
        )
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload.get("access_token")
        self._token_expiry = time.monotonic() + payload.get("expires_in", 3600) - 60
        return self._token

    async def _fetch_oauth(self, client: httpx.AsyncClient, query: str, limit: int) -> list[ContentItem]:
        token = await self._get_token(client)
        if not token:
            return []
        resp = await client.get(
            OAUTH_SEARCH_URL,
            params={"q": query, "limit": limit, "sort": "relevance", "type": "link", "raw_json": 1},
            headers={"Authorization": f"bearer {token}"},
        )
        resp.raise_for_status()
        payload = resp.json()

        items: list[ContentItem] = []
        for child in (payload.get("data", {}).get("children") or [])[:limit]:
            d = child.get("data") or {}
            permalink = d.get("permalink")
            if not permalink:
                continue
            thumb = d.get("thumbnail")
            items.append(
                ContentItem(
                    id=f"reddit:{d.get('id') or permalink}",
                    source_type=self.source_type,
                    title=d.get("title"),
                    body=d.get("selftext") or None,
                    url=f"https://www.reddit.com{permalink}",
                    author=f"r/{d['subreddit']}" if d.get("subreddit") else None,
                    author_handle=f"u/{d['author']}" if d.get("author") else None,
                    published_at=_from_epoch(d.get("created_utc")),
                    thumbnail_url=thumb if (thumb or "").startswith("http") else None,
                    likes=d.get("score"),
                    comments=d.get("num_comments"),
                )
            )
        return items


# --- helpers ----------------------------------------------------------------

def _selftext_from_content(content_html: str) -> str | None:
    """Reddit's RSS <content> is HTML ending in a 'submitted by …' trailer.
    Keep the part before it, strip tags — that's the self-post body (empty for link posts)."""
    if not content_html:
        return None
    body_html = re.split(r"submitted by", content_html)[0]
    text = html.unescape(re.sub(r"<[^>]+>", " ", body_html)).strip()
    text = re.sub(r"\s+", " ", text)
    return text or None


def _parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _from_epoch(ts: float | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, OSError):
        return None

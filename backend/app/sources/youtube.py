"""
YouTube source: YouTube Data API v3 search -> ContentItem.

Same shape as news.py. Provides the video format, with an embeddable player URL
for faithful cards.

FREE-TIER LANDMINE: the API gives 10,000 units/day and a search costs **100 units**
→ only ~100 searches/day. The query cache in main.py is what keeps this from 403-ing
mid-demo, so cache hard. Get a free key at https://console.cloud.google.com (enable
"YouTube Data API v3").
"""
from __future__ import annotations

import os
from datetime import datetime

import httpx

from app.models import ContentItem, SourceType
from app.sources.base import SourceProvider

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


class YouTubeSource(SourceProvider):
    source_type = SourceType.YOUTUBE

    def __init__(self, api_key: str | None = None):
        self._key = api_key or os.getenv("YOUTUBE_API_KEY")

    def healthcheck(self) -> bool:
        return bool(self._key)

    async def fetch(self, query: str, *, limit: int = 20) -> list[ContentItem]:
        if not self._key:
            return []
        params = {
            "key": self._key,
            "q": query,
            "part": "snippet",
            "type": "video",
            "maxResults": min(limit, 50),  # API hard-caps at 50 per call
            "safeSearch": "moderate",
            "relevanceLanguage": "en",  # bias toward English (cuts livestream-compilation spam)
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(SEARCH_URL, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except (httpx.HTTPError, ValueError):
            return []

        items: list[ContentItem] = []
        for rec in (payload.get("items") or [])[:limit]:
            vid = (rec.get("id") or {}).get("videoId")
            snip = rec.get("snippet") or {}
            if not vid:
                continue
            thumbs = snip.get("thumbnails") or {}
            thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url")
            items.append(
                ContentItem(
                    id=f"youtube:{vid}",
                    source_type=self.source_type,
                    title=snip.get("title"),
                    body=snip.get("description") or None,
                    url=f"https://www.youtube.com/watch?v={vid}",
                    author=snip.get("channelTitle"),
                    published_at=_parse_iso(snip.get("publishedAt")),
                    thumbnail_url=thumb,
                    embed_url=f"https://www.youtube.com/embed/{vid}",  # faithful playable card
                )
            )
        return items


def _parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None

"""
Example concrete source: NewsData.io -> ContentItem.

This is the PATTERN every source follows. Reddit and YouTube providers are the
same shape: call the API, map each record into a ContentItem, prefix the id with
the source name, return a list. Nothing here knows about classification or the API
layer — it just produces normalized items.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from app.models import ContentItem, SourceType
from app.sources.base import SourceProvider

NEWSDATA_URL = "https://newsdata.io/api/1/latest"


class NewsDataSource(SourceProvider):
    source_type = SourceType.NEWS

    def __init__(self, api_key: str | None = None):
        self._key = api_key or os.getenv("NEWSDATA_API_KEY")

    def healthcheck(self) -> bool:
        return bool(self._key)

    async def fetch(self, query: str, *, limit: int = 20) -> list[ContentItem]:
        if not self._key:
            return []  # no key -> behave as an empty source, never crash the pipeline

        params = {"apikey": self._key, "q": query, "language": "en"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(NEWSDATA_URL, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except (httpx.HTTPError, ValueError):
            return []  # TODO: log; degrade gracefully

        items: list[ContentItem] = []
        for rec in (payload.get("results") or [])[:limit]:
            link = rec.get("link")
            if not link:
                continue
            items.append(
                ContentItem(
                    id=f"news:{rec.get('article_id') or link}",
                    source_type=self.source_type,
                    title=rec.get("title"),
                    body=rec.get("description") or rec.get("content"),
                    url=link,
                    author=(rec.get("source_id") or None),
                    published_at=_parse_dt(rec.get("pubDate")),
                    thumbnail_url=rec.get("image_url"),
                )
            )
        return items


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        # NewsData returns "YYYY-MM-DD HH:MM:SS" (UTC)
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

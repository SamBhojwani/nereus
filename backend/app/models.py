"""
The single normalized shape that flows through the entire pipeline.

Every source (news, Reddit, YouTube) maps its raw response INTO a ContentItem,
and every later stage (classifier, ranking, the API response, the frontend cards)
consumes ONLY this shape. That decoupling is the whole point: add a new source or
swap the classifier without touching anything downstream.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    NEWS = "news"
    REDDIT = "reddit"
    YOUTUBE = "youtube"


class Stance(str, Enum):
    """Output of the fact-vs-opinion classifier. UNCLASSIFIED until it runs."""
    FACTUAL = "factual"
    OPINION = "opinion"
    UNCLASSIFIED = "unclassified"


class Classification(BaseModel):
    stance: Stance = Stance.UNCLASSIFIED
    confidence: float = 0.0            # 0..1
    rationale: Optional[str] = None    # kept for error analysis + "why" in the UI


class ContentItem(BaseModel):
    # identity
    id: str                            # stable, unique per item (source prefix + native id)
    source_type: SourceType

    # content
    title: Optional[str] = None
    body: Optional[str] = None         # article text / post body / video description
    url: str

    # attribution
    author: Optional[str] = None       # outlet, subreddit, or channel
    author_handle: Optional[str] = None
    published_at: Optional[datetime] = None

    # media (faithful cards use these)
    thumbnail_url: Optional[str] = None
    embed_url: Optional[str] = None    # e.g. YouTube iframe src

    # engagement (render if present, ignore if not)
    likes: Optional[int] = None
    comments: Optional[int] = None

    # AI output — populated by the classifier stage
    classification: Classification = Field(default_factory=Classification)

    def text_for_classification(self) -> str:
        """What the classifier reads. One place to tune later."""
        return "\n\n".join(p for p in (self.title, self.body) if p).strip()

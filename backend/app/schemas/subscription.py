"""Schemas for subscriptions and recommendations."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SubscriptionCreate(BaseModel):
    topic_keywords: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    frequency: str = "daily"  # daily, weekly
    enabled: bool = True


class SubscriptionUpdate(BaseModel):
    topic_keywords: list[str] | None = None
    categories: list[str] | None = None
    frequency: str | None = None
    enabled: bool | None = None


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    topic_keywords: list[str] = []
    categories: list[str] = []
    frequency: str = "daily"
    enabled: bool = True
    created_at: datetime


class DigestPaperItem(BaseModel):
    paper_id: str
    arxiv_id: str
    title: str
    authors: list[str] = []
    abstract: str = ""
    primary_category: str = ""
    published_at: str | None = None
    arxiv_url: str | None = None
    in_library: bool = False


class DigestTopicGroup(BaseModel):
    topic: str
    keywords: list[str] = []
    papers: list[DigestPaperItem] = []


class DailyDigestOut(BaseModel):
    date: str  # "2026-07-14"
    topic_groups: list[DigestTopicGroup] = []


class RecommendationItem(BaseModel):
    paper_id: str
    arxiv_id: str
    arxiv_url: str | None = None
    in_library: bool = False
    title: str
    authors: list[str] = []
    abstract: str = ""
    primary_category: str = ""
    relevance_score: float = 0.0
    reason: str = ""  # "基于你收藏的「xx」论文" / "与你同领域研究者也在读"


class RecommendationFeed(BaseModel):
    history_based: list[RecommendationItem] = []
    content_based: list[RecommendationItem] = []
    collaborative: list[RecommendationItem] = []

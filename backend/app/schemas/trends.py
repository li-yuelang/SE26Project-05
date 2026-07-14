"""Schemas for trend topics."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TrendSignalOut(BaseModel):
    """A trend signal -- name + hotness level."""
    name: str
    hotness: int = 0  # 0-100
    paper_count: int = 0
    month_over_month_change: float = 0.0


class TrendTopicSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    keywords: list[str] = []
    paper_count: int = 0
    hotness: int = 0
    trend_direction: str = "stable"  # rising, stable, declining


class TrendOverview(BaseModel):
    signals: list[TrendSignalOut] = []
    topics: list[TrendTopicSummary] = []


class TrendMonthlyPoint(BaseModel):
    month: str  # "2024-01"
    count: int = 0


class TrendMilestone(BaseModel):
    paper_id: str
    title: str
    published_at: str | None = None
    citation_count: int = 0
    significance: str = ""  # "first_of_kind", "most_cited", "turning_point"


class TrendPhase(BaseModel):
    phase: str  # "emerging", "growing", "mature", "declining"
    start_month: str
    end_month: str
    description: str = ""


class TrendDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    keywords: list[str] = []
    monthly_trend: list[TrendMonthlyPoint] = []
    milestones: list[TrendMilestone] = []
    phases: list[TrendPhase] = []

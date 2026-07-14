"""Schemas for paper comparison."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ComparisonCreate(BaseModel):
    title: str = Field(..., max_length=500)
    paper_ids: list[UUID] = Field(..., min_length=2)


class ComparisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    paper_ids: list[str]
    report_content: str | None = None
    created_at: datetime
    updated_at: datetime

"""Trend analysis API endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession
from app.schemas.common import success
from app.services.trends import trend_service

router = APIRouter(prefix="/trends", tags=["Trends"])


@router.get("", response_model=dict)
async def get_trend_overview(db: DbSession):
    """Get trend overview with signals and topic summaries."""
    result = await trend_service.get_trend_overview(db)
    return success(result)


@router.get("/{topic_id}", response_model=dict)
async def get_trend_detail(topic_id: UUID, db: DbSession):
    """Get detailed trend data for a specific topic, including milestones and phases."""
    try:
        result = await trend_service.get_trend_detail(db, topic_id)
        return success(result)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))

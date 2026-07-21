"""Trend analysis API endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import success
from app.services.trends import trend_service

router = APIRouter(prefix="/trends", tags=["Trends"])


@router.get("", response_model=dict)
async def get_trend_overview(db: DbSession, user: CurrentUser):
    """Get trend overview for the authenticated user's paper library."""
    result = await trend_service.get_trend_overview(db, user.id)
    return success(result)


@router.get("/{topic_id}", response_model=dict)
async def get_trend_detail(topic_id: UUID, db: DbSession, user: CurrentUser):
    """Get trend details calculated only from the authenticated user's papers."""
    try:
        result = await trend_service.get_trend_detail(db, user.id, topic_id)
        return success(result)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))

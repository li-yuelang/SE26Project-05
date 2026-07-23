"""Paper comparison API endpoints."""
from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import success
from app.schemas.compare import ComparisonCreate
from app.services.compare import compare_service

router = APIRouter(prefix="/compare", tags=["Compare"])


@router.get("", response_model=dict)
async def list_comparisons(
    user: CurrentUser, db: DbSession,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
):
    items, total = await compare_service.list_comparisons(db, user, page, page_size)
    return success({"items": items, "total": total, "page": page, "pageSize": page_size})


@router.post("", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_comparison(body: ComparisonCreate, user: CurrentUser, db: DbSession):
    try:
        result = await compare_service.create_comparison(db, user, body.title, body.paper_ids)
        return success(result, "Comparison created")
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/{comparison_id}", response_model=dict)
async def get_comparison(comparison_id: UUID, user: CurrentUser, db: DbSession):
    try:
        result = await compare_service.get_comparison(db, user, comparison_id)
        return success(result)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.delete("/{comparison_id}", response_model=dict)
async def delete_comparison(comparison_id: UUID, user: CurrentUser, db: DbSession):
    try:
        await compare_service.delete_comparison(db, user, comparison_id)
        return success(None, "Comparison deleted")
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.get("/export/{comparison_id}", response_model=dict)
async def export_comparison(comparison_id: UUID, user: CurrentUser, db: DbSession):
    """Generate a rich comparison matrix for export."""
    try:
        result = await compare_service.export_comparison(db, user, comparison_id)
        return success(result)
    except ValueError as e:
        error_msg = str(e)
        try:
            detail = json.loads(error_msg)
            if isinstance(detail, dict) and "unparsed_papers" in detail:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail=detail,
                ) from e
        except (json.JSONDecodeError, TypeError):
            pass
        raise HTTPException(status.HTTP_404_NOT_FOUND, error_msg)

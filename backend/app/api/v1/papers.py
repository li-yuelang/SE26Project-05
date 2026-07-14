"""论文相关 API 路由 — 列表、详情、更新、搜索。"""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import success
from app.schemas.paper import (
    PaperDetail,
    PaperFilterParams,
    PaperListResponse,
    PaperListItem,
    PaperUpdateRequest,
)
from app.services import paper_service

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("")
async def list_papers(
    db: DbSession,
    user: CurrentUser,
    query: str | None = Query(default=None, max_length=500),
    category: str | None = Query(default=None, max_length=100),
    author: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None, max_length=32),
    parsed_status: str | None = Query(default=None, max_length=32),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    params = PaperFilterParams(
        query=query,
        category=category,
        author=author,
        status=status,
        parsed_status=parsed_status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    items, total = await paper_service.list_papers(db, params)
    resp = PaperListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
    return success(resp.model_dump(by_alias=True))


@router.get("/{paper_id}")
async def get_paper_detail(
    paper_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    detail = await paper_service.get_paper_detail(db, paper_id)
    return success(detail.model_dump(mode="json"))


@router.patch("/{paper_id}")
async def update_paper(
    paper_id: UUID,
    body: PaperUpdateRequest,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    detail = await paper_service.update_paper(db, paper_id, body)
    return success(detail.model_dump(mode="json"))

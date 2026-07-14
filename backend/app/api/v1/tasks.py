"""抓取任务相关 API 路由 — 列表、详情、更新、重置。"""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import success
from app.schemas.task import TaskCatalogResponse, TaskUpdateRequest
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(
    db: DbSession,
    user: CurrentUser,
) -> dict:
    items, total = await task_service.list_tasks(db)
    resp = TaskCatalogResponse(tasks=items, total=total)
    return success(resp.model_dump(by_alias=True))


@router.get("/{task_id}")
async def get_task_detail(
    task_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    detail = await task_service.get_task_detail(db, task_id)
    return success(detail.model_dump(mode="json"))


@router.patch("/{task_id}")
async def update_task(
    task_id: UUID,
    body: TaskUpdateRequest,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    detail = await task_service.update_task(db, task_id, body)
    return success(detail.model_dump(mode="json"))


@router.post("/reset")
async def reset_tasks(
    db: DbSession,
    user: CurrentUser,
) -> dict:
    tasks = await task_service.reset_tasks(db)
    return success([t.model_dump(mode="json") for t in tasks])

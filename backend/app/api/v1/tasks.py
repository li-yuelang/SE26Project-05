"""Authenticated fetch-task configuration and execution-history endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import success
from app.schemas.task import TaskCreateRequest, TaskUpdateRequest
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/meta")
async def get_task_meta(_: CurrentUser) -> dict:
    return success(await task_service.task_meta())


@router.get("")
async def list_tasks(
    db: DbSession,
    user: CurrentUser,
    q: str | None = Query(default=None, max_length=200),
    task_type: str | None = Query(default=None, max_length=32),
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    response = await task_service.list_tasks(
        db,
        user.id,
        query_text=q,
        task_type=task_type,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return success(response.model_dump(mode="json"))


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_task(body: TaskCreateRequest, db: DbSession, user: CurrentUser) -> dict:
    detail, run = await task_service.create_task(db, user.id, body)
    payload = detail.model_dump(mode="json")
    payload["run"] = run.model_dump(mode="json") if run else None
    return success(payload, "task created")


@router.get("/{task_id}")
async def get_task_detail(task_id: UUID, db: DbSession, user: CurrentUser) -> dict:
    detail = await task_service.get_task_detail(db, user.id, task_id)
    return success(detail.model_dump(mode="json"))


@router.patch("/{task_id}")
async def update_task(
    task_id: UUID,
    body: TaskUpdateRequest,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    detail = await task_service.update_task(db, user.id, task_id, body)
    return success(detail.model_dump(mode="json"))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, db: DbSession, user: CurrentUser) -> Response:
    await task_service.delete_task(db, user.id, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{task_id}/pause")
async def pause_task(task_id: UUID, db: DbSession, user: CurrentUser) -> dict:
    detail = await task_service.set_task_enabled(db, user.id, task_id, False)
    return success(detail.model_dump(mode="json"), "task paused")


@router.post("/{task_id}/resume")
async def resume_task(task_id: UUID, db: DbSession, user: CurrentUser) -> dict:
    detail = await task_service.set_task_enabled(db, user.id, task_id, True)
    return success(detail.model_dump(mode="json"), "task resumed")


@router.post("/{task_id}/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_task_run(task_id: UUID, db: DbSession, user: CurrentUser) -> dict:
    detail, run = await task_service.create_run(db, user.id, task_id)
    return success(
        {"task": detail.model_dump(mode="json"), "run": run.model_dump(mode="json")},
        "task run queued",
    )


@router.get("/{task_id}/runs")
async def list_task_runs(
    task_id: UUID,
    db: DbSession,
    user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    runs = await task_service.list_runs(db, user.id, task_id, page=page, page_size=page_size)
    return success(runs.model_dump(mode="json"))


@router.get("/{task_id}/runs/{run_id}")
async def get_task_run(task_id: UUID, run_id: UUID, db: DbSession, user: CurrentUser) -> dict:
    run = await task_service.get_run(db, user.id, task_id, run_id)
    return success(run.model_dump(mode="json"))


@router.post("/{task_id}/runs/{run_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_task_run(task_id: UUID, run_id: UUID, db: DbSession, user: CurrentUser) -> dict:
    detail, run = await task_service.retry_run(db, user.id, task_id, run_id)
    return success(
        {"task": detail.model_dump(mode="json"), "run": run.model_dump(mode="json")},
        "task run retry queued",
    )

"""Task configuration, ownership, scheduling and run-history services."""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import String, cast, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.models.task import FetchTask, FetchTaskRun, FetchTaskRunPaper
from app.schemas.task import (
    ARXIV_CATEGORY_OPTIONS,
    KEYWORD_MATCH_MODES,
    LOOKBACK_DAYS,
    SCHEDULE_KINDS,
    TASK_TYPES,
    TIMEZONE,
    FetchTaskResponse,
    FetchTaskRunResponse,
    TaskCatalogResponse,
    TaskConfigRequest,
    TaskCreateRequest,
    TaskDetailResponse,
    TaskRunListResponse,
    TaskRunPaperResponse,
    TaskSummary,
    TaskUpdateRequest,
    validate_task_configuration,
)

logger = logging.getLogger(__name__)
UTC = timezone.utc
SHANGHAI = ZoneInfo(TIMEZONE)

STATUS_META = TaskCatalogResponse.model_fields["status_meta"].default_factory()
TYPE_META = {"category": "分类检索", "keyword": "关键词检索"}


def utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _time_label(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def format_schedule(schedule_kind: str, schedule_time: time | None, weekday: int | None) -> str:
    if schedule_kind == "daily" and schedule_time:
        return f"每天 {_time_label(schedule_time)}"
    if schedule_kind == "weekly" and schedule_time and weekday:
        return f"每周{('一', '二', '三', '四', '五', '六', '日')[weekday - 1]} {_time_label(schedule_time)}"
    return "手动运行"


def calculate_next_run_at(
    schedule_kind: str,
    schedule_time: time | None,
    schedule_weekday: int | None,
    *,
    now: datetime | None = None,
) -> datetime | None:
    """Return the next schedule instant in UTC for the fixed app timezone."""

    if schedule_kind == "manual" or schedule_time is None:
        return None
    current_utc = _as_utc(now or utc_now())
    local_now = current_utc.astimezone(SHANGHAI)
    if schedule_kind == "daily":
        candidate_date = local_now.date()
        candidate = datetime.combine(candidate_date, schedule_time, tzinfo=SHANGHAI)
        if candidate <= local_now:
            candidate += timedelta(days=1)
    elif schedule_kind == "weekly" and schedule_weekday:
        days_ahead = (schedule_weekday - local_now.isoweekday()) % 7
        candidate_date = local_now.date() + timedelta(days=days_ahead)
        candidate = datetime.combine(candidate_date, schedule_time, tzinfo=SHANGHAI)
        if candidate <= local_now:
            candidate += timedelta(days=7)
    else:
        return None
    return candidate.astimezone(UTC)


def task_config_snapshot(task: FetchTask) -> dict[str, Any]:
    return {
        "name": task.name,
        "description": task.description,
        "task_type": task.task_type,
        "keywords": list(task.keywords or []),
        "keyword_match_mode": task.keyword_match_mode,
        "categories": list(task.categories or []),
        "schedule_kind": task.schedule_kind,
        "schedule_time": _time_label(task.schedule_time),
        "schedule_weekday": task.schedule_weekday,
        "timezone": task.timezone,
        "initial_lookback_days": task.initial_lookback_days,
        "max_results": task.max_results,
        "auto_analyze": task.auto_analyze,
    }


def calculate_run_window(
    task: FetchTask,
    *,
    now: datetime | None = None,
    previous_window_end: datetime | None = None,
) -> tuple[datetime, datetime]:
    end = _as_utc(now or utc_now())
    if previous_window_end is not None:
        start = _as_utc(previous_window_end) - timedelta(hours=24)
    elif task.last_success_at is not None:
        start = _as_utc(task.last_success_at) - timedelta(hours=24)
    else:
        start = end - timedelta(days=task.initial_lookback_days)
    return start, end


async def _owned_task(
    db: AsyncSession,
    user_id: UUID,
    task_id: UUID,
    *,
    for_update: bool = False,
) -> FetchTask:
    statement = select(FetchTask).where(FetchTask.id == task_id, FetchTask.creator_id == user_id)
    if for_update:
        statement = statement.with_for_update()
    task = await db.scalar(statement)
    if task is None:
        raise AppError("任务不存在", code="TASK_NOT_FOUND", status_code=404)
    return task


async def _active_run(
    db: AsyncSession, task_id: UUID, *, for_update: bool = False
) -> FetchTaskRun | None:
    statement = (
        select(FetchTaskRun)
        .where(FetchTaskRun.task_id == task_id, FetchTaskRun.status.in_(("queued", "running")))
        .order_by(FetchTaskRun.created_at.desc())
        .limit(1)
    )
    if for_update:
        statement = statement.with_for_update()
    return await db.scalar(statement)


async def _latest_run(db: AsyncSession, task_id: UUID) -> FetchTaskRun | None:
    return await db.scalar(
        select(FetchTaskRun)
        .where(FetchTaskRun.task_id == task_id)
        .order_by(FetchTaskRun.created_at.desc())
        .limit(1)
    )


def derive_task_status(
    task: FetchTask, active_run: FetchTaskRun | None, latest_run: FetchTaskRun | None
) -> str:
    if active_run is not None:
        return active_run.status
    if not task.is_enabled:
        return "paused"
    if latest_run is not None:
        if latest_run.status == "failed":
            return "failed"
        if latest_run.status == "succeeded_with_warnings":
            return "succeeded_with_warnings"
        if latest_run.status == "succeeded" and task.schedule_kind == "manual":
            return "completed"
    return "scheduled"


def _task_response(
    task: FetchTask,
    active_run: FetchTaskRun | None,
    latest_run: FetchTaskRun | None,
) -> FetchTaskResponse:
    status = derive_task_status(task, active_run, latest_run)
    return FetchTaskResponse(
        id=task.id,
        name=task.name,
        description=task.description,
        task_type=task.task_type,
        status=status,
        keywords=list(task.keywords or []),
        keyword_match_mode=task.keyword_match_mode,
        categories=list(task.categories or []),
        schedule_kind=task.schedule_kind,
        schedule_time=task.schedule_time,
        schedule_weekday=task.schedule_weekday,
        timezone=task.timezone,
        is_enabled=task.is_enabled,
        next_run_at=task.next_run_at,
        initial_lookback_days=task.initial_lookback_days,
        max_results=task.max_results,
        auto_analyze=task.auto_analyze,
        last_success_at=task.last_success_at,
        candidate_count=latest_run.candidate_count if latest_run else 0,
        new_count=latest_run.new_count if latest_run else 0,
        duplicate_count=latest_run.duplicate_count if latest_run else 0,
        analysis_queued_count=latest_run.analysis_queued_count if latest_run else 0,
        analysis_enqueue_failed_count=latest_run.analysis_enqueue_failed_count if latest_run else 0,
        page_count=latest_run.page_count if latest_run else 0,
        schedule=format_schedule(task.schedule_kind, task.schedule_time, task.schedule_weekday),
        execution_log=list(latest_run.execution_log or []) if latest_run else [],
        started_at=latest_run.started_at if latest_run else None,
        finished_at=latest_run.finished_at if latest_run else None,
        error_message=latest_run.error_message if latest_run else None,
        active_run_id=active_run.id if active_run else None,
        latest_run_id=latest_run.id if latest_run else None,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _run_paper_response(link: FetchTaskRunPaper) -> TaskRunPaperResponse | None:
    paper = link.paper
    if paper is None:
        return None
    return TaskRunPaperResponse(
        id=link.id,
        paper_id=paper.id,
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        primary_category=paper.primary_category,
        published_at=paper.published_at,
        result_kind=link.result_kind,
        parsed_status=paper.parsed_status,
    )


def run_response(run: FetchTaskRun, *, include_papers: bool = False) -> FetchTaskRunResponse:
    papers = []
    if include_papers:
        papers = [item for link in run.papers if (item := _run_paper_response(link)) is not None]
    return FetchTaskRunResponse(
        id=run.id,
        task_id=run.task_id,
        trigger_kind=run.trigger_kind,
        config_snapshot=dict(run.config_snapshot or {}),
        window_start=run.window_start,
        window_end=run.window_end,
        celery_task_id=run.celery_task_id,
        status=run.status,
        candidate_count=run.candidate_count,
        new_count=run.new_count,
        duplicate_count=run.duplicate_count,
        analysis_queued_count=run.analysis_queued_count,
        analysis_enqueue_failed_count=run.analysis_enqueue_failed_count,
        page_count=run.page_count,
        execution_log=list(run.execution_log or []),
        error_message=run.error_message,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
        papers=papers,
    )


async def _summary_for_tasks(db: AsyncSession, tasks: list[FetchTask]) -> TaskSummary:
    summary = TaskSummary()
    for task in tasks:
        active = await _active_run(db, task.id)
        latest = await _latest_run(db, task.id)
        status = derive_task_status(task, active, latest)
        if status in ("queued", "running"):
            summary.running += 1
        elif status == "scheduled":
            summary.scheduled += 1
        elif status == "failed":
            summary.failed += 1
        if latest:
            summary.candidate_count += latest.candidate_count
            summary.duplicate_count += latest.duplicate_count
        cumulative_new = await db.scalar(
            select(func.coalesce(func.sum(FetchTaskRun.new_count), 0)).where(
                FetchTaskRun.task_id == task.id,
                FetchTaskRun.status.in_(("succeeded", "succeeded_with_warnings")),
            )
        )
        summary.new_papers += int(cumulative_new or 0)
    return summary


async def list_tasks(
    db: AsyncSession,
    user_id: UUID,
    *,
    query_text: str | None = None,
    task_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> TaskCatalogResponse:
    base = select(FetchTask).where(FetchTask.creator_id == user_id)
    if query_text:
        pattern = f"%{query_text.strip()}%"
        base = base.where(
            or_(
                FetchTask.name.ilike(pattern),
                FetchTask.description.ilike(pattern),
                cast(FetchTask.keywords, String).ilike(pattern),
                cast(FetchTask.categories, String).ilike(pattern),
            )
        )
    if task_type:
        base = base.where(FetchTask.task_type == task_type)

    active_exists = exists(
        select(FetchTaskRun.id).where(
            FetchTaskRun.task_id == FetchTask.id,
            FetchTaskRun.status.in_(("queued", "running")),
        )
    )
    latest_status = (
        select(FetchTaskRun.status)
        .where(FetchTaskRun.task_id == FetchTask.id)
        .order_by(FetchTaskRun.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    if status in ("queued", "running"):
        base = base.where(
            exists(
                select(FetchTaskRun.id).where(
                    FetchTaskRun.task_id == FetchTask.id,
                    FetchTaskRun.status == status,
                )
            )
        )
    elif status == "paused":
        base = base.where(FetchTask.is_enabled.is_(False))
    elif status == "failed":
        base = base.where(FetchTask.is_enabled.is_(True), ~active_exists, latest_status == "failed")
    elif status == "succeeded_with_warnings":
        base = base.where(FetchTask.is_enabled.is_(True), ~active_exists, latest_status == status)
    elif status == "completed":
        base = base.where(
            FetchTask.is_enabled.is_(True),
            ~active_exists,
            FetchTask.schedule_kind == "manual",
            latest_status == "succeeded",
        )
    elif status == "scheduled":
        base = base.where(
            FetchTask.is_enabled.is_(True),
            ~active_exists,
            or_(
                latest_status.is_(None),
                (FetchTask.schedule_kind != "manual") & (latest_status == "succeeded"),
            ),
        )

    count = (await db.scalar(select(func.count()).select_from(base.subquery()))) or 0
    rows = (
        await db.execute(
            base.order_by(FetchTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    items = []
    for task in rows:
        items.append(_task_response(task, await _active_run(db, task.id), await _latest_run(db, task.id)))
    all_tasks = list((await db.scalars(select(FetchTask).where(FetchTask.creator_id == user_id))).all())
    return TaskCatalogResponse(
        items=items,
        tasks=items,
        total=count,
        page=page,
        page_size=page_size,
        summary=await _summary_for_tasks(db, all_tasks),
    )


async def task_meta() -> dict[str, Any]:
    return {
        "task_types": [{"value": value, "label": TYPE_META[value]} for value in TASK_TYPES],
        "statuses": STATUS_META,
        "lookback_days": list(LOOKBACK_DAYS),
        "keyword_match_modes": [
            {"value": value, "label": "匹配任一（OR）" if value == "or" else "匹配全部（AND）"}
            for value in KEYWORD_MATCH_MODES
        ],
        "schedule_kinds": [
            {"value": value, "label": {"manual": "手动", "daily": "每日", "weekly": "每周"}[value]}
            for value in SCHEDULE_KINDS
        ],
        "categories": ARXIV_CATEGORY_OPTIONS,
        "timezone": TIMEZONE,
        "max_results": {"min": 10, "max": 200, "default": 50},
    }


def _task_values(payload: TaskConfigRequest | dict[str, Any]) -> dict[str, Any]:
    values = payload.model_dump() if isinstance(payload, BaseModel) else dict(payload)
    values.pop("run_now", None)
    values["keywords"] = list(values.get("keywords") or [])
    values["categories"] = list(values.get("categories") or [])
    return values


def _validate_model_values(values: dict[str, Any]) -> None:
    validate_task_configuration(
        task_type=values["task_type"],
        keywords=values["keywords"],
        categories=values["categories"],
        keyword_match_mode=values["keyword_match_mode"],
        schedule_kind=values["schedule_kind"],
        schedule_time=values.get("schedule_time"),
        schedule_weekday=values.get("schedule_weekday"),
        timezone=values["timezone"],
        initial_lookback_days=values["initial_lookback_days"],
        max_results=values["max_results"],
    )


async def _enqueue_run(db: AsyncSession, run: FetchTaskRun) -> FetchTaskRun:
    from app.tasks.arxiv_fetch_task import run_fetch_task

    try:
        result = run_fetch_task.delay(str(run.id))
        run.celery_task_id = getattr(result, "id", None)
        await db.commit()
        await db.refresh(run)
        return run
    except Exception as exc:
        await db.rollback()
        failed = await db.get(FetchTaskRun, run.id)
        if failed is not None:
            failed.status = "failed"
            failed.error_message = f"无法将抓取运行加入队列: {exc}"[:4000]
            failed.finished_at = utc_now()
            failed.execution_log = [
                *(failed.execution_log or []),
                {"time": utc_now().isoformat(), "level": "error", "content": failed.error_message},
            ]
            await db.commit()
        raise AppError("无法将抓取运行加入队列", code="FETCH_QUEUE_ERROR", status_code=503) from exc


async def create_task(
    db: AsyncSession, user_id: UUID, body: TaskCreateRequest
) -> tuple[TaskDetailResponse, FetchTaskRun | None]:
    values = _task_values(body)
    task = FetchTask(creator_id=user_id, **values)
    if task.schedule_kind != "manual" and task.is_enabled:
        task.next_run_at = calculate_next_run_at(
            task.schedule_kind, task.schedule_time, task.schedule_weekday
        )
    else:
        task.next_run_at = None
    db.add(task)
    try:
        await db.commit()
        await db.refresh(task)
    except IntegrityError as exc:
        await db.rollback()
        raise AppError("任务配置保存失败", code="TASK_CREATE_ERROR", status_code=400) from exc

    run = None
    if body.run_now:
        _, run = await create_run(db, user_id, task.id, trigger_kind="initial")
    return await get_task_detail(db, user_id, task.id), run


async def get_task_detail(db: AsyncSession, user_id: UUID, task_id: UUID) -> TaskDetailResponse:
    task = await _owned_task(db, user_id, task_id)
    active = await _active_run(db, task.id)
    latest = await _latest_run(db, task.id)
    runs = (
        await db.scalars(
            select(FetchTaskRun)
            .where(FetchTaskRun.task_id == task.id)
            .order_by(FetchTaskRun.created_at.desc())
            .limit(10)
        )
    ).all()
    latest_run = latest or (runs[0] if runs else None)
    latest_summary = TaskSummary(
        new_papers=latest_run.new_count if latest_run else 0,
        candidate_count=latest_run.candidate_count if latest_run else 0,
        duplicate_count=latest_run.duplicate_count if latest_run else 0,
        running=1 if active else 0,
    )
    return TaskDetailResponse(
        task=_task_response(task, active, latest),
        summary=latest_summary,
        recent_runs=[run_response(run) for run in runs],
        status_meta=STATUS_META,
        type_meta=TYPE_META,
    )


async def update_task(
    db: AsyncSession, user_id: UUID, task_id: UUID, changes: TaskUpdateRequest
) -> TaskDetailResponse:
    task = await _owned_task(db, user_id, task_id, for_update=True)
    # ``exclude_unset`` preserves explicit nulls, which are required when a
    # daily/weekly schedule is changed back to manual or a description is
    # cleared from the UI.
    data = changes.model_dump(exclude_unset=True)
    legacy_status = data.pop("status", None)
    data.pop("schedule", None)
    if legacy_status is not None:
        data["is_enabled"] = legacy_status not in {"paused", "disabled"}
    if not data:
        return await get_task_detail(db, user_id, task_id)

    merged = task_config_snapshot(task)
    merged.update(data)
    if isinstance(merged.get("schedule_time"), str):
        merged["schedule_time"] = time.fromisoformat(merged["schedule_time"])
    _validate_model_values(merged)
    for key, value in data.items():
        if hasattr(task, key):
            setattr(task, key, value)
    if task.schedule_kind == "manual" or not task.is_enabled:
        task.next_run_at = None
    else:
        task.next_run_at = calculate_next_run_at(
            task.schedule_kind, task.schedule_time, task.schedule_weekday
        )
    await db.commit()
    return await get_task_detail(db, user_id, task_id)


async def delete_task(db: AsyncSession, user_id: UUID, task_id: UUID) -> None:
    task = await _owned_task(db, user_id, task_id, for_update=True)
    active = await _active_run(db, task.id, for_update=True)
    if active is not None:
        raise AppError("任务当前有运行中的执行记录", code="TASK_RUN_ACTIVE", status_code=409)
    await db.delete(task)
    await db.commit()


async def set_task_enabled(
    db: AsyncSession, user_id: UUID, task_id: UUID, enabled: bool
) -> TaskDetailResponse:
    task = await _owned_task(db, user_id, task_id, for_update=True)
    task.is_enabled = enabled
    if not enabled or task.schedule_kind == "manual":
        task.next_run_at = None
    else:
        task.next_run_at = calculate_next_run_at(
            task.schedule_kind, task.schedule_time, task.schedule_weekday
        )
    await db.commit()
    return await get_task_detail(db, user_id, task_id)


def _new_run(task: FetchTask, *, trigger_kind: str, window_start: datetime, window_end: datetime) -> FetchTaskRun:
    return FetchTaskRun(
        task_id=task.id,
        trigger_kind=trigger_kind,
        config_snapshot=task_config_snapshot(task),
        window_start=window_start,
        window_end=window_end,
        status="queued",
        execution_log=[
            {"time": utc_now().isoformat(), "level": "info", "content": "运行已排队。"}
        ],
    )


async def create_run(
    db: AsyncSession,
    user_id: UUID,
    task_id: UUID,
    *,
    trigger_kind: str = "manual",
    config_snapshot: dict[str, Any] | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> tuple[TaskDetailResponse, FetchTaskRun]:
    task = await _owned_task(db, user_id, task_id, for_update=True)
    active = await _active_run(db, task.id, for_update=True)
    if active is not None:
        raise AppError("任务已有排队或运行中的执行记录", code="TASK_RUN_ACTIVE", status_code=409)
    start, end = calculate_run_window(task)
    run = _new_run(task, trigger_kind=trigger_kind, window_start=window_start or start, window_end=window_end or end)
    if config_snapshot is not None:
        run.config_snapshot = config_snapshot
    db.add(run)
    try:
        await db.commit()
        await db.refresh(run)
    except IntegrityError as exc:
        await db.rollback()
        raise AppError("任务已有排队或运行中的执行记录", code="TASK_RUN_ACTIVE", status_code=409) from exc
    await _enqueue_run(db, run)
    return await get_task_detail(db, user_id, task_id), run


async def list_runs(
    db: AsyncSession,
    user_id: UUID,
    task_id: UUID,
    *,
    page: int = 1,
    page_size: int = 20,
) -> TaskRunListResponse:
    await _owned_task(db, user_id, task_id)
    base = select(FetchTaskRun).where(FetchTaskRun.task_id == task_id)
    total = (await db.scalar(select(func.count()).select_from(base.subquery()))) or 0
    runs = (
        await db.scalars(
            base.order_by(FetchTaskRun.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return TaskRunListResponse(
        items=[run_response(run) for run in runs], total=total, page=page, page_size=page_size
    )


async def get_run(
    db: AsyncSession, user_id: UUID, task_id: UUID, run_id: UUID
) -> FetchTaskRunResponse:
    await _owned_task(db, user_id, task_id)
    run = await db.scalar(
        select(FetchTaskRun)
        .options(selectinload(FetchTaskRun.papers).selectinload(FetchTaskRunPaper.paper))
        .where(FetchTaskRun.id == run_id, FetchTaskRun.task_id == task_id)
    )
    if run is None:
        raise AppError("运行记录不存在", code="TASK_RUN_NOT_FOUND", status_code=404)
    return run_response(run, include_papers=True)


async def retry_run(
    db: AsyncSession, user_id: UUID, task_id: UUID, run_id: UUID
) -> tuple[TaskDetailResponse, FetchTaskRun]:
    await _owned_task(db, user_id, task_id, for_update=True)
    old_run = await db.scalar(
        select(FetchTaskRun).where(FetchTaskRun.id == run_id, FetchTaskRun.task_id == task_id)
    )
    if old_run is None:
        raise AppError("运行记录不存在", code="TASK_RUN_NOT_FOUND", status_code=404)
    if old_run.status not in {"failed", "succeeded_with_warnings"}:
        raise AppError("只有失败或带警告的运行可以重试", code="TASK_RUN_NOT_RETRYABLE", status_code=409)
    return await create_run(
        db,
        user_id,
        task_id,
        trigger_kind="retry",
        config_snapshot=dict(old_run.config_snapshot or {}),
        window_start=old_run.window_start,
        window_end=old_run.window_end,
    )


async def mark_run_failed(
    run_id: UUID, message: str, *, log_level: str = "error"
) -> None:
    """Best-effort state update used when queue submission fails outside a request."""

    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        run = await db.get(FetchTaskRun, run_id)
        if run is None:
            return
        run.status = "failed"
        run.error_message = message[:4000]
        run.finished_at = utc_now()
        run.execution_log = [
            *(run.execution_log or []),
            {"time": utc_now().isoformat(), "level": log_level, "content": message[:4000]},
        ]
        await db.commit()


__all__ = [
    "calculate_next_run_at",
    "calculate_run_window",
    "create_run",
    "create_task",
    "delete_task",
    "derive_task_status",
    "get_run",
    "get_task_detail",
    "list_runs",
    "list_tasks",
    "mark_run_failed",
    "retry_run",
    "run_response",
    "set_task_enabled",
    "task_config_snapshot",
    "task_meta",
    "update_task",
    "utc_now",
]

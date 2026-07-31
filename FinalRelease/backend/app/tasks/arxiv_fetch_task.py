"""Celery worker and beat-dispatcher tasks for arXiv fetch runs."""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any
from uuid import UUID

# Windows Python 3.13 defaults to ProactorEventLoop which crashes asyncpg.
# Celery workers don't go through main.py, so set the policy here.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import CelerySessionLocal
from app.models.paper import Paper, UserPaper
from app.models.task import FetchTask, FetchTaskRun, FetchTaskRunPaper
from app.services.arxiv_fetch import ArxivFetchError, build_search_query, fetch_arxiv_window
from app.services.analysis_runs import create_analysis_run
from app.services.task_service import (
    calculate_next_run_at,
    calculate_run_window,
    task_config_snapshot,
    utc_now,
)
from app.tasks.celery_app import celery_app
from app.tasks.async_utils import run_async

logger = logging.getLogger(__name__)

def _append_log(run: FetchTaskRun, level: str, content: str) -> None:
    run.execution_log = [
        *(run.execution_log or []),
        {"time": utc_now().isoformat(), "level": level, "content": content},
    ]


def _query_from_snapshot(snapshot: dict[str, Any]) -> str:
    return build_search_query(
        keywords=snapshot.get("keywords") or [],
        categories=snapshot.get("categories") or [],
        keyword_match_mode=snapshot.get("keyword_match_mode", "or"),
    )


def _sync_arxiv_source_dates(paper: Paper, candidate: dict[str, Any]) -> bool:
    """Refresh source-owned dates without ever substituting the fetch time."""

    changed = False
    published_at = candidate.get("published_at")
    if published_at is not None and paper.published_at != published_at:
        paper.published_at = published_at
        changed = True

    updated_at_source = candidate.get("updated_at_source")
    if updated_at_source is not None and paper.updated_at_source != updated_at_source:
        paper.updated_at_source = updated_at_source
        changed = True

    return changed


async def _set_run_retry_pending(run_id: UUID, message: str) -> None:
    async with CelerySessionLocal() as db:
        run = await db.get(FetchTaskRun, run_id)
        if run is None:
            return
        run.status = "queued"
        run.error_message = message[:4000]
        _append_log(run, "warning", message[:4000])
        await db.commit()


async def _set_run_failed(run_id: UUID, message: str) -> None:
    async with CelerySessionLocal() as db:
        run = await db.get(FetchTaskRun, run_id)
        if run is None:
            return
        run.status = "failed"
        run.error_message = message[:4000]
        run.finished_at = utc_now()
        _append_log(run, "error", message[:4000])
        await db.commit()


async def _mark_run_running(run_id: UUID) -> tuple[FetchTaskRun, FetchTask] | None:
    async with CelerySessionLocal() as db:
        row = await db.execute(
            select(FetchTaskRun, FetchTask)
            .join(FetchTask, FetchTask.id == FetchTaskRun.task_id)
            .where(FetchTaskRun.id == run_id)
            .with_for_update()
        )
        item = row.one_or_none()
        if item is None:
            return None
        run, task = item
        if run.status != "queued":
            return None
        run.status = "running"
        run.started_at = utc_now()
        _append_log(run, "info", "开始执行 arXiv 抓取。")
        await db.commit()
        # The objects are detached after the session closes; callers only use
        # their scalar values and reload the run before persistence.
        return run, task


async def _persist_candidates(
    run_id: UUID, candidates: list[dict[str, Any]], page_count: int
) -> tuple[list[UUID], int, int, int]:
    """Persist papers and run links atomically in one database transaction."""

    async with CelerySessionLocal() as db:
        run = await db.get(FetchTaskRun, run_id, with_for_update=True)
        if run is None:
            raise ValueError(f"FetchTaskRun not found: {run_id}")

        unique_candidates: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for candidate in candidates:
            arxiv_id = str(candidate.get("arxiv_id", "")).strip()
            if not arxiv_id or arxiv_id in seen_ids:
                continue
            seen_ids.add(arxiv_id)
            unique_candidates.append(candidate)

        candidate_ids = [candidate["arxiv_id"] for candidate in unique_candidates]
        owner_id = (
            await db.scalar(select(FetchTask.creator_id).where(FetchTask.id == run.task_id))
        )
        if owner_id is None:
            raise ValueError(f"FetchTask owner not found: {run.task_id}")

        existing_ids: set[str] = set()
        if candidate_ids:
            existing_ids = set(
                (
                    await db.scalars(
                        select(Paper.arxiv_id).where(Paper.arxiv_id.in_(candidate_ids))
                    )
                ).all()
            )

        to_insert = [candidate for candidate in unique_candidates if candidate["arxiv_id"] not in existing_ids]
        inserted_ids: set[str] = set()
        if to_insert:
            values = [
                {
                    "arxiv_id": candidate["arxiv_id"],
                    "title": candidate.get("title") or candidate["arxiv_id"],
                    "authors": candidate.get("authors") or [],
                    "abstract": candidate.get("abstract") or "",
                    "categories": candidate.get("categories") or [],
                    "primary_category": candidate.get("primary_category"),
                    "published_at": candidate.get("published_at"),
                    "updated_at_source": candidate.get("updated_at_source"),
                    "pdf_url": candidate.get("pdf_url") or "",
                    "arxiv_url": candidate.get("arxiv_url") or "",
                    "parsed_status": "pending",
                    "metadata_extra": candidate.get("metadata_extra"),
                }
                for candidate in to_insert
            ]
            dialect_name = db.get_bind().dialect.name
            if dialect_name == "postgresql":
                statement = (
                    pg_insert(Paper)
                    .values(values)
                    .on_conflict_do_nothing(index_elements=[Paper.arxiv_id])
                    .returning(Paper.arxiv_id)
                )
                inserted_ids = set((await db.scalars(statement)).all())
            else:
                # This branch keeps service-level tests usable with a small
                # non-Postgres test database; production uses the atomic PG
                # upsert above.
                for value in values:
                    duplicate = await db.scalar(
                        select(Paper).where(Paper.arxiv_id == value["arxiv_id"])
                    )
                    if duplicate is None:
                        db.add(Paper(**value))
                        inserted_ids.add(value["arxiv_id"])
                await db.flush()

        paper_rows = {}
        if candidate_ids:
            paper_rows = {
                paper.arxiv_id: paper
                for paper in (
                    await db.scalars(
                        select(Paper).where(Paper.arxiv_id.in_(candidate_ids))
                    )
                ).all()
            }
        for candidate in unique_candidates:
            paper = paper_rows.get(candidate["arxiv_id"])
            if paper is None:
                continue
            # A duplicate may have been inserted by an older version that used
            # its fetch timestamp as ``published_at``. Re-reading the same
            # arXiv entry must repair that value from Atom source metadata.
            _sync_arxiv_source_dates(paper, candidate)
            if db.get_bind().dialect.name == "postgresql":
                await db.execute(
                    pg_insert(UserPaper)
                    .values(user_id=owner_id, paper_id=paper.id)
                    .on_conflict_do_nothing(index_elements=[UserPaper.user_id, UserPaper.paper_id])
                )
            else:
                linked = await db.scalar(
                    select(UserPaper.id).where(UserPaper.user_id == owner_id, UserPaper.paper_id == paper.id)
                )
                if linked is None:
                    db.add(UserPaper(user_id=owner_id, paper_id=paper.id))
            db.add(
                FetchTaskRunPaper(
                    run_id=run.id,
                    paper_id=paper.id,
                    result_kind="inserted" if candidate["arxiv_id"] in inserted_ids else "duplicate",
                )
            )

        inserted_count = len(inserted_ids)
        duplicate_count = max(0, len(candidates) - inserted_count)
        run.candidate_count = len(candidates)
        run.new_count = inserted_count
        run.duplicate_count = duplicate_count
        run.page_count = page_count
        await db.flush()
        await db.commit()
        return [paper_rows[arxiv_id].id for arxiv_id in inserted_ids if arxiv_id in paper_rows], inserted_count, duplicate_count, len(candidates)


async def _enqueue_analysis(paper_ids: list[UUID]) -> tuple[int, int]:
    if not paper_ids:
        return 0, 0

    queued = 0
    failed = 0
    for paper_id in paper_ids:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                async with CelerySessionLocal() as db:
                    _, created = await create_analysis_run(db, paper_id, force=False)
                    await db.commit()
                if created:
                    queued += 1
                last_error = None
                break
            except Exception as exc:  # pragma: no cover - broker-dependent
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.2 * (attempt + 1))
        if last_error is not None:
            failed += 1
            logger.warning("unable to enqueue analysis for %s: %s", paper_id, last_error)
    return queued, failed


async def _execute_run(run_id: UUID) -> dict[str, Any]:
    marked = await _mark_run_running(run_id)
    if marked is None:
        return {"status": "skipped", "run_id": str(run_id), "reason": "run is not queued"}
    _, task = marked

    async with CelerySessionLocal() as db:
        run = await db.get(FetchTaskRun, run_id)
        if run is None:
            raise ValueError(f"FetchTaskRun not found: {run_id}")
        snapshot = dict(run.config_snapshot or {})
        window_start = run.window_start
        window_end = run.window_end
    if window_start is None or window_end is None:
        window_start, window_end = calculate_run_window(task)

    candidates, page_count = await fetch_arxiv_window(
        _query_from_snapshot(snapshot),
        window_start=window_start,
        window_end=window_end,
        max_results=int(snapshot.get("max_results", task.max_results)),
    )
    paper_ids, inserted_count, duplicate_count, candidate_count = await _persist_candidates(
        run_id, candidates, page_count
    )

    if bool(snapshot.get("auto_analyze", task.auto_analyze)):
        analysis_queued, analysis_failed = await _enqueue_analysis(paper_ids)
    else:
        analysis_queued, analysis_failed = 0, 0

    async with CelerySessionLocal() as db:
        run = await db.get(FetchTaskRun, run_id, with_for_update=True)
        task = await db.get(FetchTask, run.task_id) if run else None
        if run is None or task is None:
            raise ValueError(f"FetchTaskRun not found: {run_id}")
        run.analysis_queued_count = analysis_queued
        run.analysis_enqueue_failed_count = analysis_failed
        run.status = "succeeded_with_warnings" if analysis_failed else "succeeded"
        run.finished_at = utc_now()
        if analysis_failed:
            _append_log(run, "warning", f"{analysis_failed} 篇新增论文未能加入解析队列。")
        _append_log(
            run,
            "success" if not analysis_failed else "warning",
            f"抓取完成：候选 {candidate_count}，新增 {inserted_count}，重复 {duplicate_count}。",
        )
        task.last_success_at = run.window_end
        if task.is_enabled and task.schedule_kind != "manual":
            task.next_run_at = calculate_next_run_at(
                task.schedule_kind, task.schedule_time, task.schedule_weekday, now=utc_now()
            )
        else:
            task.next_run_at = None if not task.is_enabled else task.next_run_at
        await db.commit()
    return {
        "status": "succeeded_with_warnings" if analysis_failed else "succeeded",
        "run_id": str(run_id),
        "candidate_count": candidate_count,
        "new_count": inserted_count,
        "duplicate_count": duplicate_count,
        "analysis_queued_count": analysis_queued,
        "analysis_enqueue_failed_count": analysis_failed,
        "page_count": page_count,
    }


@celery_app.task(
    bind=True,
    name="app.tasks.run_fetch_task",
    max_retries=settings.arxiv_max_retries,
    acks_late=True,
    track_started=True,
    queue="arxiv",
)
def run_fetch_task(self: Any, run_id: str) -> dict[str, Any]:
    """Execute one immutable fetch run snapshot."""

    run_uuid = UUID(run_id)
    try:
        return run_async(_execute_run(run_uuid))
    except ArxivFetchError as exc:
        retry_number = int(getattr(self.request, "retries", 0)) + 1
        if exc.retryable and retry_number <= self.max_retries:
            run_async(_set_run_retry_pending(run_uuid, str(exc)))
            raise self.retry(exc=exc, countdown=min(900, 30 * (2 ** (retry_number - 1))))
        run_async(_set_run_failed(run_uuid, str(exc)))
        raise
    except Exception as exc:
        run_async(_set_run_failed(run_uuid, str(exc)))
        raise


async def _dispatch_due_runs() -> int:
    dispatched = 0
    now = utc_now()
    async with CelerySessionLocal() as db:
        tasks = (
            await db.scalars(
                select(FetchTask)
                .where(
                    FetchTask.is_enabled.is_(True),
                    FetchTask.schedule_kind.in_(("daily", "weekly")),
                    (FetchTask.next_run_at <= now) | FetchTask.next_run_at.is_(None),
                )
                .order_by(FetchTask.next_run_at.asc().nullsfirst())
                .with_for_update(skip_locked=True)
            )
        ).all()
        for task in tasks:
            if task.next_run_at is None:
                task.next_run_at = calculate_next_run_at(
                    task.schedule_kind, task.schedule_time, task.schedule_weekday, now=now
                )
                continue
            active = await db.scalar(
                select(FetchTaskRun.id).where(
                    FetchTaskRun.task_id == task.id,
                    FetchTaskRun.status.in_(("queued", "running")),
                )
            )
            if active is not None:
                task.next_run_at = calculate_next_run_at(
                    task.schedule_kind, task.schedule_time, task.schedule_weekday, now=now
                )
                continue
            start, end = calculate_run_window(task, now=now)
            run = FetchTaskRun(
                task_id=task.id,
                trigger_kind="scheduled",
                config_snapshot=task_config_snapshot(task),
                window_start=start,
                window_end=end,
                status="queued",
                execution_log=[
                    {"time": now.isoformat(), "level": "info", "content": "定时运行已排队。"}
                ],
            )
            db.add(run)
            task.next_run_at = calculate_next_run_at(
                task.schedule_kind, task.schedule_time, task.schedule_weekday, now=now
            )
            try:
                await db.flush()
            except IntegrityError:
                await db.rollback()
                logger.info("skipped duplicate scheduled run for task %s", task.id)
                continue
            await db.commit()
            try:
                result = run_fetch_task.delay(str(run.id))
                run.celery_task_id = getattr(result, "id", None)
                await db.commit()
            except Exception as exc:  # pragma: no cover - broker-dependent
                await db.rollback()
                await _set_run_failed(run.id, f"无法将定时运行加入队列: {exc}")
            dispatched += 1
    return dispatched


@celery_app.task(name="app.tasks.dispatch_due_fetch_runs", queue="arxiv")
def dispatch_due_fetch_runs() -> int:
    return run_async(_dispatch_due_runs())


__all__ = ["dispatch_due_fetch_runs", "run_fetch_task"]

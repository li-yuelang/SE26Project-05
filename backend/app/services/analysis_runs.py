"""Durable paper-analysis runs and the PostgreSQL transactional outbox.

PostgreSQL owns the lifecycle in this module.  Celery/Redis only receives an
idempotent notification after the run and outbox row have committed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.models.paper import (
    ACTIVE_ANALYSIS_RUN_STATUSES,
    Paper,
    PaperAnalysisRun,
)
from app.models.task import TaskOutbox
from app.services.analysis_state import get_analysis_metadata

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def deterministic_task_id(run_id: UUID) -> str:
    """Return the stable Celery id used for every delivery of one outbox event."""

    return f"paper-analysis-{run_id}"


def _compat_metadata(
    paper: Paper,
    run: PaperAnalysisRun,
    *,
    status: str | None = None,
    stage: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    previous = get_analysis_metadata(paper)
    now = utc_now().isoformat()
    analysis = {
        **previous,
        "status": status or run.status,
        "stage": stage or run.stage,
        "task_id": run.celery_task_id,
        "analysis_version": run.analysis_version,
        "model": run.llm_model,
        "embedding_model": run.embedding_model,
        "prompt_version": run.prompt_version,
        "updated_at": now,
        "error_code": error_code if error_code is not None else run.error_code,
        "error": error_message if error_message is not None else run.error_message,
    }
    if run.started_at is not None:
        analysis["started_at"] = run.started_at.isoformat()
    if run.finished_at is not None:
        analysis["finished_at"] = run.finished_at.isoformat()
        if run.status == "completed":
            analysis["completed_at"] = run.finished_at.isoformat()
        if run.status == "failed":
            analysis["failed_at"] = run.finished_at.isoformat()
    paper.metadata_extra = {**(paper.metadata_extra or {}), "analysis": analysis}


def _run_payload(run: PaperAnalysisRun, paper_id: UUID) -> dict[str, Any]:
    return {
        "paper_id": str(paper_id),
        "run_id": str(run.id),
        "force": run.force,
        "task_id": run.celery_task_id,
    }


async def _load_paper_for_update(db: AsyncSession, paper_id: UUID) -> Paper:
    paper = await db.scalar(select(Paper).where(Paper.id == paper_id).with_for_update())
    if paper is None:
        raise LookupError(f"Paper {paper_id} does not exist")
    return paper


async def create_analysis_run(
    db: AsyncSession,
    paper_id: UUID,
    *,
    force: bool = False,
    requested_by: UUID | None = None,
    config: Settings = settings,
    celery_task_id: str | None = None,
    create_outbox: bool = True,
    attempt: int = 0,
) -> tuple[PaperAnalysisRun, bool]:
    """Create one queued run, or return the existing active/completed run.

    The caller owns the transaction.  Locking the paper row serialises the
    common double-click path; the partial unique index remains the final
    protection when multiple API instances race.
    """

    paper = await _load_paper_for_update(db, paper_id)
    active = await db.scalar(
        select(PaperAnalysisRun)
        .where(
            PaperAnalysisRun.paper_id == paper_id,
            PaperAnalysisRun.status.in_(ACTIVE_ANALYSIS_RUN_STATUSES),
        )
        .order_by(PaperAnalysisRun.created_at.desc())
        .limit(1)
    )
    if active is not None:
        return active, False

    if not force and paper.active_analysis_run_id is not None:
        completed = await db.get(PaperAnalysisRun, paper.active_analysis_run_id)
        latest = await db.scalar(
            select(PaperAnalysisRun)
            .where(PaperAnalysisRun.paper_id == paper_id)
            .order_by(PaperAnalysisRun.created_at.desc())
            .limit(1)
        )
        if (
            completed is not None
            and completed.status == "completed"
            and (latest is None or latest.status == "completed")
        ):
            return completed, False

    run_id = uuid4()
    run = PaperAnalysisRun(
        id=run_id,
        paper_id=paper_id,
        celery_task_id=celery_task_id or deterministic_task_id(run_id),
        status="queued",
        stage="queued",
        attempt=attempt,
        force=force,
        pipeline_version=config.analysis_version,
        analysis_version=f"{config.analysis_version}-{run_id.hex[:12]}",
        parser_version=config.analysis_parser_version,
        prompt_version=config.analysis_prompt_version,
        llm_model=config.llm_model,
        embedding_model=config.embedding_model,
        requested_by=requested_by,
        queued_at=utc_now(),
    )
    db.add(run)
    # TaskOutbox keeps the run id as a scalar FK for a lightweight model.
    # Flush the parent explicitly so SQLAlchemy cannot order the child insert
    # before paper_analysis_runs when no ORM relationship is configured.
    await db.flush()
    if create_outbox:
        db.add(
            TaskOutbox(
                id=uuid4(),
                event_key=f"paper-analysis-run:{run_id}",
                event_type="paper.analysis.dispatch",
                aggregate_type="paper_analysis_run",
                aggregate_id=run_id,
                analysis_run_id=run_id,
                task_id=run.celery_task_id,
                payload=_run_payload(run, paper_id),
                status="pending",
                available_at=utc_now(),
            )
        )
    paper.parsed_status = "processing"
    _compat_metadata(paper, run, status="processing", stage="queued", error_code=None, error_message=None)
    await db.flush()
    return run, True


async def get_current_analysis_run(
    db: AsyncSession, paper_id: UUID, *, with_for_update: bool = False
) -> PaperAnalysisRun | None:
    """Return the newest active run, then the paper's successful active run."""

    if not hasattr(db, "add"):
        return None

    statement = (
        select(PaperAnalysisRun)
        .where(
            PaperAnalysisRun.paper_id == paper_id,
            PaperAnalysisRun.status.in_(ACTIVE_ANALYSIS_RUN_STATUSES),
        )
        .order_by(PaperAnalysisRun.created_at.desc())
        .limit(1)
    )
    if with_for_update:
        statement = statement.with_for_update()
    run = await db.scalar(statement)
    if run is not None:
        return run
    paper = await db.get(Paper, paper_id)
    if paper is None:
        return None
    latest = await db.scalar(
        select(PaperAnalysisRun)
        .where(PaperAnalysisRun.paper_id == paper_id)
        .order_by(PaperAnalysisRun.created_at.desc())
        .limit(1)
    )
    if latest is not None and latest.status in {"failed", "cancelled"}:
        return latest
    if paper.active_analysis_run_id is None:
        return latest
    return await db.get(PaperAnalysisRun, paper.active_analysis_run_id)


async def claim_analysis_run(
    db: AsyncSession,
    run_id: UUID,
    *,
    task_id: str | None = None,
) -> PaperAnalysisRun | None:
    """Atomically move a queued/retry run into its current pipeline stage."""

    run = await db.get(PaperAnalysisRun, run_id, with_for_update=True)
    if run is None or run.status not in {"queued", "retry_wait"}:
        # Celery can redeliver a task after a broker/worker failure.  A run
        # already in a pipeline stage is owned by the first delivery; only a
        # retry_wait run may be claimed again.
        return None
    if task_id and run.celery_task_id and task_id != run.celery_task_id:
        return None

    stage = run.stage if run.status == "retry_wait" else (run.stage or "downloading")
    if stage in {"queued", "completed", "failed"}:
        stage = "downloading"
    run.status = stage
    run.stage = stage
    run.attempt = max(1, run.attempt + 1)
    run.started_at = run.started_at or utc_now()
    run.heartbeat_at = utc_now()
    run.retry_after_at = None
    run.error_code = None
    run.error_message = None
    paper = await db.get(Paper, run.paper_id, with_for_update=True)
    if paper is not None:
        paper.parsed_status = "processing"
        _compat_metadata(paper, run, status="processing", stage=stage)
    await db.flush()
    return run


async def set_analysis_stage(
    db: AsyncSession,
    run_id: UUID,
    stage: str,
    *,
    commit: bool = True,
) -> PaperAnalysisRun:
    if stage not in {"downloading", "parsing", "chunking", "extracting", "embedding", "persisting"}:
        raise ValueError(f"Unsupported analysis stage: {stage}")
    run = await db.get(PaperAnalysisRun, run_id, with_for_update=True)
    if run is None:
        raise LookupError(f"Analysis run {run_id} does not exist")
    if run.status in {"completed", "failed", "cancelled"}:
        raise RuntimeError(f"Analysis run {run_id} is already {run.status}")
    run.status = stage
    run.stage = stage
    run.heartbeat_at = utc_now()
    paper = await db.get(Paper, run.paper_id)
    if paper is not None:
        paper.parsed_status = "processing"
        _compat_metadata(paper, run, status="processing", stage=stage)
    if commit:
        await db.commit()
        await db.refresh(run)
    return run


async def heartbeat_analysis_run(run_id: UUID) -> bool:
    """Write a heartbeat without holding a transaction over external calls."""

    async with _session_factory() as db:
        result = await db.execute(
            update(PaperAnalysisRun)
            .where(
                PaperAnalysisRun.id == run_id,
                PaperAnalysisRun.status.in_(ACTIVE_ANALYSIS_RUN_STATUSES),
            )
            .values(heartbeat_at=utc_now())
        )
        await db.commit()
        return bool(result.rowcount)


async def mark_analysis_retry_wait(
    db: AsyncSession,
    run_id: UUID,
    *,
    stage: str,
    error_code: str,
    error_message: str,
    retry_after_seconds: int,
    attempt: int,
    commit: bool = True,
) -> PaperAnalysisRun:
    run = await db.get(PaperAnalysisRun, run_id, with_for_update=True)
    if run is None:
        raise LookupError(f"Analysis run {run_id} does not exist")
    run.status = "retry_wait"
    run.stage = stage
    run.attempt = max(run.attempt, attempt)
    run.error_code = error_code
    run.error_message = error_message[:4000]
    run.retry_after_at = utc_now() + timedelta(seconds=retry_after_seconds)
    run.heartbeat_at = utc_now()
    paper = await db.get(Paper, run.paper_id)
    if paper is not None:
        paper.parsed_status = "processing"
        _compat_metadata(
            paper,
            run,
            status="processing",
            stage="retry_wait",
            error_code=error_code,
            error_message=error_message[:4000],
        )
    if commit:
        await db.commit()
    return run


async def mark_analysis_failed(
    db: AsyncSession,
    run_id: UUID,
    *,
    error_code: str,
    error_message: str,
    commit: bool = True,
) -> PaperAnalysisRun:
    run = await db.get(PaperAnalysisRun, run_id, with_for_update=True)
    if run is None:
        raise LookupError(f"Analysis run {run_id} does not exist")
    run.status = "failed"
    run.stage = "failed"
    run.error_code = error_code
    run.error_message = error_message[:4000]
    run.finished_at = utc_now()
    run.heartbeat_at = run.finished_at
    paper = await db.get(Paper, run.paper_id, with_for_update=True)
    if paper is not None:
        successful = await db.scalar(
            select(PaperAnalysisRun)
            .where(
                PaperAnalysisRun.paper_id == run.paper_id,
                PaperAnalysisRun.status == "completed",
                PaperAnalysisRun.id != run.id,
            )
            .order_by(PaperAnalysisRun.finished_at.desc().nullslast())
            .limit(1)
        )
        if successful is not None:
            paper.active_analysis_run_id = successful.id
            paper.parsed_status = "completed"
            _compat_metadata(paper, successful, status="completed", stage="completed")
            analysis = get_analysis_metadata(paper)
            analysis.update(
                {
                    "last_error_code": error_code,
                    "last_error": error_message[:4000],
                    "last_failed_run_id": str(run.id),
                    "last_failed_at": run.finished_at.isoformat(),
                }
            )
            paper.metadata_extra = {**(paper.metadata_extra or {}), "analysis": analysis}
        else:
            paper.active_analysis_run_id = None
            paper.parsed_status = "failed"
            _compat_metadata(
                paper,
                run,
                status="failed",
                stage="failed",
                error_code=error_code,
                error_message=error_message[:4000],
            )
    if commit:
        await db.commit()
    return run


async def mark_analysis_completed(
    db: AsyncSession,
    run_id: UUID,
    *,
    analysis_version: str,
    commit: bool = True,
) -> PaperAnalysisRun:
    run = await db.get(PaperAnalysisRun, run_id, with_for_update=True)
    if run is None:
        raise LookupError(f"Analysis run {run_id} does not exist")
    if run.status in {"failed", "cancelled"}:
        raise RuntimeError(f"Analysis run {run_id} is already {run.status}")
    run.status = "completed"
    run.stage = "completed"
    run.analysis_version = analysis_version
    run.finished_at = utc_now()
    run.heartbeat_at = run.finished_at
    run.error_code = None
    run.error_message = None
    paper = await db.get(Paper, run.paper_id, with_for_update=True)
    if paper is not None:
        # This is the only place where a successful version becomes visible.
        paper.active_analysis_run_id = run.id
        paper.parsed_status = "completed"
        _compat_metadata(paper, run, status="completed", stage="completed")
    if commit:
        await db.commit()
    return run


def _session_factory():
    # Imported lazily to avoid importing the engine while settings are being
    # constructed and to keep unit tests free to replace AsyncSessionLocal.
    from app.database import AsyncSessionLocal

    return AsyncSessionLocal()


async def dispatch_pending_outbox(
    *,
    config: Settings = settings,
    limit: int | None = None,
) -> dict[str, int]:
    """Claim and deliver committed outbox events with a stable Celery id."""

    from app.tasks.paper_tasks import process_paper

    batch_size = max(1, limit or config.analysis_outbox_batch_size)
    now = utc_now()
    claimed: list[dict[str, Any]] = []
    async with _session_factory() as db:
        lease_cutoff = now - timedelta(seconds=config.analysis_outbox_lease_seconds)
        await db.execute(
            update(TaskOutbox)
            .where(TaskOutbox.status == "sending", TaskOutbox.locked_at < lease_cutoff)
            .values(status="pending", locked_at=None)
        )
        events = (
            await db.scalars(
                select(TaskOutbox)
                .where(
                    TaskOutbox.status.in_(("pending", "failed")),
                    TaskOutbox.available_at <= now,
                )
                .order_by(TaskOutbox.available_at.asc(), TaskOutbox.created_at.asc())
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        ).all()
        for event in events:
            event.status = "sending"
            event.locked_at = now
            event.attempts += 1
            claimed.append(
                {
                    "id": event.id,
                    "paper_id": event.payload.get("paper_id"),
                    "run_id": event.payload.get("run_id"),
                    "force": bool(event.payload.get("force", False)),
                    "task_id": event.task_id,
                }
            )
        await db.commit()

    sent = 0
    failed = 0
    for item in claimed:
        try:
            process_paper.apply_async(
                args=[item["paper_id"]],
                kwargs={"run_id": item["run_id"], "force": item["force"]},
                task_id=item["task_id"],
                queue=config.analysis_queue,
            )
        except Exception as exc:  # pragma: no cover - broker/network dependent
            failed += 1
            async with _session_factory() as db:
                event = await db.get(TaskOutbox, item["id"], with_for_update=True)
                if event is not None:
                    event.status = "failed"
                    event.locked_at = None
                    event.last_error = str(exc)[:4000]
                    event.available_at = utc_now() + timedelta(
                        seconds=min(900, 2 ** min(event.attempts, 8))
                    )
                    await db.commit()
            continue
        sent += 1
        async with _session_factory() as db:
            event = await db.get(TaskOutbox, item["id"], with_for_update=True)
            if event is not None:
                event.status = "sent"
                event.locked_at = None
                event.sent_at = utc_now()
                event.last_error = None
                await db.commit()
    return {"claimed": len(claimed), "sent": sent, "failed": failed}


async def recover_stale_analysis_runs(
    *,
    config: Settings = settings,
) -> dict[str, int]:
    """Turn heartbeat-expired workers into auditable failures and safe retries."""

    cutoff = utc_now() - timedelta(seconds=config.analysis_heartbeat_timeout_seconds)
    recovered = 0
    requeued = 0
    async with _session_factory() as db:
        runs = (
            await db.scalars(
                select(PaperAnalysisRun)
                .where(
                    PaperAnalysisRun.status.in_(ACTIVE_ANALYSIS_RUN_STATUSES),
                    or_(
                        PaperAnalysisRun.heartbeat_at < cutoff,
                        and_(
                            PaperAnalysisRun.heartbeat_at.is_(None),
                            PaperAnalysisRun.started_at < cutoff,
                        ),
                    ),
                )
                .with_for_update(skip_locked=True)
            )
        ).all()
        for run in runs:
            recovered += 1
            failed_stage = run.stage if run.stage not in {"queued", "failed", "completed"} else "downloading"
            run.status = "failed"
            run.stage = "failed"
            run.error_code = "WORKER_LOST"
            run.error_message = "Worker heartbeat expired before the analysis completed."
            run.finished_at = utc_now()
            run.heartbeat_at = run.finished_at
            paper = await db.get(Paper, run.paper_id, with_for_update=True)
            if paper is None:
                continue
            if config.analysis_auto_requeue_worker_lost and run.attempt < config.analysis_max_retries:
                replacement_id = uuid4()
                replacement = PaperAnalysisRun(
                    id=replacement_id,
                    paper_id=run.paper_id,
                    celery_task_id=deterministic_task_id(replacement_id),
                    status="queued",
                    stage=failed_stage,
                    attempt=run.attempt,
                    force=True,
                    pipeline_version=config.analysis_version,
                    analysis_version=f"{config.analysis_version}-{replacement_id.hex[:12]}",
                    parser_version=config.analysis_parser_version,
                    prompt_version=config.analysis_prompt_version,
                    llm_model=config.llm_model,
                    embedding_model=config.embedding_model,
                    queued_at=utc_now(),
                )
                db.add(replacement)
                await db.flush()
                db.add(
                    TaskOutbox(
                        id=uuid4(),
                        event_key=f"paper-analysis-run:{replacement_id}",
                        event_type="paper.analysis.dispatch",
                        aggregate_type="paper_analysis_run",
                        aggregate_id=replacement_id,
                        analysis_run_id=replacement_id,
                        task_id=replacement.celery_task_id,
                        payload=_run_payload(replacement, run.paper_id),
                        status="pending",
                        available_at=utc_now(),
                    )
                )
                paper.parsed_status = "processing"
                _compat_metadata(paper, replacement, status="processing", stage="queued")
                requeued += 1
            else:
                successful = await db.scalar(
                    select(PaperAnalysisRun)
                    .where(
                        PaperAnalysisRun.paper_id == run.paper_id,
                        PaperAnalysisRun.status == "completed",
                    )
                    .order_by(PaperAnalysisRun.finished_at.desc().nullslast())
                    .limit(1)
                )
                paper.active_analysis_run_id = successful.id if successful else None
                paper.parsed_status = "completed" if successful else "failed"
                _compat_metadata(
                    paper,
                    run,
                    status=paper.parsed_status,
                    stage="failed",
                    error_code="WORKER_LOST",
                    error_message=run.error_message,
                )
        await db.commit()
    return {"recovered": recovered, "requeued": requeued}


__all__ = [
    "create_analysis_run",
    "get_current_analysis_run",
    "claim_analysis_run",
    "set_analysis_stage",
    "heartbeat_analysis_run",
    "mark_analysis_retry_wait",
    "mark_analysis_failed",
    "mark_analysis_completed",
    "dispatch_pending_outbox",
    "recover_stale_analysis_runs",
    "deterministic_task_id",
    "utc_now",
]

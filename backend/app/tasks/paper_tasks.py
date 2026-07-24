"""Celery entry points for durable paper-analysis runs."""

from __future__ import annotations

import asyncio
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import UUID

# Windows Python 3.13 defaults to ProactorEventLoop which crashes asyncpg.
# Celery workers don't go through main.py, so set the policy here.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select

from app.config import settings
from app.database import CelerySessionLocal
from app.models.paper import PaperAnalysisRun
from app.services.analysis_errors import classify_analysis_error
from app.services.analysis_runs import (
    dispatch_pending_outbox,
    mark_analysis_retry_wait,
    recover_stale_analysis_runs,
)
from app.services.paper_analysis import process_paper_async, record_failure
from app.tasks.celery_app import celery_app

# ---------------------------------------------------------------------------
# Persistent event loop for Celery async tasks
# ---------------------------------------------------------------------------
# Celery --pool=solo runs tasks synchronously (no event loop).  asyncio.run()
# creates a fresh loop per call, which causes asyncpg's internal protocol
# state to crash with "Future attached to a different loop" when the engine
# was created under a previous loop whose futures get recycled.
#
# Solution: a single long-lived SelectorEventLoop running in a daemon thread.
# All Celery async coroutines are dispatched onto it via
# asyncio.run_coroutine_threadsafe.
_LOOP_LOCK = threading.Lock()
_LOOP: asyncio.AbstractEventLoop | None = None
_LOOP_THREAD: threading.Thread | None = None


def _get_or_start_loop() -> asyncio.AbstractEventLoop:
    global _LOOP, _LOOP_THREAD
    if _LOOP is None or _LOOP.is_closed():
        with _LOOP_LOCK:
            if _LOOP is None or _LOOP.is_closed():
                if sys.platform == "win32":
                    _LOOP = asyncio.SelectorEventLoop()
                else:
                    _LOOP = asyncio.new_event_loop()
                asyncio.set_event_loop(_LOOP)
                _LOOP_THREAD = threading.Thread(
                    target=_LOOP.run_forever, daemon=True, name="celery-async-loop",
                )
                _LOOP_THREAD.start()
    return _LOOP


def _run_async(coroutine: Any) -> Any:
    """Run async worker code in normal Celery and eager/test execution."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # Celery solo pool: dispatch onto the persistent background loop.
        loop = _get_or_start_loop()
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        return future.result(timeout=600)
    # Celery eager mode can execute synchronously inside FastAPI's loop.  A
    # short-lived thread gives the coroutine its own event loop.
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coroutine).result()


async def _record_retry(
    paper_id: str,
    task_id: str | None,
    run_id: str | None,
    error: Exception,
    retry_number: int,
) -> None:
    info = classify_analysis_error(error)
    async with CelerySessionLocal() as db:
        run = await db.get(PaperAnalysisRun, run_id, with_for_update=True) if run_id else None
        if run is None and task_id:
            run = await db.scalar(
                select(PaperAnalysisRun)
                .where(PaperAnalysisRun.celery_task_id == task_id)
                .with_for_update()
            )
        if run is None:
            run = await db.scalar(
                select(PaperAnalysisRun)
                .where(PaperAnalysisRun.paper_id == UUID(paper_id))
                .order_by(PaperAnalysisRun.created_at.desc())
                .limit(1)
                .with_for_update()
            )
        if run is None:
            return
        stage = run.stage if run.stage not in {"queued", "completed", "failed"} else "downloading"
        await mark_analysis_retry_wait(
            db,
            run.id,
            stage=stage,
            error_code=info.code,
            error_message=str(error),
            retry_after_seconds=min(900, 2 ** min(retry_number, 8)),
            attempt=retry_number,
        )



@celery_app.task(
    bind=True,
    name="app.tasks.process_paper",
    max_retries=settings.analysis_max_retries,
    track_started=True,
    acks_late=True,
    queue=settings.analysis_queue,
)
def process_paper(
    self: Any,
    paper_id: str,
    run_id: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Run one paper analysis and retry only transient failures."""

    task_id = getattr(self.request, "id", None)
    try:
        return _run_async(
            process_paper_async(
                paper_id,
                task_id=task_id,
                run_id=run_id,
                force=force,
            )
        )
    except Exception as exc:
        info = classify_analysis_error(exc)
        retry_number = int(getattr(self.request, "retries", 0)) + 1
        if info.retryable and retry_number <= self.max_retries:
            _run_async(_record_retry(paper_id, task_id, run_id, exc, retry_number))
            raise self.retry(exc=exc, countdown=min(900, 2 ** min(retry_number, 8)))
        _run_async(
            record_failure(
                paper_id,
                exc,
                task_id=task_id,
                run_id=run_id,
                error_code=info.code,
            )
        )
        raise


@celery_app.task(name="app.tasks.dispatch_analysis_outbox", queue=settings.analysis_queue)
def dispatch_analysis_outbox() -> dict[str, int]:
    """Publish committed analysis events to the dedicated queue."""

    return _run_async(dispatch_pending_outbox())


@celery_app.task(name="app.tasks.reconcile_analysis_runs", queue=settings.analysis_queue)
def reconcile_analysis_runs() -> dict[str, int]:
    """Recover runs whose worker heartbeat has expired."""

    return _run_async(recover_stale_analysis_runs())


__all__ = [
    "dispatch_analysis_outbox",
    "process_paper",
    "reconcile_analysis_runs",
]

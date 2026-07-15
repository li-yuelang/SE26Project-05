"""Celery entry points for asynchronous paper analysis."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.config import settings
from app.services.analysis_state import mark_analysis_retrying
from app.services.paper_analysis import process_paper_async, record_failure
from app.database import AsyncSessionLocal
from app.tasks.celery_app import celery_app


async def _record_retry(paper_id: str, error: Exception, retry_number: int) -> None:
    async with AsyncSessionLocal() as db:
        await mark_analysis_retrying(db, paper_id, str(error), retry_number=retry_number)


def _run_async(coroutine: Any) -> Any:
    """Run a coroutine from both a worker thread and Celery eager API calls."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    # Celery eager mode executes the task synchronously inside FastAPI's event
    # loop.  A short-lived thread gives the coroutine its own loop while
    # preserving the normal synchronous Celery task contract.
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coroutine).result()


@celery_app.task(
    bind=True,
    name="app.tasks.process_paper",
    max_retries=settings.analysis_max_retries,
    track_started=True,
)
def process_paper(self: Any, paper_id: str, force: bool = False) -> dict[str, Any]:
    """Run one paper analysis with finite exponential-backoff retries."""

    task_id = getattr(self.request, "id", None)
    try:
        return _run_async(process_paper_async(paper_id, task_id=task_id, force=force))
    except Exception as exc:
        retry_number = int(getattr(self.request, "retries", 0)) + 1
        if retry_number <= self.max_retries:
            _run_async(_record_retry(paper_id, exc, retry_number))
            countdown = min(300, 2 ** min(retry_number, 8))
            raise self.retry(exc=exc, countdown=countdown)
        _run_async(record_failure(paper_id, exc, task_id=task_id))
        raise


__all__ = ["process_paper"]

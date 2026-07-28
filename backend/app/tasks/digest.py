"""Celery tasks for daily subscription ingestion and digest delivery."""
from __future__ import annotations

import logging
from typing import Any

from redis import Redis

from app.config import settings
from app.database import CelerySessionLocal
from app.services.arxiv_fetch import ArxivFetchError
from app.services.digest_sync import sync_subscription_arxiv
from app.tasks.async_utils import run_async
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)
LOCK_NAME = "papermate:digest:arxiv-sync"


async def _sync_subscription_arxiv() -> dict[str, str | int]:
    async with CelerySessionLocal() as db:
        return await sync_subscription_arxiv(db)


@celery_app.task(
    bind=True,
    name="app.tasks.sync_subscription_arxiv",
    max_retries=settings.arxiv_max_retries,
    acks_late=True,
    track_started=True,
    queue="arxiv",
)
def sync_subscription_arxiv_task(self: Any) -> dict[str, str | int]:
    """Synchronise the latest arXiv metadata needed by enabled subscriptions."""

    redis_client = Redis.from_url(settings.redis_coordination_url or settings.redis_url)
    lock = redis_client.lock(
        LOCK_NAME,
        timeout=settings.celery_visibility_timeout_seconds,
    )
    acquired = False
    try:
        acquired = bool(lock.acquire(blocking=False))
        if not acquired:
            logger.info("Skipped daily arXiv subscription sync because another run is active")
            return {"status": "skipped", "reason": "already_running"}
        return run_async(
            _sync_subscription_arxiv(),
            timeout_seconds=settings.celery_visibility_timeout_seconds,
        )
    except ArxivFetchError as exc:
        retry_number = int(getattr(self.request, "retries", 0)) + 1
        if exc.retryable and retry_number <= self.max_retries:
            raise self.retry(
                exc=exc,
                countdown=min(900, 30 * (2 ** (retry_number - 1))),
            )
        raise
    finally:
        if acquired:
            try:
                lock.release()
            except Exception:
                logger.warning("Unable to release daily arXiv sync lock", exc_info=True)
        redis_client.close()


@celery_app.task(name="digest.send_notifications")
def send_digest_notifications() -> None:
    """Send email / push notifications for daily digest."""
    # Placeholder for notification dispatch.
    pass


__all__ = ["send_digest_notifications", "sync_subscription_arxiv_task"]

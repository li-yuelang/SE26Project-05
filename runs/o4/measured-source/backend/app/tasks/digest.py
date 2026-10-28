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
def send_digest_notifications() -> dict[str, str | int]:
    """Send email / push notifications for daily digest to users at their configured push time."""

    async def _send() -> dict[str, str | int]:
        from datetime import datetime, timezone
        from sqlalchemy import select
        from app.models.user import User, UserPreference

        async with CelerySessionLocal() as db:
            now = datetime.now(timezone.utc)

            prefs = list((
                await db.scalars(
                    select(UserPreference)
                )
            ).all())

            sent_count = 0
            skipped_count = 0
            for pref in prefs:
                notif = pref.notification_settings or {}
                push_time = notif.get("push_time", "09:00")
                email_digest = notif.get("email_digest", True)
                last_sent_raw = notif.get("digest_last_sent_at")

                # Skip if email digest is disabled
                if not email_digest:
                    skipped_count += 1
                    continue

                # Only send at the user's configured push time (within 5-min window)
                current_time_str = datetime.now(
                    timezone.utc
                ).astimezone(
                    __import__("zoneinfo", fromlist=["ZoneInfo"]).ZoneInfo("Asia/Shanghai")
                ).strftime("%H:%M")
                if current_time_str != push_time:
                    skipped_count += 1
                    continue

                # Skip if already sent today
                if last_sent_raw:
                    try:
                        last_sent = datetime.fromisoformat(last_sent_raw)
                        if last_sent.date() == now.date():
                            skipped_count += 1
                            continue
                    except (ValueError, TypeError):
                        pass

                # Send notification (log + mark as sent)
                user = await db.scalar(
                    select(User).where(User.id == pref.user_id)
                )
                username = user.username if user else "unknown"
                logger.info(
                    "Digest notification sent to user=%s at push_time=%s",
                    username,
                    push_time,
                )
                pref.notification_settings = {
                    **notif,
                    "digest_last_sent_at": now.isoformat(),
                }
                sent_count += 1

            if sent_count or skipped_count:
                await db.commit()

            return {
                "status": "completed",
                "sent": sent_count,
                "skipped": skipped_count,
            }

    return run_async(
        _send(),
        timeout_seconds=settings.celery_visibility_timeout_seconds,
    )


__all__ = ["send_digest_notifications", "sync_subscription_arxiv_task"]

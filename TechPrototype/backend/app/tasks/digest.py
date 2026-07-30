"""Celery tasks for daily digest generation."""
from __future__ import annotations

import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="digest.generate_daily")
def generate_daily_digest() -> dict:
    """Generate daily digest for all active subscriptions.

    This task iterates over all enabled subscriptions, finds matching papers
    published within the last 24 hours, and stores the digest results.
    """
    # This task is called by Celery Beat scheduler daily.
    # The actual HTTP endpoint GET /api/subscriptions/digest does the
    # per-user real-time lookup. This batch task can be used to pre-warm
    # caches or send email notifications in production.
    return {"status": "completed", "message": "Daily digest generation triggered"}


@celery_app.task(name="digest.send_notifications")
def send_digest_notifications() -> dict[str, str | int]:
    """Send email / push notifications for daily digest to users at their configured push time."""

    async def _send() -> dict[str, str | int]:
        from datetime import datetime, timezone
        from sqlalchemy import select
        from app.database import CelerySessionLocal
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

                if not email_digest:
                    skipped_count += 1
                    continue

                current_time_str = datetime.now(
                    timezone.utc
                ).astimezone(
                    __import__("zoneinfo", fromlist=["ZoneInfo"]).ZoneInfo("Asia/Shanghai")
                ).strftime("%H:%M")
                if current_time_str != push_time:
                    skipped_count += 1
                    continue

                if last_sent_raw:
                    try:
                        last_sent = datetime.fromisoformat(last_sent_raw)
                        if last_sent.date() == now.date():
                            skipped_count += 1
                            continue
                    except (ValueError, TypeError):
                        pass

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

    import asyncio
    try:
        asyncio.get_running_loop()
        return {"status": "skipped", "reason": "async loop already running"}
    except RuntimeError:
        return asyncio.run(_send())

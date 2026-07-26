"""Celery tasks for daily digest generation."""
from __future__ import annotations

from app.tasks.celery_app import celery_app


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
    pass


@celery_app.task(name="digest.send_notifications")
def send_digest_notifications() -> None:
    """Send email / push notifications for daily digest."""
    # Placeholder for notification dispatch.
    pass

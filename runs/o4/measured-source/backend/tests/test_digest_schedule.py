"""Celery registration checks for the daily arXiv subscription sync."""

from types import SimpleNamespace

from app.config import settings
from app.tasks.celery_app import celery_app
from app.tasks import digest


def test_daily_arxiv_sync_schedule_and_route() -> None:
    schedule = celery_app.conf.beat_schedule["sync-subscription-arxiv-daily"]

    assert schedule["task"] == "app.tasks.sync_subscription_arxiv"
    assert settings.digest_arxiv_sync_hour in schedule["schedule"].hour
    assert settings.digest_arxiv_sync_minute in schedule["schedule"].minute
    assert schedule["options"]["queue"] == "arxiv"
    assert (
        celery_app.conf.task_routes["app.tasks.sync_subscription_arxiv"]["queue"]
        == "arxiv"
    )


def test_daily_arxiv_sync_skips_when_lock_is_already_held(monkeypatch) -> None:
    lock = SimpleNamespace(
        acquire=lambda **kwargs: False,
        release=lambda: None,
    )
    client = SimpleNamespace(
        lock=lambda *args, **kwargs: lock,
        close=lambda: None,
    )
    monkeypatch.setattr(digest.Redis, "from_url", lambda *args, **kwargs: client)

    result = digest.sync_subscription_arxiv_task.run()

    assert result == {"status": "skipped", "reason": "already_running"}

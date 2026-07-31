from celery import Celery
from celery.schedules import crontab

from app.config import settings

broker_url = settings.redis_broker_url or settings.redis_url
result_backend = settings.redis_result_backend_url or settings.redis_url

celery_app = Celery("papermate", broker=broker_url, backend=result_backend)
celery_app.conf.update(
    task_track_started=True,
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={
        "visibility_timeout": settings.celery_visibility_timeout_seconds,
    },
    result_expires=settings.analysis_result_expires_seconds,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=settings.celery_task_eager_propagates,
    include=["app.tasks.paper_tasks", "app.tasks.arxiv_fetch_task", "app.tasks.digest"],
    task_routes={
        "app.tasks.process_paper": {"queue": settings.analysis_queue},
        "app.tasks.dispatch_analysis_outbox": {"queue": settings.analysis_queue},
        "app.tasks.reconcile_analysis_runs": {"queue": settings.analysis_queue},
        "app.tasks.run_fetch_task": {"queue": "arxiv"},
        "app.tasks.dispatch_due_fetch_runs": {"queue": "arxiv"},
        "app.tasks.sync_subscription_arxiv": {"queue": "arxiv"},
        "digest.send_notifications": {"queue": "arxiv"},
    },
    beat_schedule={
        "dispatch-analysis-outbox-every-10-seconds": {
            "task": "app.tasks.dispatch_analysis_outbox",
            "schedule": 10.0,
            "options": {"queue": settings.analysis_queue},
        },
        "reconcile-analysis-runs-every-minute": {
            "task": "app.tasks.reconcile_analysis_runs",
            "schedule": float(settings.analysis_reconcile_interval_seconds),
            "options": {"queue": settings.analysis_queue},
        },
        "dispatch-due-fetch-runs-every-minute": {
            "task": "app.tasks.dispatch_due_fetch_runs",
            "schedule": 60.0,
            "options": {"queue": "arxiv"},
        },
        "sync-subscription-arxiv-daily": {
            "task": "app.tasks.sync_subscription_arxiv",
            "schedule": crontab(
                hour=settings.digest_arxiv_sync_hour,
                minute=settings.digest_arxiv_sync_minute,
            ),
            "options": {"queue": "arxiv"},
        },
        "send-digest-notifications-every-5-minutes": {
            "task": "digest.send_notifications",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "arxiv"},
        },
    },
)
celery_app.autodiscover_tasks(["app.tasks"])

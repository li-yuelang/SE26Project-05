from celery import Celery

from app.config import settings

celery_app = Celery("papermate", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_track_started=True,
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=settings.celery_task_eager_propagates,
    include=["app.tasks.paper_tasks", "app.tasks.arxiv_fetch_task"],
    task_routes={
        "app.tasks.process_paper": {"queue": "default"},
        "app.tasks.run_fetch_task": {"queue": "arxiv"},
        "app.tasks.dispatch_due_fetch_runs": {"queue": "default"},
    },
    beat_schedule={
        "dispatch-due-fetch-runs-every-minute": {
            "task": "app.tasks.dispatch_due_fetch_runs",
            "schedule": 60.0,
            "options": {"queue": "default"},
        },
    },
)
celery_app.autodiscover_tasks(["app.tasks"])

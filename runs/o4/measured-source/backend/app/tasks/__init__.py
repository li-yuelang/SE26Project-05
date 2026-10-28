"""Celery tasks are registered here by domain modules."""

from app.tasks.arxiv_fetch_task import dispatch_due_fetch_runs, run_fetch_task
from app.tasks.digest import send_digest_notifications, sync_subscription_arxiv_task
from app.tasks.paper_tasks import dispatch_analysis_outbox, process_paper, reconcile_analysis_runs

__all__ = [
    "dispatch_analysis_outbox",
    "dispatch_due_fetch_runs",
    "process_paper",
    "reconcile_analysis_runs",
    "run_fetch_task",
    "send_digest_notifications",
    "sync_subscription_arxiv_task",
]

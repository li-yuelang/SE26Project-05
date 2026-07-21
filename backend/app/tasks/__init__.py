"""Celery tasks are registered here by domain modules."""

from app.tasks.paper_tasks import dispatch_analysis_outbox, process_paper, reconcile_analysis_runs
from app.tasks.arxiv_fetch_task import dispatch_due_fetch_runs, run_fetch_task

__all__ = [
    "dispatch_analysis_outbox",
    "dispatch_due_fetch_runs",
    "process_paper",
    "reconcile_analysis_runs",
    "run_fetch_task",
]

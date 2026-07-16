"""Celery tasks are registered here by domain modules."""

from app.tasks.paper_tasks import process_paper
from app.tasks.arxiv_fetch_task import dispatch_due_fetch_runs, run_fetch_task

__all__ = ["dispatch_due_fetch_runs", "process_paper", "run_fetch_task"]

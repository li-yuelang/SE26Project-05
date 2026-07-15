"""Celery tasks are registered here by domain modules."""

from app.tasks.paper_tasks import process_paper

__all__ = ["process_paper"]

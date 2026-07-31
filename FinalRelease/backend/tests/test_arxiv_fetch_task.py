"""Regression tests for source metadata persisted by arXiv fetch tasks."""

from datetime import datetime, timezone
from types import SimpleNamespace

from app.tasks.arxiv_fetch_task import _sync_arxiv_source_dates


def test_duplicate_fetch_repairs_publication_date_from_arxiv_metadata() -> None:
    fetch_time = datetime(2026, 7, 22, 11, 16, tzinfo=timezone.utc)
    published_at = datetime(2024, 1, 3, 23, 45, tzinfo=timezone.utc)
    source_updated_at = datetime(2025, 4, 8, 9, 30, tzinfo=timezone.utc)
    paper = SimpleNamespace(
        published_at=fetch_time,
        updated_at_source=fetch_time,
    )

    changed = _sync_arxiv_source_dates(
        paper,
        {
            "published_at": published_at,
            "updated_at_source": source_updated_at,
        },
    )

    assert changed is True
    assert paper.published_at == published_at
    assert paper.updated_at_source == source_updated_at


def test_duplicate_fetch_never_replaces_dates_with_missing_values() -> None:
    published_at = datetime(2024, 1, 3, 23, 45, tzinfo=timezone.utc)
    source_updated_at = datetime(2025, 4, 8, 9, 30, tzinfo=timezone.utc)
    paper = SimpleNamespace(
        published_at=published_at,
        updated_at_source=source_updated_at,
    )

    changed = _sync_arxiv_source_dates(
        paper,
        {
            "published_at": None,
            "updated_at_source": None,
        },
    )

    assert changed is False
    assert paper.published_at == published_at
    assert paper.updated_at_source == source_updated_at

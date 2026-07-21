"""Pure rules for fetch-task configuration and scheduling."""

from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

import pytest

from app.models.task import FetchTask, FetchTaskRun
from app.schemas.task import TaskCreateRequest, TaskUpdateRequest
from app.services.arxiv_fetch import build_search_query, build_window_query
from app.services.task_service import calculate_next_run_at, calculate_run_window, derive_task_status


def test_keyword_configuration_deduplicates_and_defaults_to_or() -> None:
    request = TaskCreateRequest(
        name="RAG",
        task_type="keyword",
        keywords=[" rag ", "rag", "retrieval"],
        categories=["cs.AI", "cs.AI"],
    )

    assert request.keywords == ["rag", "retrieval"]
    assert request.categories == ["cs.AI"]
    assert request.keyword_match_mode == "or"
    assert request.auto_analyze is True


def test_new_task_requires_auto_analysis() -> None:
    with pytest.raises(ValueError, match="auto_analyze must be enabled"):
        TaskCreateRequest(
            name="No analysis",
            task_type="keyword",
            keywords=["rag"],
            auto_analyze=False,
        )


def test_task_configuration_rejects_invalid_combinations() -> None:
    with pytest.raises(ValueError, match="category tasks"):
        TaskCreateRequest(name="empty", task_type="category")
    with pytest.raises(ValueError, match="daily schedules"):
        TaskCreateRequest(name="daily", task_type="keyword", keywords=["llm"], schedule_kind="daily")
    with pytest.raises(ValueError, match="invalid arXiv categories"):
        TaskCreateRequest(name="bad", task_type="category", categories=["not-a-category"])
    with pytest.raises(ValueError, match="between 10 and 200"):
        TaskUpdateRequest(max_results=201)


def test_search_query_supports_or_and_and_escapes_quotes() -> None:
    query = build_search_query(keywords=['RAG "agents"', "LLM"], keyword_match_mode="or")
    assert " OR " in query
    assert '\\"agents\\"' in query

    query = build_search_query(keywords=["RAG", "LLM"], keyword_match_mode="and")
    assert " AND " in query


def test_submitted_date_window_is_added_to_query() -> None:
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    end = datetime(2026, 7, 2, tzinfo=timezone.utc)
    assert build_window_query("cat:cs.AI", start, end) == (
        "(cat:cs.AI) AND submittedDate:[202607010000 TO 202607020000]"
    )


def test_daily_and_weekly_schedules_use_shanghai_and_roll_forward() -> None:
    now = datetime(2026, 7, 16, 0, 0, tzinfo=timezone.utc)  # Thursday, 08:00 Shanghai
    assert calculate_next_run_at("daily", time(8, 30), None, now=now) == datetime(
        2026, 7, 16, 0, 30, tzinfo=timezone.utc
    )
    assert calculate_next_run_at("weekly", time(7, 0), 4, now=now) == datetime(
        2026, 7, 22, 23, 0, tzinfo=timezone.utc
    )


def test_subsequent_window_overlaps_last_success_by_24_hours() -> None:
    task = FetchTask(
        id=uuid4(),
        task_type="keyword",
        keywords=["llm"],
        categories=[],
        initial_lookback_days=7,
        max_results=50,
        last_success_at=datetime(2026, 7, 10, 0, 0, tzinfo=timezone.utc),
    )
    start, end = calculate_run_window(task, now=datetime(2026, 7, 12, tzinfo=timezone.utc))
    assert start == datetime(2026, 7, 9, tzinfo=timezone.utc)
    assert end == datetime(2026, 7, 12, tzinfo=timezone.utc)
    assert end - start == timedelta(days=3)


def test_task_status_prefers_active_run_and_hides_legacy_ownerless_state() -> None:
    task = FetchTask(id=uuid4(), task_type="keyword", is_enabled=True, schedule_kind="manual")
    latest = FetchTaskRun(task_id=task.id, status="failed")
    active = FetchTaskRun(task_id=task.id, status="running")
    assert derive_task_status(task, active, latest) == "running"
    assert derive_task_status(task, None, latest) == "failed"
    task.is_enabled = False
    assert derive_task_status(task, None, latest) == "paused"

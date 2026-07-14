"""Tests for task schemas."""

from uuid import uuid4

from app.schemas.task import FetchTaskResponse, TaskCatalogResponse


def test_fetch_task_serialization():
    task = FetchTaskResponse(
        id=uuid4(),
        task_type="keyword",
        status="running",
        schedule="每天 08:30",
        keywords=["llm", "rag"],
        categories=None,
        execution_log=[],
        started_at=None,
        finished_at=None,
        error_message=None,
        created_at="2026-07-01T00:00:00Z",
        updated_at="2026-07-01T00:00:00Z",
    )
    d = task.model_dump(mode="json")
    assert d["status"] == "running"
    assert d["task_type"] == "keyword"


def test_task_catalog_response():
    task = FetchTaskResponse(
        id=uuid4(),
        task_type="keyword",
        status="scheduled",
        schedule=None,
        keywords=[],
        categories=None,
        execution_log=[],
        started_at=None,
        finished_at=None,
        error_message=None,
        created_at="2026-07-01T00:00:00Z",
        updated_at="2026-07-01T00:00:00Z",
    )
    catalog = TaskCatalogResponse(tasks=[task], total=1)
    d = catalog.model_dump(by_alias=True)
    assert d["total"] == 1
    assert "statusMeta" in d
    assert "typeMeta" in d
    assert len(d["tasks"]) == 1

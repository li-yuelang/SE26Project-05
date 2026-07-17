"""Regression tests for fetch-task API response serialization."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.database import get_db_session
from app.main import app
from app.models.task import FetchTaskRun
from app.schemas.task import FetchTaskResponse, TaskDetailResponse
from app.services import task_service


class FakeSession:
    """The create endpoint delegates persistence to the mocked service below."""


def test_create_task_with_run_now_serializes_orm_run(monkeypatch) -> None:
    user_id = uuid4()
    task_id = uuid4()
    run_id = uuid4()
    now = datetime.now(timezone.utc)
    task = FetchTaskResponse(id=task_id, name="API serialization test")
    detail = TaskDetailResponse(task=task)
    run = FetchTaskRun(
        id=run_id,
        task_id=task_id,
        trigger_kind="initial",
        config_snapshot={"keywords": ["llm"]},
        status="queued",
        candidate_count=0,
        new_count=0,
        duplicate_count=0,
        analysis_queued_count=0,
        analysis_enqueue_failed_count=0,
        page_count=0,
        execution_log=[],
        created_at=now,
        updated_at=now,
    )

    async def fake_create_task(*_args, **_kwargs):
        return detail, run

    monkeypatch.setattr(task_service, "create_task", fake_create_task)
    app.dependency_overrides[get_db_session] = lambda: FakeSession()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user_id)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/tasks",
                json={
                    "name": "API serialization test",
                    "task_type": "keyword",
                    "keywords": ["llm"],
                    "run_now": True,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["data"]["run"]["id"] == str(run_id)
    assert response.json()["data"]["run"]["papers"] == []

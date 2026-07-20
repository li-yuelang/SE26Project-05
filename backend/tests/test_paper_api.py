from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1 import papers as papers_api
from app.database import get_db_session
from app.main import app
from app.models.paper import Paper


class FakeSession:
    def __init__(self, paper: Paper | None):
        self.paper = paper

    async def scalar(self, statement: object) -> Paper | None:
        del statement
        return self.paper

    async def get(self, model: object, paper_id: object) -> Paper | None:
        del model
        return self.paper if self.paper and self.paper.id == paper_id else None

    async def commit(self) -> None:
        return None

    async def delete(self, paper: Paper) -> None:
        if self.paper is paper:
            self.paper = None


class FakeTaskResult:
    id = "fake-task-1"


def make_paper(status: str = "pending") -> Paper:
    return Paper(
        id=uuid4(),
        arxiv_id="2301.00001",
        title="A paper",
        authors=[],
        abstract="Abstract",
        categories=[],
        published_at=datetime.now(timezone.utc),
        pdf_url="https://example.test/paper.pdf",
        arxiv_url="https://arxiv.org/abs/2301.00001",
        parsed_status=status,
    )


def test_reparse_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.post(f"/api/papers/{uuid4()}/analysis")

    assert response.status_code == 401


def test_analysis_not_found_uses_shared_error_shape() -> None:
    app.dependency_overrides[get_db_session] = lambda: FakeSession(None)
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/papers/{uuid4()}/analysis")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["code"] == "PAPER_NOT_FOUND"


def test_delete_paper_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.delete(f"/api/papers/{uuid4()}")

    assert response.status_code == 401


def test_delete_paper_returns_no_content() -> None:
    paper = make_paper()
    db = FakeSession(paper)
    app.dependency_overrides[get_db_session] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: object()
    try:
        with TestClient(app) as client:
            response = client.delete(f"/api/papers/{paper.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""
    assert db.paper is None


def test_delete_missing_paper_uses_shared_error_shape() -> None:
    app.dependency_overrides[get_db_session] = lambda: FakeSession(None)
    app.dependency_overrides[get_current_user] = lambda: object()
    try:
        with TestClient(app) as client:
            response = client.delete(f"/api/papers/{uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["code"] == "PAPER_NOT_FOUND"


def test_batch_delete_returns_deleted_ids(monkeypatch) -> None:
    paper_ids = [uuid4(), uuid4()]

    async def fake_delete_papers(db, requested_ids):
        del db
        assert requested_ids == paper_ids
        return requested_ids

    monkeypatch.setattr(papers_api.paper_service, "delete_papers", fake_delete_papers)
    app.dependency_overrides[get_db_session] = lambda: FakeSession(None)
    app.dependency_overrides[get_current_user] = lambda: object()
    try:
        with TestClient(app) as client:
            response = client.request(
                "DELETE",
                "/api/papers/batch",
                json={"paper_ids": [str(paper_id) for paper_id in paper_ids]},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["data"] == {
        "deletedIds": [str(paper_id) for paper_id in paper_ids],
        "deletedCount": 2,
    }


def test_processing_analysis_request_is_idempotent(monkeypatch) -> None:
    paper = make_paper()
    db = FakeSession(paper)
    calls: list[tuple[tuple, dict]] = []

    def fake_delay(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeTaskResult()

    monkeypatch.setattr(papers_api.process_paper, "delay", fake_delay)
    app.dependency_overrides[get_db_session] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: object()
    try:
        with TestClient(app) as client:
            first = client.post(f"/api/papers/{paper.id}/analysis")
            second = client.post(f"/api/papers/{paper.id}/analysis")
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["data"]["taskId"] == "fake-task-1"
    assert second.json()["data"]["taskId"] == "fake-task-1"
    assert len(calls) == 1

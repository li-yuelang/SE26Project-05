from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db_session

from app.main import app


def test_health_check() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


@pytest.mark.parametrize("failure", [None, OSError(), TimeoutError(), SQLAlchemyError()])
def test_readiness_tracks_paper_store(monkeypatch, failure) -> None:
    db = AsyncMock()
    db.execute.side_effect = failure
    monkeypatch.setitem(app.dependency_overrides, get_db_session, lambda: db)
    with TestClient(app) as client:
        response = client.get("/readyz")
        assert client.get("/health").status_code == 200

    db.execute.assert_awaited_once()
    if failure is None:
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "ready"
    else:
        assert response.status_code == 503

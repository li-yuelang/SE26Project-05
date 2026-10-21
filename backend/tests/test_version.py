import json
from importlib.resources import files

from fastapi.testclient import TestClient

from app.main import app


def test_version_matches_packaged_build_info() -> None:
    expected = json.loads(
        files("app").joinpath("build_info.json").read_text(encoding="utf-8")
    )

    with TestClient(app) as client:
        response = client.get("/version")

    assert response.status_code == 200
    assert response.json()["data"] == expected
    assert {"version", "build_no", "commit", "run_id", "run_url"} <= expected.keys()
    assert all(isinstance(value, str) for value in expected.values())
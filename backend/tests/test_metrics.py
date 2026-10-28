import asyncio

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry, generate_latest

from app.core.metrics import HttpMetrics, RedMetricsMiddleware


def test_red_labels_counts_errors_and_exclusions():
    registry = CollectorRegistry()
    metrics = HttpMetrics(registry)
    app = FastAPI()
    app.add_middleware(RedMetricsMiddleware, metrics=metrics)

    @app.get("/papers/{paper_id}")
    async def paper(paper_id: int):
        if paper_id == 2:
            raise HTTPException(503, "unavailable")
        if paper_id == 3:
            raise RuntimeError("unexpected")
        return {"id": paper_id}

    with TestClient(app, raise_server_exceptions=False) as client:
        for path, code in [("/papers/1?token=secret", 200), ("/papers/2", 503),
                           ("/papers/3", 500), ("/papers/no-int", 422),
                           ("/missing/random-id", 404)]:
            assert client.get(path).status_code == code
        client.get("/metrics")
        client.get("/health")
    for code in ("200", "503", "500", "422"):
        labels = {"method": "GET", "route": "/papers/{paper_id}", "code": code}
        assert registry.get_sample_value("papermate_http_requests_total", labels) == 1
        assert registry.get_sample_value("papermate_http_request_duration_seconds_count", labels) == 1
    assert registry.get_sample_value("papermate_http_inflight_requests") == 0
    output = generate_latest(registry).decode()
    assert 'route="__unmatched__"' in output
    assert "secret" not in output and "random-id" not in output
    assert '/metrics' not in output and '/health' not in output


def test_stream_duration_includes_last_body():
    registry = CollectorRegistry()
    metrics = HttpMetrics(registry)
    app = FastAPI()
    app.add_middleware(RedMetricsMiddleware, metrics=metrics)

    @app.get("/stream")
    async def stream():
        async def chunks():
            yield b"first"
            await asyncio.sleep(.03)
            yield b"last"
        return StreamingResponse(chunks())

    with TestClient(app) as client:
        assert client.get("/stream").content == b"firstlast"
    labels = {"method": "GET", "route": "/stream", "code": "200"}
    assert registry.get_sample_value("papermate_http_request_duration_seconds_sum", labels) >= .03
    assert registry.get_sample_value("papermate_http_inflight_requests") == 0


def test_included_router_keeps_api_prefix_in_label():
    registry = CollectorRegistry()
    app = FastAPI()
    app.add_middleware(RedMetricsMiddleware, metrics=HttpMetrics(registry), api_prefix="/api")
    router = APIRouter(prefix="/papers")

    @router.get("/{paper_id}")
    async def paper(paper_id: int):
        return {"id": paper_id}

    app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        assert client.get("/api/papers/123").status_code == 200
    assert registry.get_sample_value("papermate_http_requests_total", {
        "method": "GET", "route": "/api/papers/{paper_id}", "code": "200"
    }) == 1

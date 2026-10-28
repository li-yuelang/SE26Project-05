"""Single-process HTTP RED metrics; never use raw URLs as labels."""

from time import perf_counter

from prometheus_client import Counter, Gauge, Histogram, REGISTRY
from starlette.types import ASGIApp, Message, Receive, Scope, Send

LATENCY_BUCKETS = (.001, .002, .005, .01, .02, .05, .1, .2, .5, 1, 2, 5)
EXCLUDED_PATHS = {"/metrics", "/health", "/version", "/docs", "/redoc", "/openapi.json"}


class HttpMetrics:
    def __init__(self, registry=REGISTRY):
        labels = ("method", "route", "code")
        self.requests = Counter(
            "papermate_http_requests_total", "Completed HTTP requests by response status.",
            labels, registry=registry,
        )
        self.duration = Histogram(
            "papermate_http_request_duration_seconds",
            "Time from middleware entry to final response body or application exception.",
            labels, buckets=LATENCY_BUCKETS, registry=registry,
        )
        self.inflight = Gauge(
            "papermate_http_inflight_requests", "Requests currently inside HTTP middleware.",
            registry=registry,
        )


http_metrics = HttpMetrics()


class RedMetricsMiddleware:
    def __init__(self, app: ASGIApp, metrics: HttpMetrics = http_metrics, api_prefix: str = ""):
        self.app = app
        self.metrics = metrics
        self.api_prefix = api_prefix.rstrip("/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http" or scope["path"].rstrip("/") in EXCLUDED_PATHS:
            await self.app(scope, receive, send)
            return

        started = perf_counter()
        code = 500
        duration = None
        self.metrics.inflight.inc()

        async def measured_send(message: Message):
            nonlocal code, duration
            if message["type"] == "http.response.start":
                code = message["status"]
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                duration = perf_counter() - started

        try:
            await self.app(scope, receive, measured_send)
        finally:
            # Routing populates scope only after entering the downstream app.
            route = getattr(scope.get("route"), "path", "__unmatched__")
            # Recent FastAPI versions expose the included router's original
            # route rather than its effective path. Keep the configured API
            # prefix in labels on both old and new versions.
            prefix = self.api_prefix
            if (prefix and route != "__unmatched__"
                    and scope["path"].startswith(prefix + "/")
                    and route != prefix and not route.startswith(prefix + "/")):
                route = prefix + route
            method = scope["method"]
            if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
                method = "OTHER"
            labels = (method, route, str(code))
            self.metrics.requests.labels(*labels).inc()
            self.metrics.duration.labels(*labels).observe(
                duration if duration is not None else perf_counter() - started
            )
            self.metrics.inflight.dec()

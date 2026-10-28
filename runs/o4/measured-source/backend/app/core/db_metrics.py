"""Measure actual async pool acquisition and checkout-to-checkin lifetime."""

from time import perf_counter

from prometheus_client import Counter, Gauge, Histogram, REGISTRY
from sqlalchemy import event
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.pool import AsyncAdaptedQueuePool

BUCKETS = (.0001, .0002, .0005, .001, .002, .005, .01, .02, .05, .1, .2, .5, 1, 2, 5)


class DatabaseMetrics:
    def __init__(self, registry=REGISTRY):
        self.checked_out = Gauge(
            "papermate_db_pool_checked_out", "Connections currently borrowed from the API pool.",
            registry=registry,
        )
        self.capacity = Gauge(
            "papermate_db_pool_capacity", "Configured pool_size plus max_overflow, per API worker.",
            registry=registry,
        )
        self.acquiring = Gauge(
            "papermate_db_pool_acquiring", "Calls currently acquiring a connection (not pure waiters).",
            registry=registry,
        )
        self.acquire = Histogram(
            "papermate_db_pool_acquire_seconds",
            "Pool.connect duration, including queueing, connection creation and pre-ping.",
            ["outcome"], buckets=BUCKETS, registry=registry,
        )
        for outcome in ("success", "timeout", "error"):
            self.acquire.labels(outcome)
        self.hold = Histogram(
            "papermate_db_pool_hold_seconds",
            "Checkout-to-checkin duration, including SQL and application/transaction lifetime.",
            buckets=BUCKETS, registry=registry,
        )
        self.timeouts = Counter(
            "papermate_db_pool_timeouts_total", "API connection pool acquisition timeouts.",
            registry=registry,
        )


db_metrics = DatabaseMetrics()


class ObservedAsyncPool(AsyncAdaptedQueuePool):
    metrics = db_metrics

    def connect(self):
        started = perf_counter()
        outcome = "success"
        self.metrics.acquiring.inc()
        try:
            return super().connect()
        except PoolTimeoutError:
            outcome = "timeout"
            self.metrics.timeouts.inc()
            raise
        except BaseException:
            outcome = "error"
            raise
        finally:
            self.metrics.acquire.labels(outcome).observe(perf_counter() - started)
            self.metrics.acquiring.dec()


def instrument_pool(engine, capacity: int, metrics: DatabaseMetrics = db_metrics):
    engine.sync_engine.pool.metrics = metrics
    metrics.capacity.set(capacity)
    metrics.checked_out.set_function(lambda: engine.sync_engine.pool.checkedout())

    @event.listens_for(engine.sync_engine, "checkout")
    def checkout(connection, record, proxy):
        record.record_info["papermate_checkout_started"] = perf_counter()

    @event.listens_for(engine.sync_engine, "checkin")
    def checkin(connection, record):
        started = record.record_info.pop("papermate_checkout_started", None)
        if started is not None:
            metrics.hold.observe(perf_counter() - started)

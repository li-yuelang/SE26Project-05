"""Database configuration safeguards for asynchronous worker execution."""

from sqlalchemy.pool import NullPool

from app.database import engine


def test_async_engine_does_not_reuse_connections_across_event_loops() -> None:
    """Celery's per-task event loops must not share asyncpg connections."""

    assert isinstance(engine.sync_engine.pool, NullPool)

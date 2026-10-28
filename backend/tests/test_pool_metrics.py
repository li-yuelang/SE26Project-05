import asyncio
import os

from fastapi import HTTPException
from prometheus_client import CollectorRegistry
import pytest
from sqlalchemy import text
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.core.db_metrics import DatabaseMetrics, ObservedAsyncPool, instrument_pool
from app import database


def test_pool_settings_preserve_defaults_and_reject_unbounded_capacity():
    settings = Settings(_env_file=None)
    assert settings.db_pool_size == 200
    assert settings.db_max_overflow == 100
    with pytest.raises(ValueError):
        Settings(_env_file=None, db_pool_size=0)
    with pytest.raises(ValueError):
        Settings(_env_file=None, db_max_overflow=-1)


def integration_engine():
    url = os.environ.get("O4_INTEGRATION_DATABASE_URL")
    if not url:
        pytest.skip("Set explicit O4_INTEGRATION_DATABASE_URL for a disposable PostgreSQL DB")
    registry = CollectorRegistry()
    metrics = DatabaseMetrics(registry)
    engine = create_async_engine(url, poolclass=ObservedAsyncPool, pool_size=1,
                                 max_overflow=0, pool_timeout=.03, pool_pre_ping=True)
    instrument_pool(engine, 1, metrics)
    return engine, registry


@pytest.mark.integration
async def test_real_pool_contention_timeout_and_release():
    engine, registry = integration_engine()
    try:
        async with engine.connect() as held:
            await held.execute(text("select 1"))
            assert registry.get_sample_value("papermate_db_pool_checked_out") == 1
            with pytest.raises(PoolTimeoutError):
                async with engine.connect():
                    pass
            assert registry.get_sample_value("papermate_db_pool_timeouts_total") == 1
            assert registry.get_sample_value("papermate_db_pool_acquiring") == 0
            assert registry.get_sample_value("papermate_db_pool_acquire_seconds_sum",
                                             {"outcome": "timeout"}) >= .025
        assert registry.get_sample_value("papermate_db_pool_checked_out") == 0
        assert registry.get_sample_value("papermate_db_pool_hold_seconds_count") == 1
        assert registry.get_sample_value("papermate_db_pool_hold_seconds_sum") >= .025
        async with engine.connect():
            pass
        assert registry.get_sample_value("papermate_db_pool_hold_seconds_count") == 2
    finally:
        await engine.dispose()


@pytest.mark.integration
async def test_cancelled_acquisition_leaves_no_gauge_leak_and_timeout_maps_to_503(monkeypatch):
    engine, registry = integration_engine()
    monkeypatch.setattr(database, "AsyncSessionLocal", async_sessionmaker(engine))
    try:
        async with engine.connect():
            async def acquire():
                async with engine.connect():
                    pass
            pending = asyncio.create_task(acquire())
            await asyncio.sleep(.005)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            assert registry.get_sample_value("papermate_db_pool_acquiring") == 0
            dependency = database.get_db_session()
            session = await anext(dependency)
            with pytest.raises(PoolTimeoutError) as caught:
                await session.execute(text("select 1"))
            with pytest.raises(HTTPException) as response:
                await dependency.athrow(caught.value)
            assert response.value.status_code == 503
        assert registry.get_sample_value("papermate_db_pool_checked_out") == 0
    finally:
        await engine.dispose()

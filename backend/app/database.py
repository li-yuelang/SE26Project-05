from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings


class Base(DeclarativeBase):
    pass


# ---- FastAPI engine (sized pool) ----
# Reuses connections across HTTP requests under a single long-lived event
# loop.  pool_size + max_overflow must cover the expected concurrency so
# requests don't queue at the application layer.
_engine = create_async_engine(
    settings.database_url,
    pool_size=200,
    max_overflow=100,
    pool_recycle=1800,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(
    _engine, expire_on_commit=False, class_=AsyncSession,
)


# ---- Celery engine (NullPool) ----
# Celery --pool=solo spawns a fresh asyncio event loop per task.
# We use a single persistent SelectorEventLoop (see paper_tasks._run_async)
# so a module-level engine is safe — all connections are always created in
# the same loop.  NullPool ensures no connection is recycled across tasks.
_celery_engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool,
    connect_args={"timeout": 30, "command_timeout": 30},
)
CelerySessionLocal = async_sessionmaker(
    _celery_engine, expire_on_commit=False, class_=AsyncSession,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

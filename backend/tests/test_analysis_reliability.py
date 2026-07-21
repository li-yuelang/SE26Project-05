"""Reliability tests for the durable analysis state boundary."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import redis

from app.config import settings
from app.core.embedding import EmbeddingConfigurationError
from app.core.llm_gateway import LLMConfigurationError
from app.models.paper import Paper
from app.services.analysis_errors import classify_analysis_error
from app.services.analysis_runs import claim_analysis_run, create_analysis_run


def test_permanent_provider_configuration_errors_are_not_retryable() -> None:
    llm_info = classify_analysis_error(LLMConfigurationError("missing key"))
    embedding_info = classify_analysis_error(EmbeddingConfigurationError("missing key"))
    assert llm_info.code == "LLM_CONFIG_ERROR"
    assert llm_info.retryable is False
    assert embedding_info.code == "EMBEDDING_ERROR"
    assert embedding_info.retryable is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_postgres_run_creation_is_idempotent_and_redis_is_reachable() -> None:
    if os.getenv("PAPERMATE_REAL_SERVICES") != "1":
        pytest.skip("set PAPERMATE_REAL_SERVICES=1 to use the real PostgreSQL/Redis services")

    redis_client = redis.Redis.from_url(settings.redis_broker_url or settings.redis_url)
    assert redis_client.ping() is True
    redis_client.close()

    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            paper = Paper(
                arxiv_id=f"integration-{uuid4().hex[:16]}",
                title="Reliability integration paper",
                authors=[],
                abstract="integration",
                categories=[],
                primary_category=None,
                published_at=datetime.now(timezone.utc),
                pdf_url="https://example.test/paper.pdf",
                arxiv_url="https://arxiv.org/abs/integration",
                parsed_status="pending",
                metadata_extra={},
            )
            db.add(paper)
            await db.flush()
            first, first_created = await create_analysis_run(db, paper.id)
            second, second_created = await create_analysis_run(db, paper.id)
            assert first_created is True
            assert second_created is False
            assert first.id == second.id
            assert first.status == "queued"
            assert first.celery_task_id.startswith("paper-analysis-")
            claimed = await claim_analysis_run(db, first.id, task_id=first.celery_task_id)
            assert claimed is not None
            assert claimed.status == "downloading"
            duplicate = await claim_analysis_run(db, first.id, task_id=first.celery_task_id)
            assert duplicate is None
        finally:
            await db.rollback()

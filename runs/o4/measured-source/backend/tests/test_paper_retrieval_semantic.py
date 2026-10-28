"""Semantic candidate fusion for abstract and full-text embeddings."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.paper_retrieval import PaperHybridRetriever


@pytest.mark.asyncio
async def test_semantic_candidates_keep_best_abstract_or_chunk_distance() -> None:
    shared_id = uuid4()
    abstract_only_id = uuid4()
    chunk_only_id = uuid4()
    responses = iter(
        [
            SimpleNamespace(all=lambda: [(shared_id, 0.3), (abstract_only_id, 0.2)]),
            SimpleNamespace(all=lambda: [(shared_id, 0.1), (chunk_only_id, 0.4)]),
        ]
    )

    class FakeSession:
        async def execute(self, statement: object) -> SimpleNamespace:
            return next(responses)

    distances = await PaperHybridRetriever._semantic_candidates(
        FakeSession(),
        query_embedding=[0.0] * 1536,
        since=None,
        exclude_ids=set(),
        limit=10,
    )

    assert distances == {
        shared_id: 0.1,
        abstract_only_id: 0.2,
        chunk_only_id: 0.4,
    }

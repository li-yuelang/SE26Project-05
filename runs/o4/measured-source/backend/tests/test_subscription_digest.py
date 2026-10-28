from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1 import subscriptions as subscriptions_api
from app.api.v1.subscriptions import _calculate_digest_relevance


def make_paper(**overrides):
    values = {
        "title": "Efficient Transformers for Long Documents",
        "abstract": "We introduce a sparse attention method.",
        "primary_category": "cs.CL",
        "categories": ["cs.CL", "cs.AI"],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_digest_relevance_rewards_title_matches() -> None:
    score, matched = _calculate_digest_relevance(make_paper(), ["transformers"])

    assert score == 0.85
    assert matched == ["transformers"]


def test_digest_relevance_scores_abstract_and_category_matches() -> None:
    abstract_score, _ = _calculate_digest_relevance(make_paper(), ["sparse attention"])
    category_score, matched = _calculate_digest_relevance(make_paper(), ["cs.ai"])

    assert abstract_score == 0.5
    assert category_score == 0.65
    assert matched == ["cs.ai"]


def test_digest_relevance_returns_zero_without_terms() -> None:
    assert _calculate_digest_relevance(make_paper(), []) == (0.0, [])


@pytest.mark.asyncio
async def test_digest_reads_database_and_limits_each_topic_to_five(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subscription = SimpleNamespace(
        topic_keywords=["RAG"],
        categories=["cs.AI"],
    )
    scalar_results = iter(
        [
            SimpleNamespace(all=lambda: [subscription]),
            SimpleNamespace(all=lambda: []),
        ]
    )

    class FakeSession:
        async def scalars(self, statement: object) -> SimpleNamespace:
            return next(scalar_results)

    paper = SimpleNamespace(
        id=uuid4(),
        arxiv_id="2607.00001",
        title="Fresh RAG",
        authors=["A. Author"],
        abstract="Abstract",
        primary_category="cs.AI",
        published_at=subscriptions_api.datetime.now(subscriptions_api.timezone.utc),
        arxiv_url="https://arxiv.org/abs/2607.00001",
    )
    result_item = SimpleNamespace(paper=paper, score=0.9, reason="匹配主题 RAG")
    embed_queries = AsyncMock(return_value=[[0.0] * 1536])
    search = AsyncMock(return_value=[result_item])
    monkeypatch.setattr(
        subscriptions_api.paper_hybrid_retriever,
        "embed_queries",
        embed_queries,
    )
    monkeypatch.setattr(
        subscriptions_api.paper_hybrid_retriever,
        "search",
        search,
    )

    response = await subscriptions_api.get_daily_digest(
        SimpleNamespace(id=uuid4()),
        FakeSession(),
    )

    assert response["data"]["topic_groups"][0]["papers"][0]["arxiv_id"] == "2607.00001"
    assert search.await_args.kwargs["result_limit"] == 5
    embed_queries.assert_awaited_once_with(["RAG"])

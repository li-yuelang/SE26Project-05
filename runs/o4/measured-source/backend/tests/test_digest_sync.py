"""Tests for the scheduled arXiv subscription digest sync."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.paper import Paper
from app.services import digest_sync
from app.services.digest_sync import (
    _embed_papers,
    _persist_candidates,
    sync_subscription_arxiv,
    unique_subscription_queries,
)


def make_subscription(
    *,
    keywords: list[str],
    categories: list[str],
    enabled: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        topic_keywords=keywords,
        categories=categories,
        enabled=enabled,
    )


def make_raw(arxiv_id: str = "2607.00001", *, title: str = "Fresh Paper") -> dict:
    published_at = datetime(2026, 7, 28, 0, 0, tzinfo=timezone.utc)
    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "authors": ["A. Author"],
        "abstract": "A useful abstract.",
        "categories": ["cs.AI"],
        "primary_category": "cs.AI",
        "published_at": published_at,
        "updated_at_source": published_at,
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
        "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
        "metadata_extra": None,
    }


def test_unique_subscription_queries_filters_and_deduplicates() -> None:
    subscriptions = [
        make_subscription(keywords=[" RAG ", "Agents"], categories=["cs.AI"]),
        make_subscription(keywords=["agents", "rag"], categories=["cs.AI"]),
        make_subscription(keywords=["ignored"], categories=[], enabled=False),
        make_subscription(keywords=[], categories=[]),
    ]

    queries = unique_subscription_queries(subscriptions)

    assert len(queries) == 1
    assert tuple(value.casefold() for value in queries[0].keywords) == ("agents", "rag")
    assert queries[0].categories == ("cs.AI",)


@pytest.mark.asyncio
async def test_sync_fetches_each_unique_query_once(monkeypatch: pytest.MonkeyPatch) -> None:
    subscriptions = [
        make_subscription(keywords=["RAG"], categories=["cs.AI"]),
        make_subscription(keywords=["rag"], categories=["cs.AI"]),
        make_subscription(keywords=["LoRA"], categories=["cs.LG"]),
    ]
    scalar_result = SimpleNamespace(all=lambda: subscriptions)
    db = SimpleNamespace(scalars=AsyncMock(return_value=scalar_result))
    fetch = AsyncMock(return_value=([make_raw()], 1))
    persist = AsyncMock(return_value=(1, 0, 0, []))
    embed = AsyncMock(return_value=(0, 0))
    monkeypatch.setattr(digest_sync, "fetch_arxiv_window", fetch)
    monkeypatch.setattr(digest_sync, "_persist_candidates", persist)
    monkeypatch.setattr(digest_sync, "_embed_papers", embed)
    monkeypatch.setattr(digest_sync.settings, "digest_arxiv_lookback_hours", 24)
    monkeypatch.setattr(
        digest_sync.settings,
        "digest_arxiv_max_results_per_subscription",
        50,
    )
    now = datetime(2026, 7, 28, 7, 0, tzinfo=timezone.utc)

    result = await sync_subscription_arxiv(db, now=now)

    assert fetch.await_count == 2
    for call in fetch.await_args_list:
        assert call.kwargs["window_end"] == now
        assert (now - call.kwargs["window_start"]).total_seconds() == 24 * 3600
        assert call.kwargs["max_results"] == 50
    assert result["query_count"] == 2
    assert result["candidate_count"] == 2
    assert result["unique_candidate_count"] == 1


class FakePersistSession:
    def __init__(self, existing: list[Paper] | None = None):
        self.existing = existing or []
        self.added: list[Paper] = []
        self.commit = AsyncMock()

    async def scalars(self, statement: object) -> SimpleNamespace:
        return SimpleNamespace(all=lambda: self.existing)

    def add(self, paper: Paper) -> None:
        self.added.append(paper)


@pytest.mark.asyncio
async def test_persist_candidates_inserts_and_updates_source_metadata() -> None:
    existing = Paper(
        arxiv_id="2607.00002",
        title="Old title",
        authors=[],
        abstract="Old abstract",
        categories=["cs.CL"],
        primary_category="cs.CL",
        published_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
        pdf_url="",
        arxiv_url="",
        parsed_status="pending",
    )
    db = FakePersistSession([existing])

    inserted, updated, duplicate, embedding_targets = await _persist_candidates(
        db,
        [make_raw(), make_raw("2607.00002", title="Updated title")],
    )

    assert (inserted, updated, duplicate) == (1, 1, 0)
    assert len(db.added) == 1
    assert existing.title == "Updated title"
    assert len(embedding_targets) == 2
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_embedding_failure_keeps_metadata_and_uses_lexical_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paper = Paper(
        arxiv_id="2607.00001",
        title="Fresh Paper",
        authors=[],
        abstract="Abstract",
        categories=["cs.AI"],
        primary_category="cs.AI",
        published_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
        pdf_url="",
        arxiv_url="",
        parsed_status="pending",
    )
    provider = SimpleNamespace(embed=AsyncMock(side_effect=RuntimeError("provider down")))
    monkeypatch.setattr(digest_sync, "get_embedding_provider", lambda: provider)
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())

    embedded, failed = await _embed_papers(db, [paper])

    assert (embedded, failed) == (0, 1)
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()

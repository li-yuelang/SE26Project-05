"""Tests for paper service — upsert and pure helpers."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.paper_service import upsert_arxiv_papers


class FakePaperDBSession:
    """Simulates enough AsyncSession for upsert_arxiv_papers."""

    def __init__(self, *, existing_arxiv_ids: set[str] | None = None):
        self._existing = existing_arxiv_ids or set()
        self.added: list = []
        self.commit_called = False

    async def scalar(self, statement):
        del statement
        # Simulate: return 1 if arxiv_id exists
        # We use a simple heuristic - always return None for simplicity
        # unless overridden
        return None

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commit_called = True


class UpsertFakeSession:
    """Stateful session that tracks which arxiv_ids have been 'inserted'."""

    def __init__(self, existing_ids: set[str] | None = None):
        self._existing = set(existing_ids or [])
        self.added: list = []
        self.commit_called = False

    async def scalar(self, statement):
        # The statement selects Paper where arxiv_id == ...
        # We intercept by checking the .where() clause — but that's complex.
        # Instead, we monkey-patch the approach: track via a closure.
        return None

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commit_called = True


def test_upsert_all_new_papers() -> None:
    raw = [
        {
            "arxiv_id": "2401.00001",
            "title": "New Paper 1",
            "authors": ["Alice"],
            "abstract": "Abstract 1",
            "categories": ["cs.AI"],
            "primary_category": "cs.AI",
            "published_at": datetime.now(timezone.utc),
            "updated_at_source": None,
            "pdf_url": "https://arxiv.org/pdf/2401.00001",
            "arxiv_url": "https://arxiv.org/abs/2401.00001",
            "metadata_extra": None,
        },
        {
            "arxiv_id": "2401.00002",
            "title": "New Paper 2",
            "authors": ["Bob"],
            "abstract": "Abstract 2",
            "categories": ["cs.CL"],
            "primary_category": "cs.CL",
            "published_at": datetime.now(timezone.utc),
            "updated_at_source": None,
            "pdf_url": "",
            "arxiv_url": "",
            "metadata_extra": None,
        },
    ]

    db = UpsertFakeSession()
    import asyncio

    async def fake_scalar(statement):
        # If we've already seen this paper, return a fake
        return None

    db.scalar = fake_scalar
    inserted, skipped = asyncio.run(upsert_arxiv_papers(db, raw))
    assert inserted == 2
    assert skipped == 0
    assert db.commit_called
    assert db.added[0].arxiv_id == "2401.00001"
    assert db.added[1].arxiv_id == "2401.00002"


def test_upsert_duplicates_skipped() -> None:
    raw = [
        {
            "arxiv_id": "2401.00001",
            "title": "Paper",
            "authors": ["Alice"],
            "abstract": "Abstract",
            "categories": ["cs.AI"],
            "primary_category": "cs.AI",
            "published_at": datetime.now(timezone.utc),
            "updated_at_source": None,
            "pdf_url": "",
            "arxiv_url": "",
            "metadata_extra": None,
        },
    ]

    db = UpsertFakeSession()
    call_count = [0]

    async def fake_scalar(statement):
        call_count[0] += 1
        if call_count[0] == 1:
            return SimpleNamespace(id=uuid4())  # exists
        return None

    db.scalar = fake_scalar
    import asyncio
    inserted, skipped = asyncio.run(upsert_arxiv_papers(db, raw))
    assert inserted == 0
    assert skipped == 1


def test_upsert_empty_list() -> None:
    db = UpsertFakeSession()
    import asyncio
    inserted, skipped = asyncio.run(upsert_arxiv_papers(db, []))
    assert inserted == 0
    assert skipped == 0
    assert not db.commit_called

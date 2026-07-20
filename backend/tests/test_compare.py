"""Tests for CompareService — serialisation, create, list, delete, export."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.compare import CompareService


def _make_comparison(user_id, title="对比", paper_ids=None):
    return SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        title=title,
        paper_ids=paper_ids or [],
        report_content=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_paper(paper_id=None, **kwargs):
    if paper_id is None:
        paper_id = uuid4()
    return SimpleNamespace(
        id=paper_id,
        arxiv_id=kwargs.get("arxiv_id", "2401.00001"),
        title=kwargs.get("title", "A Paper"),
        authors=kwargs.get("authors", ["Author"]),
        abstract=kwargs.get("abstract", "Abstract text"),
        primary_category=kwargs.get("primary_category", "cs.AI"),
        published_at=kwargs.get("published_at", datetime.now(timezone.utc)),
        structured_content=kwargs.get("structured_content", {}),
    )


class _FakeScalars:
    """Wraps a list to provide SQLAlchemy-like .all() interface."""

    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeDBSession:
    def __init__(self, *, scalar_result=None, scalars_result=None):
        self._scalar = scalar_result
        self._scalars = scalars_result or []
        self.added: list = []
        self.deleted: list = []
        self.commit_called = False

    async def scalar(self, statement):
        del statement
        return self._scalar

    async def scalars(self, statement):
        del statement
        return _FakeScalars(self._scalars)

    async def execute(self, statement):
        # simulate scalar_one_or_none for delete
        return FakeExecResult(self._scalar)

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commit_called = True

    async def refresh(self, obj):
        pass


class FakeExecResult:
    def __init__(self, result):
        self._result = result

    def scalar_one_or_none(self):
        return self._result

    def all(self):
        return [self._result] if self._result else []


class TestCompareSerialisation:
    def test_serialise_returns_expected_keys(self):
        comp = _make_comparison(uuid4())
        result = CompareService._serialise(comp)
        assert "id" in result
        assert "title" in result
        assert "paper_ids" in result
        assert "report_content" in result
        assert "created_at" in result
        assert "updated_at" in result

    def test_serialise_handles_none_paper_ids(self):
        comp = _make_comparison(uuid4(), paper_ids=None)
        result = CompareService._serialise(comp)
        assert result["paper_ids"] == []


class TestCompareCreate:
    def test_create_comparison_success(self):
        service = CompareService()
        user = SimpleNamespace(id=uuid4())
        p1 = _make_paper()
        p2 = _make_paper()
        db = FakeDBSession(scalars_result=[p1, p2])
        import asyncio
        result = asyncio.run(service.create_comparison(db, user, "对比测试", [p1.id, p2.id]))
        assert result["title"] == "对比测试"
        assert len(result["paper_ids"]) == 2
        assert db.commit_called

    def test_create_comparison_requires_at_least_2_papers(self):
        service = CompareService()
        user = SimpleNamespace(id=uuid4())
        p1 = _make_paper()
        db = FakeDBSession(scalars_result=[p1])
        import asyncio
        with pytest.raises(ValueError, match="At least 2 valid papers"):
            asyncio.run(service.create_comparison(db, user, "对比测试", [p1.id, uuid4()]))


class TestCompareList:
    def test_list_comparisons_paginated(self):
        service = CompareService()
        user = SimpleNamespace(id=uuid4())
        comp = _make_comparison(user.id, paper_ids=[str(uuid4()), str(uuid4())])
        db = FakeDBSession(scalar_result=1, scalars_result=[comp])
        import asyncio
        items, total = asyncio.run(service.list_comparisons(db, user))
        assert total == 1
        assert len(items) == 1
        assert items[0]["title"] == "对比"


class TestCompareGet:
    def test_get_comparison_not_found(self):
        service = CompareService()
        user = SimpleNamespace(id=uuid4())
        db = FakeDBSession(scalar_result=None)
        import asyncio
        with pytest.raises(ValueError, match="Comparison not found"):
            asyncio.run(service.get_comparison(db, user, uuid4()))

    def test_get_comparison_success(self):
        service = CompareService()
        user = SimpleNamespace(id=uuid4())
        comp = _make_comparison(user.id)
        db = FakeDBSession(scalar_result=comp)
        import asyncio
        result = asyncio.run(service.get_comparison(db, user, comp.id))
        assert result["id"] == str(comp.id)


class TestCompareDelete:
    def test_delete_not_found_raises(self):
        service = CompareService()
        user = SimpleNamespace(id=uuid4())
        db = FakeDBSession(scalar_result=None)
        import asyncio
        with pytest.raises(ValueError, match="Comparison not found"):
            asyncio.run(service.delete_comparison(db, user, uuid4()))

    def test_delete_success(self):
        service = CompareService()
        user = SimpleNamespace(id=uuid4())
        comp = _make_comparison(user.id)
        db = FakeDBSession(scalar_result=comp)
        import asyncio
        asyncio.run(service.delete_comparison(db, user, comp.id))
        assert len(db.deleted) == 1
        assert db.commit_called


class TestGenerateReport:
    def test_generate_report_returns_none_for_less_than_2_papers(self):
        import asyncio
        result = asyncio.run(CompareService._generate_report([], "title"))
        assert result is None
        result = asyncio.run(CompareService._generate_report([{"title": "x"}], "title"))
        assert result is None

    def test_generate_report_returns_none_when_no_llm_configured(self, monkeypatch):
        import asyncio

        # Force get_llm_gateway import to raise, simulating no LLM available
        def _fake_gateway():
            raise RuntimeError("No LLM configured")
        monkeypatch.setattr("app.core.get_llm_gateway", _fake_gateway)

        papers = [{"title": "A", "authors": ["X"], "primary_category": "cs.AI", "abstract": "test", "methods": "", "experiments": ""},
                  {"title": "B", "authors": ["Y"], "primary_category": "cs.AI", "abstract": "test", "methods": "", "experiments": ""}]
        result = asyncio.run(CompareService._generate_report(papers, "对比"))
        assert result is None

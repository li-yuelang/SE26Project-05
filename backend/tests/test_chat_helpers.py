"""Tests for chat service — _conversation_view, _message_view, _time, bootstrap, delete."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.chat import (
    _conversation_view,
    _message_view,
    _time,
    delete_conversation,
    get_conversation,
)
from app.core.exceptions import AppError


# ---------------------------------------------------------------------------
# _time helper
# ---------------------------------------------------------------------------
def test_time_returns_empty_for_none() -> None:
    assert _time(None) == ""


def test_time_returns_utc_formatted() -> None:
    dt = datetime(2026, 7, 10, 14, 30, tzinfo=timezone.utc)
    assert _time(dt) == "14:30"


# ---------------------------------------------------------------------------
# _conversation_view
# ---------------------------------------------------------------------------
def _make_conversation(title="新对话", messages=None):
    return SimpleNamespace(
        id=uuid4(),
        title=title,
        updated_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
        messages=messages or [],
    )


def _make_message(role="user", content="Hello world"):
    class FakeCitations(list):
        pass
    return SimpleNamespace(
        id=uuid4(),
        role=role,
        content=content,
        created_at=datetime(2026, 7, 10, 14, 30, tzinfo=timezone.utc),
        citations=FakeCitations([]),
    )


def test_conversation_view_with_messages() -> None:
    msg = _make_message(content="This is a very long message that exceeds 80 chars for preview generation")
    conv = _make_conversation(messages=[msg])
    result = _conversation_view(conv)
    assert result["title"] == "新对话"
    assert "preview" in result
    assert "date" in result
    assert len(result["preview"]) <= 80


def test_conversation_view_empty_messages() -> None:
    conv = _make_conversation(messages=[])
    result = _conversation_view(conv, messages=[])
    assert result["preview"] == ""


# ---------------------------------------------------------------------------
# _message_view
# ---------------------------------------------------------------------------
def _make_paper(paper_id=None):
    if paper_id is None:
        paper_id = uuid4()
    return SimpleNamespace(
        id=paper_id, arxiv_id="2401.00001", title="A Paper",
    )


def _make_citation(paper_id, chunk_index=1, excerpt="some text"):
    return SimpleNamespace(
        paper_id=paper_id, chunk_index=chunk_index, excerpt=excerpt,
    )


def test_message_view_with_sources() -> None:
    paper = _make_paper()
    citation = _make_citation(paper.id, chunk_index=2, excerpt="Transformer architecture...")
    msg = SimpleNamespace(
        id=uuid4(),
        role="assistant",
        content="Based on the paper...",
        created_at=datetime(2026, 7, 10, 14, 30, tzinfo=timezone.utc),
        citations=[citation],
    )
    papers = {paper.id: paper}
    result = _message_view(msg, papers)
    assert result["role"] == "assistant"
    assert result["content"] == "Based on the paper..."
    assert len(result["sources"]) == 1
    assert result["sources"][0]["paperId"] == str(paper.id)
    assert result["sources"][0]["title"] == "A Paper"
    assert result["sources"][0]["chunkIndex"] == 2


def test_message_view_missing_paper_graceful() -> None:
    paper_id = uuid4()
    citation = _make_citation(paper_id)
    msg = SimpleNamespace(
        id=uuid4(), role="assistant", content="...",
        created_at=datetime.now(timezone.utc), citations=[citation],
    )
    result = _message_view(msg, {})  # paper not in dict
    assert result["sources"][0]["title"] == "来源论文"


# ---------------------------------------------------------------------------
# Fake DB for get/delete conversation
# ---------------------------------------------------------------------------
class FakeChatSession:
    def __init__(self, *, scalar_result):
        self._scalar = scalar_result
        self.deleted: list = []
        self.commit_called = False

    async def scalar(self, statement):
        del statement
        return self._scalar

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commit_called = True


def test_get_conversation_not_found() -> None:
    user = SimpleNamespace(id=uuid4())
    db = FakeChatSession(scalar_result=None)
    import asyncio
    with pytest.raises(AppError, match="对话不存在"):
        asyncio.run(get_conversation(db, user, uuid4()))


def test_get_conversation_success() -> None:
    user = SimpleNamespace(id=uuid4())
    conv = _make_conversation()
    db = FakeChatSession(scalar_result=conv)
    import asyncio
    result = asyncio.run(get_conversation(db, user, conv.id))
    assert result is conv


def test_delete_conversation_success() -> None:
    user = SimpleNamespace(id=uuid4())
    conv = _make_conversation()
    db = FakeChatSession(scalar_result=conv)
    import asyncio
    asyncio.run(delete_conversation(db, user, conv.id))
    assert len(db.deleted) == 1
    assert db.commit_called

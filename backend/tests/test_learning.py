"""Tests for LearningService — all CRUD paths with mock DB sessions."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.learning import LearningService


# ---------------------------------------------------------------------------
# Fake model objects mimicking ORM attribute access
# ---------------------------------------------------------------------------
def _make_bookmark(user_id, paper_id, folder=None):
    bm = SimpleNamespace(
        id=uuid4(), user_id=user_id, paper_id=paper_id, folder=folder,
        created_at=datetime.now(timezone.utc),
    )
    return bm


def _make_note(user_id, paper_id, content="a note", anchor=None, is_public=False):
    return SimpleNamespace(
        id=uuid4(), user_id=user_id, paper_id=paper_id, content=content,
        anchor=anchor, is_public=is_public,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_comment(user_id, paper_id, content="good"):
    return SimpleNamespace(
        id=uuid4(), user_id=user_id, paper_id=paper_id, content=content,
        anchor=None, created_at=datetime.now(timezone.utc),
    )


def _make_reading_history(user_id, paper_id, progress=50):
    return SimpleNamespace(
        id=uuid4(), user_id=user_id, paper_id=paper_id, progress=progress,
        last_read_at=datetime.now(timezone.utc),
    )


def _make_followed_topic(user_id, topic="RAG", keywords=None):
    return SimpleNamespace(
        id=uuid4(), user_id=user_id, topic=topic, keywords=keywords or [],
        created_at=datetime.now(timezone.utc),
    )


def _make_paper(paper_id=None):
    if paper_id is None:
        paper_id = uuid4()
    return SimpleNamespace(
        id=paper_id, title="Test Paper", authors=["A. Author"],
        primary_category="cs.AI", arxiv_id="2401.00001",
    )


# ---------------------------------------------------------------------------
# Fake DB session
# ---------------------------------------------------------------------------
class FakeDBSession:
    """Simulates enough AsyncSession to drive the LearningService methods."""

    def __init__(self, *, scalar_result=None, scalars_result=None, get_result=None):
        self._scalar = scalar_result
        self._scalars = scalars_result or []
        self._get = get_result
        self.added: list = []
        self.deleted: list = []
        self.commit_called = False

    async def scalar(self, statement):
        if "user_papers" in str(statement):
            return self._get
        return self._scalar

    async def scalars(self, statement):
        del statement
        return self._scalars

    async def get(self, model, ident):
        return self._get

    async def execute(self, statement):
        del statement
        return FakeResult(self._scalars)

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commit_called = True

    async def refresh(self, obj):
        pass

    async def rollback(self):
        pass


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBookmarkSerialisation:
    def test_serialise_with_paper(self):
        bm = _make_bookmark(uuid4(), uuid4(), folder="ml")
        paper = _make_paper(bm.paper_id)
        result = LearningService._serialise_bookmark(bm, paper)
        assert result["folder"] == "ml"
        assert result["paper_title"] == "Test Paper"

    def test_serialise_without_paper(self):
        bm = _make_bookmark(uuid4(), uuid4())
        result = LearningService._serialise_bookmark(bm, None)
        assert result["paper_title"] is None


class TestNoteSerialisation:
    def test_serialise_with_paper(self):
        note = _make_note(uuid4(), uuid4(), "my note", anchor={"start": 10})
        paper = _make_paper(note.paper_id)
        result = LearningService._serialise_note(note, paper)
        assert result["content"] == "my note"
        assert result["anchor"] == {"start": 10}
        assert result["paper_title"] == "Test Paper"


class TestCommentSerialisation:
    def test_serialise_with_paper_and_user(self):
        comment = _make_comment(uuid4(), uuid4(), "nice work")
        paper = _make_paper(comment.paper_id)
        user = SimpleNamespace(display_name="Reviewer", username="rev")
        result = LearningService._serialise_comment(comment, paper, user)
        assert result["user_display_name"] == "Reviewer"
        assert result["paper_title"] == "Test Paper"


class TestReadingHistorySerialisation:
    def test_serialise(self):
        rh = _make_reading_history(uuid4(), uuid4(), 80)
        paper = _make_paper(rh.paper_id)
        result = LearningService._serialise_reading_history(rh, paper)
        assert result["progress"] == 80
        assert result["paper_title"] == "Test Paper"


class TestFollowedTopicSerialisation:
    def test_serialise(self):
        ft = _make_followed_topic(uuid4(), "Graph Neural Nets", ["gnn", "graph"])
        result = LearningService._serialise_followed_topic(ft)
        assert result["topic"] == "Graph Neural Nets"
        assert result["keywords"] == ["gnn", "graph"]


class TestBookmarkCRUD:
    def test_add_bookmark_new(self):
        service = LearningService()
        user = SimpleNamespace(id=uuid4())
        paper_id = uuid4()
        paper = _make_paper(paper_id)
        db = FakeDBSession(scalar_result=None, get_result=paper)
        import asyncio
        result = asyncio.run(service.add_bookmark(db, user, paper_id, "favorites"))
        assert db.commit_called
        assert result["folder"] == "favorites"
        assert result["paper_title"] == "Test Paper"

    def test_add_bookmark_paper_not_found(self):
        service = LearningService()
        user = SimpleNamespace(id=uuid4())
        db = FakeDBSession(get_result=None)
        import asyncio
        with pytest.raises(ValueError, match="Paper not found"):
            asyncio.run(service.add_bookmark(db, user, uuid4(), None))

    def test_remove_bookmark_not_found_is_noop(self):
        service = LearningService()
        user = SimpleNamespace(id=uuid4())
        paper_id = uuid4()
        db = FakeDBSession(scalars_result=[])  # empty → scalar_one_or_none returns None
        import asyncio
        # Should not raise
        asyncio.run(service.remove_bookmark(db, user, paper_id))

    def test_remove_bookmark_deletes(self):
        service = LearningService()
        bm = _make_bookmark(uuid4(), uuid4())
        user = SimpleNamespace(id=bm.user_id)
        db = FakeDBSession(scalars_result=[bm])
        import asyncio
        asyncio.run(service.remove_bookmark(db, user, bm.paper_id))
        assert len(db.deleted) == 1
        assert db.commit_called


class TestNoteCRUD:
    def test_create_note(self):
        service = LearningService()
        user = SimpleNamespace(id=uuid4())
        paper_id = uuid4()
        paper = _make_paper(paper_id)
        db = FakeDBSession(get_result=paper)
        import asyncio
        result = asyncio.run(service.create_note(db, user, paper_id, "great paper"))
        assert result["content"] == "great paper"
        assert len(db.added) == 1

    def test_create_note_paper_not_found(self):
        service = LearningService()
        db = FakeDBSession(get_result=None)
        import asyncio
        with pytest.raises(ValueError, match="Paper not found"):
            asyncio.run(service.create_note(db, SimpleNamespace(id=uuid4()), uuid4(), "x"))

    def test_delete_note_not_found(self):
        service = LearningService()
        user = SimpleNamespace(id=uuid4())
        db = FakeDBSession(scalar_result=None)
        import asyncio
        with pytest.raises(ValueError, match="Note not found"):
            asyncio.run(service.delete_note(db, user, uuid4()))

    def test_delete_note_exists(self):
        service = LearningService()
        note = _make_note(uuid4(), uuid4())
        user = SimpleNamespace(id=note.user_id)
        db = FakeDBSession(scalar_result=note)
        import asyncio
        asyncio.run(service.delete_note(db, user, note.id))
        assert len(db.deleted) == 1


class TestCommentCRUD:
    def test_create_comment(self):
        service = LearningService()
        user = SimpleNamespace(id=uuid4(), display_name="Me", username="me")
        paper_id = uuid4()
        paper = _make_paper(paper_id)
        db = FakeDBSession(get_result=paper)
        import asyncio
        result = asyncio.run(service.create_comment(db, user, paper_id, "insightful"))
        assert result["content"] == "insightful"
        assert result["user_display_name"] == "Me"

    def test_delete_comment_not_found(self):
        service = LearningService()
        db = FakeDBSession(scalar_result=None)
        import asyncio
        with pytest.raises(ValueError, match="Comment not found"):
            asyncio.run(service.delete_comment(db, SimpleNamespace(id=uuid4()), uuid4()))


class TestReadingHistory:
    def test_record_reading_new(self):
        service = LearningService()
        user = SimpleNamespace(id=uuid4())
        paper_id = uuid4()
        paper = _make_paper(paper_id)
        db = FakeDBSession(get_result=paper, scalar_result=None)
        import asyncio
        result = asyncio.run(service.record_reading(db, user, paper_id, 30))
        assert result["progress"] == 30
        assert len(db.added) == 1

    def test_record_reading_paper_not_found(self):
        service = LearningService()
        db = FakeDBSession(get_result=None)
        import asyncio
        with pytest.raises(ValueError, match="Paper not found"):
            asyncio.run(service.record_reading(db, SimpleNamespace(id=uuid4()), uuid4(), 10))


class TestFollowedTopics:
    def test_follow_topic_new(self):
        service = LearningService()
        user = SimpleNamespace(id=uuid4())
        db = FakeDBSession(scalar_result=None)
        import asyncio
        result = asyncio.run(service.follow_topic(db, user, "RAG", ["retrieval"]))
        assert result["topic"] == "RAG"
        assert len(db.added) == 1

    def test_unfollow_topic_not_found(self):
        service = LearningService()
        user = SimpleNamespace(id=uuid4())
        db = FakeDBSession(scalar_result=None)
        import asyncio
        with pytest.raises(ValueError, match="Followed topic not found"):
            asyncio.run(service.unfollow_topic(db, user, uuid4()))

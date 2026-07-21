"""Regression tests for cross-user paper, Wiki, and trend boundaries."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.core.exceptions import AppError
from app.schemas.chat import MessageCreate
from app.schemas.wiki import ConceptUpdate
from app.services import chat as chat_service
from app.services import rag
from app.services import trends as trends_module
from app.services import wiki as wiki_service


class EmptyScalars:
    def all(self):
        return []

    def unique(self):
        return self


class CaptureSession:
    def __init__(self):
        self.statements = []

    async def scalars(self, statement):
        self.statements.append(statement)
        return EmptyScalars()

    async def scalar(self, statement):
        self.statements.append(statement)
        return 0


@pytest.mark.asyncio
async def test_rag_query_always_contains_current_user_library_scope(monkeypatch):
    monkeypatch.setattr(rag.settings, "embedding_api_key", "")
    monkeypatch.setattr(rag.settings, "llm_api_key", "")
    db = CaptureSession()
    user_id = uuid4()

    await rag.retrieve(db, "attention", user_id=user_id)

    sql = " ".join(
        str(statement.compile(dialect=postgresql.dialect())) for statement in db.statements
    )
    assert "user_papers" in sql
    assert "user_id" in sql


@pytest.mark.asyncio
async def test_chat_rejects_another_users_explicit_paper(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    conversation = SimpleNamespace(id=uuid4(), title="新对话", messages=[])
    db = CaptureSession()
    async def get_conversation(*args):
        return conversation

    monkeypatch.setattr(chat_service, "get_conversation", get_conversation)

    with pytest.raises(AppError) as error:
        await chat_service.send_message(
            db,
            user,
            conversation.id,
            MessageCreate(content="private", paper_ids=[uuid4()]),
        )

    assert error.value.code == "PAPER_ACCESS_DENIED"
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_wiki_cannot_mutate_shared_concept_for_any_library_member(monkeypatch):
    user_id = uuid4()
    shared_concept = SimpleNamespace(id=uuid4())
    async def visible_concept(*args):
        return shared_concept

    class WikiSession(CaptureSession):
        async def scalar(self, statement):
            self.statements.append(statement)
            return None

    monkeypatch.setattr(wiki_service, "_get_visible_concept", visible_concept)
    db = WikiSession()

    with pytest.raises(AppError) as error:
        await wiki_service.update_concept(
            db, user_id, shared_concept.id, ConceptUpdate(description="overwrite")
        )

    assert error.value.code == "WIKI_READ_ONLY"
    assert error.value.status_code == 403


def test_trend_matching_query_contains_current_user_library_scope():
    service = trends_module.TrendService()
    db = CaptureSession()
    user_id = uuid4()

    import asyncio

    asyncio.run(service._count_matching_papers(db, user_id, ["RAG"]))

    sql = str(db.statements[0].compile(dialect=postgresql.dialect()))
    assert "user_papers" in sql
    assert "user_id" in sql

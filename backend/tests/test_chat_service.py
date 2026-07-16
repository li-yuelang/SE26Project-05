from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas.chat import ConversationCreate
from app.services import chat as chat_service


class NewConversation:
    def __init__(self) -> None:
        self.id = uuid4()
        self.title = "新对话"
        self.updated_at = datetime.now(timezone.utc)

    @property
    def messages(self):
        raise AssertionError("creating a conversation must not lazy-load messages")


class FakeSession:
    def __init__(self) -> None:
        self.added = None

    def add(self, value: object) -> None:
        self.added = value

    async def commit(self) -> None:
        return None

    async def refresh(self, value: object) -> None:
        assert value is self.added


@pytest.mark.asyncio
async def test_create_conversation_does_not_lazy_load_messages(monkeypatch) -> None:
    conversation = NewConversation()
    db = FakeSession()
    monkeypatch.setattr(chat_service, "Conversation", lambda **kwargs: conversation)

    result = await chat_service.create_conversation(
        db,
        SimpleNamespace(id=uuid4()),
        ConversationCreate(),
    )

    assert result == {
        "id": str(conversation.id),
        "title": "新对话",
        "date": conversation.updated_at.date().isoformat(),
        "preview": "",
    }

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500), default="New conversation")
    metadata_extra: Mapped[dict | None] = mapped_column(JSONB)

    user: Mapped[User] = relationship(back_populates="conversations")
    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )


class ChatMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_messages"

    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(100))
    token_usage: Mapped[int | None] = mapped_column(Integer)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    citations: Mapped[list[MessageCitation]] = relationship(back_populates="message", cascade="all, delete-orphan")


class MessageCitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "message_citations"

    message_id: Mapped[UUID] = mapped_column(ForeignKey("chat_messages.id", ondelete="CASCADE"), index=True)
    paper_id: Mapped[UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    chunk_id: Mapped[UUID | None] = mapped_column(ForeignKey("paper_chunks.id", ondelete="SET NULL"))
    chunk_index: Mapped[int | None] = mapped_column(Integer)
    excerpt: Mapped[str | None] = mapped_column(Text)

    message: Mapped[ChatMessage] = relationship(back_populates="citations")

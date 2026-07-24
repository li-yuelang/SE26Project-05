from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.paper import Paper
    from app.models.user import User


class Bookmark(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bookmarks"
    __table_args__ = (UniqueConstraint("user_id", "paper_id", name="uq_user_bookmark"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    paper_id: Mapped[UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    folder: Mapped[str | None] = mapped_column(String(100))

    user: Mapped[User] = relationship(back_populates="bookmarks")
    paper: Mapped[Paper] = relationship(back_populates="bookmarks")


class Note(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notes"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    paper_id: Mapped[UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    anchor: Mapped[dict | None] = mapped_column(JSONB)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="notes")
    paper: Mapped[Paper] = relationship(back_populates="notes")


class Comment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "comments"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    paper_id: Mapped[UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    anchor: Mapped[dict | None] = mapped_column(JSONB)

    user: Mapped[User] = relationship(back_populates="comments")
    paper: Mapped[Paper] = relationship(back_populates="comments")


class ReadingHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reading_history"
    __table_args__ = (UniqueConstraint("user_id", "paper_id", name="uq_user_reading_history"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    paper_id: Mapped[UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    progress: Mapped[int] = mapped_column(default=0)
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="reading_history")
    paper: Mapped[Paper] = relationship(back_populates="readers")


class FollowedTopic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "followed_topics"
    __table_args__ = (UniqueConstraint("user_id", "topic", name="uq_user_followed_topic"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(255), index=True)
    keywords: Mapped[list[str]] = mapped_column(JSONB, default=list)

    user: Mapped[User] = relationship(back_populates="followed_topics")


class PaperComparison(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "paper_comparisons"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    paper_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    report_content: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="comparisons")

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class FetchTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fetch_tasks"

    creator_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    task_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="scheduled", index=True)
    schedule: Mapped[str | None] = mapped_column(String(100))
    keywords: Mapped[list[str]] = mapped_column(JSONB, default=list)
    categories: Mapped[list[str]] = mapped_column(JSONB, default=list)
    execution_log: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    creator: Mapped[User | None] = relationship(back_populates="fetch_tasks")


class TrendTopic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trend_topics"

    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(JSONB, default=list)
    milestone_paper_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    trend_data: Mapped[dict] = mapped_column(JSONB, default=dict)


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_keywords: Mapped[list[str]] = mapped_column(JSONB, default=list)
    categories: Mapped[list[str]] = mapped_column(JSONB, default=list)
    frequency: Mapped[str] = mapped_column(String(32), default="daily")
    enabled: Mapped[bool] = mapped_column(default=True)

    user: Mapped[User] = relationship(back_populates="subscriptions")

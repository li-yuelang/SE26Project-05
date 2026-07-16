from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, Time, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.paper import Paper
    from app.models.user import User


class FetchTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fetch_tasks"

    creator_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), default="未命名抓取任务")
    description: Mapped[str | None] = mapped_column(Text)
    task_type: Mapped[str] = mapped_column(String(32), index=True)
    keywords: Mapped[list[str]] = mapped_column(JSONB, default=list)
    keyword_match_mode: Mapped[str] = mapped_column(String(8), default="or")
    categories: Mapped[list[str]] = mapped_column(JSONB, default=list)
    schedule_kind: Mapped[str] = mapped_column(String(16), default="manual", index=True)
    schedule_time: Mapped[time | None] = mapped_column(Time)
    schedule_weekday: Mapped[int | None] = mapped_column(SmallInteger)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai")
    is_enabled: Mapped[bool] = mapped_column(default=True, index=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    initial_lookback_days: Mapped[int] = mapped_column(Integer, default=7)
    max_results: Mapped[int] = mapped_column(Integer, default=50)
    auto_analyze: Mapped[bool] = mapped_column(default=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    creator: Mapped[User | None] = relationship(back_populates="fetch_tasks")
    runs: Mapped[list[FetchTaskRun]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="FetchTaskRun.created_at.desc()"
    )


class FetchTaskRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fetch_task_runs"
    __table_args__ = (
        Index(
            "uq_fetch_task_active_run",
            "task_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
        Index("ix_fetch_task_runs_task_created", "task_id", "created_at"),
    )

    task_id: Mapped[UUID] = mapped_column(ForeignKey("fetch_tasks.id", ondelete="CASCADE"), index=True)
    trigger_kind: Mapped[str] = mapped_column(String(16), default="manual", index=True)
    config_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    celery_task_id: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    analysis_queued_count: Mapped[int] = mapped_column(Integer, default=0)
    analysis_enqueue_failed_count: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    execution_log: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    task: Mapped[FetchTask] = relationship(back_populates="runs")
    papers: Mapped[list[FetchTaskRunPaper]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="FetchTaskRunPaper.created_at"
    )


class FetchTaskRunPaper(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fetch_task_run_papers"

    run_id: Mapped[UUID] = mapped_column(ForeignKey("fetch_task_runs.id", ondelete="CASCADE"), index=True)
    paper_id: Mapped[UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    result_kind: Mapped[str] = mapped_column(String(16), default="inserted")

    run: Mapped[FetchTaskRun] = relationship(back_populates="papers")
    paper: Mapped[Paper] = relationship()


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

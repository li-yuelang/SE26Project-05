from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

ANALYSIS_RUN_STATUSES = (
    "queued",
    "downloading",
    "parsing",
    "chunking",
    "extracting",
    "embedding",
    "persisting",
    "retry_wait",
    "completed",
    "failed",
    "cancelled",
)
ANALYSIS_RUN_STAGES = (
    "queued",
    "downloading",
    "parsing",
    "chunking",
    "extracting",
    "embedding",
    "persisting",
    "completed",
    "failed",
)
ACTIVE_ANALYSIS_RUN_STATUSES = (
    "queued",
    "downloading",
    "parsing",
    "chunking",
    "extracting",
    "embedding",
    "persisting",
    "retry_wait",
)

if TYPE_CHECKING:
    from app.models.concept import ConceptRelationEvidence, PaperConcept
    from app.models.learning import Bookmark, Comment, Note
    from app.models.user import User


class PaperAnalysisRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Durable state for one immutable paper-analysis attempt.

    ``status`` deliberately contains the current pipeline state so operators
    can inspect a run with one indexed column. ``stage`` is retained as an
    explicit field for retry recovery: a ``retry_wait`` run can remember the
    stage that failed and resume there.
    """

    __tablename__ = "paper_analysis_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'downloading', 'parsing', 'chunking', 'extracting', "
            "'embedding', 'persisting', 'retry_wait', 'completed', 'failed', 'cancelled')",
            name="ck_paper_analysis_run_status",
        ),
        CheckConstraint(
            "stage IN ('queued', 'downloading', 'parsing', 'chunking', 'extracting', "
            "'embedding', 'persisting', 'completed', 'failed')",
            name="ck_paper_analysis_run_stage",
        ),
        Index(
            "uq_paper_analysis_active_run",
            "paper_id",
            unique=True,
            postgresql_where=text(
                "status IN ('queued', 'downloading', 'parsing', 'chunking', 'extracting', "
                "'embedding', 'persisting', 'retry_wait')"
            ),
        ),
        Index("ix_paper_analysis_runs_paper_created", "paper_id", "created_at"),
        Index(
            "uq_paper_analysis_celery_task_id",
            "celery_task_id",
            unique=True,
            postgresql_where=text("celery_task_id IS NOT NULL"),
        ),
    )

    paper_id: Mapped[UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), index=True
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(32), default="queued")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    force: Mapped[bool] = mapped_column(default=False)
    pipeline_version: Mapped[str] = mapped_column(String(128), default="v1")
    analysis_version: Mapped[str] = mapped_column(String(128), default="")
    parser_version: Mapped[str] = mapped_column(String(128), default="pymupdf-pdfplumber-v1")
    prompt_version: Mapped[str] = mapped_column(String(128), default="paper-analysis-v1")
    llm_model: Mapped[str] = mapped_column(String(255), default="")
    embedding_model: Mapped[str] = mapped_column(String(255), default="")
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    retry_after_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    paper: Mapped[Paper] = relationship(
        "Paper", foreign_keys=[paper_id], back_populates="analysis_runs"
    )


class Paper(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "papers"

    # Content is cached globally. User visibility is represented by UserPaper.
    arxiv_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(1000), index=True)
    authors: Mapped[list[str]] = mapped_column(JSONB, default=list)
    abstract: Mapped[str] = mapped_column(Text)
    abstract_embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    categories: Mapped[list[str]] = mapped_column(JSONB, default=list)
    primary_category: Mapped[str | None] = mapped_column(String(100), index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at_source: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pdf_url: Mapped[str] = mapped_column(String(1000))
    arxiv_url: Mapped[str] = mapped_column(String(1000))
    source_content: Mapped[str | None] = mapped_column(Text)
    structured_content: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    parsed_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    metadata_extra: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    active_analysis_run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "paper_analysis_runs.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_papers_active_analysis_run",
        ),
        index=True,
    )

    chunks: Mapped[list[PaperChunk]] = relationship(
        back_populates="paper", cascade="all, delete-orphan", passive_deletes=True
    )
    concepts: Mapped[list[PaperConcept]] = relationship(
        back_populates="paper", cascade="all, delete-orphan", passive_deletes=True
    )
    analysis_runs: Mapped[list[PaperAnalysisRun]] = relationship(
        "PaperAnalysisRun",
        foreign_keys="PaperAnalysisRun.paper_id",
        back_populates="paper",
        cascade="all, delete-orphan",
        order_by="PaperAnalysisRun.created_at.desc()",
    )
    active_analysis_run: Mapped[PaperAnalysisRun | None] = relationship(
        "PaperAnalysisRun",
        foreign_keys=[active_analysis_run_id],
        post_update=True,
    )
    outgoing_citations: Mapped[list[PaperCitation]] = relationship(
        foreign_keys="PaperCitation.source_paper_id",
        back_populates="source_paper",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    incoming_citations: Mapped[list[PaperCitation]] = relationship(
        foreign_keys="PaperCitation.target_paper_id",
        back_populates="target_paper",
        passive_deletes=True,
    )
    bookmarks: Mapped[list[Bookmark]] = relationship(
        back_populates="paper", cascade="all, delete-orphan", passive_deletes=True
    )
    notes: Mapped[list[Note]] = relationship(
        back_populates="paper", cascade="all, delete-orphan", passive_deletes=True
    )
    comments: Mapped[list[Comment]] = relationship(
        back_populates="paper", cascade="all, delete-orphan", passive_deletes=True
    )
    relation_evidence: Mapped[list[ConceptRelationEvidence]] = relationship(
        back_populates="paper", cascade="all, delete-orphan", passive_deletes=True
    )
    library_entries: Mapped[list[UserPaper]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )


class UserPaper(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A paper's membership in one user's personal library."""

    __tablename__ = "user_papers"
    __table_args__ = (UniqueConstraint("user_id", "paper_id", name="uq_user_paper"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    paper_id: Mapped[UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)

    user: Mapped[User] = relationship(back_populates="paper_library")
    paper: Mapped[Paper] = relationship(back_populates="library_entries")


class PaperChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "paper_chunks"
    __table_args__ = (
        UniqueConstraint("analysis_run_id", "chunk_index", name="uq_paper_chunk_run_index"),
        Index("ix_paper_chunks_paper_run", "paper_id", "analysis_run_id"),
    )

    paper_id: Mapped[UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    analysis_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("paper_analysis_runs.id", ondelete="CASCADE"), index=True
    )
    analysis_version: Mapped[str | None] = mapped_column(String(128), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))

    paper: Mapped[Paper] = relationship(back_populates="chunks")


class PaperCitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "paper_citations"
    __table_args__ = (
        UniqueConstraint(
            "source_paper_id",
            "target_paper_id",
            "analysis_run_id",
            name="uq_paper_citation_run",
        ),
        Index("ix_paper_citations_source_run", "source_paper_id", "analysis_run_id"),
    )

    source_paper_id: Mapped[UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    target_paper_id: Mapped[UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    analysis_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("paper_analysis_runs.id", ondelete="CASCADE"), index=True
    )
    analysis_version: Mapped[str | None] = mapped_column(String(128), index=True)
    context: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)

    source_paper: Mapped[Paper] = relationship(foreign_keys=[source_paper_id], back_populates="outgoing_citations")
    target_paper: Mapped[Paper] = relationship(foreign_keys=[target_paper_id], back_populates="incoming_citations")

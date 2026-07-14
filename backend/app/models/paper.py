from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.concept import PaperConcept
    from app.models.learning import Bookmark, Comment, Note, ReadingHistory


class Paper(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "papers"

    arxiv_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(1000), index=True)
    authors: Mapped[list[str]] = mapped_column(JSONB, default=list)
    abstract: Mapped[str] = mapped_column(Text)
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

    chunks: Mapped[list[PaperChunk]] = relationship(back_populates="paper", cascade="all, delete-orphan")
    concepts: Mapped[list[PaperConcept]] = relationship(back_populates="paper", cascade="all, delete-orphan")
    outgoing_citations: Mapped[list[PaperCitation]] = relationship(
        foreign_keys="PaperCitation.source_paper_id", back_populates="source_paper", cascade="all, delete-orphan"
    )
    incoming_citations: Mapped[list[PaperCitation]] = relationship(
        foreign_keys="PaperCitation.target_paper_id", back_populates="target_paper"
    )
    bookmarks: Mapped[list[Bookmark]] = relationship(back_populates="paper", cascade="all, delete-orphan")
    notes: Mapped[list[Note]] = relationship(back_populates="paper", cascade="all, delete-orphan")
    comments: Mapped[list[Comment]] = relationship(back_populates="paper", cascade="all, delete-orphan")
    readers: Mapped[list[ReadingHistory]] = relationship(back_populates="paper", cascade="all, delete-orphan")


class PaperChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "paper_chunks"
    __table_args__ = (UniqueConstraint("paper_id", "chunk_index", name="uq_paper_chunk_index"),)

    paper_id: Mapped[UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))

    paper: Mapped[Paper] = relationship(back_populates="chunks")


class PaperCitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "paper_citations"
    __table_args__ = (UniqueConstraint("source_paper_id", "target_paper_id", name="uq_paper_citation"),)

    source_paper_id: Mapped[UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    target_paper_id: Mapped[UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    context: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)

    source_paper: Mapped[Paper] = relationship(foreign_keys=[source_paper_id], back_populates="outgoing_citations")
    target_paper: Mapped[Paper] = relationship(foreign_keys=[target_paper_id], back_populates="incoming_citations")

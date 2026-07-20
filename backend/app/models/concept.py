from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.paper import Paper


class Concept(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "concepts"

    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    paper_links: Mapped[list[PaperConcept]] = relationship(back_populates="concept", cascade="all, delete-orphan")
    outgoing_relations: Mapped[list[ConceptRelation]] = relationship(
        foreign_keys="ConceptRelation.source_concept_id", back_populates="source_concept", cascade="all, delete-orphan"
    )
    incoming_relations: Mapped[list[ConceptRelation]] = relationship(
        foreign_keys="ConceptRelation.target_concept_id", back_populates="target_concept"
    )


class PaperConcept(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "paper_concepts"
    __table_args__ = (
        UniqueConstraint("paper_id", "concept_id", "analysis_run_id", name="uq_paper_concept_run"),
        Index("ix_paper_concepts_paper_run", "paper_id", "analysis_run_id"),
    )

    paper_id: Mapped[UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    concept_id: Mapped[UUID] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"), index=True)
    analysis_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("paper_analysis_runs.id", ondelete="CASCADE"), index=True
    )
    analysis_version: Mapped[str | None] = mapped_column(String(128), index=True)
    relevance: Mapped[float] = mapped_column(Float, default=1.0)
    evidence: Mapped[str | None] = mapped_column(Text)

    paper: Mapped[Paper] = relationship(back_populates="concepts")
    concept: Mapped[Concept] = relationship(back_populates="paper_links")


class ConceptRelation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "concept_relations"
    __table_args__ = (UniqueConstraint("source_concept_id", "target_concept_id", "relation_type", name="uq_concept_relation"),)

    source_concept_id: Mapped[UUID] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"), index=True)
    target_concept_id: Mapped[UUID] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"), index=True)
    relation_type: Mapped[str] = mapped_column(String(64))
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    source_concept: Mapped[Concept] = relationship(foreign_keys=[source_concept_id], back_populates="outgoing_relations")
    target_concept: Mapped[Concept] = relationship(foreign_keys=[target_concept_id], back_populates="incoming_relations")
    evidence_records: Mapped[list[ConceptRelationEvidence]] = relationship(
        back_populates="relation", cascade="all, delete-orphan"
    )


class ConceptRelationEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Paper-level provenance for a concept relation.

    A relation is shared by the graph, while this table keeps the exact paper,
    excerpt, confidence and analysis version that caused it to be created or
    confirmed.  This makes re-processing auditable without duplicating graph
    edges.
    """

    __tablename__ = "concept_relation_evidence"
    __table_args__ = (
        UniqueConstraint(
            "relation_id", "paper_id", "analysis_version", name="uq_relation_evidence_version"
        ),
    )

    relation_id: Mapped[UUID] = mapped_column(
        ForeignKey("concept_relations.id", ondelete="CASCADE"), index=True
    )
    paper_id: Mapped[UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    analysis_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("paper_analysis_runs.id", ondelete="CASCADE"), index=True
    )
    evidence: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    analysis_version: Mapped[str] = mapped_column(String(128), index=True)

    relation: Mapped[ConceptRelation] = relationship(back_populates="evidence_records")
    paper: Mapped[Paper] = relationship(back_populates="relation_evidence")

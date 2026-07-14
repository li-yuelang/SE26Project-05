"""Add paper-analysis provenance and vector search indexes."""

from alembic import op
from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, inspect, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision = "20260714_0002"
down_revision = "20260714_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The first migration uses metadata.create_all, so the table may already
    # exist on a fresh database.  The inspection keeps this migration safe for
    # both fresh installs and databases created before paper analysis existed.
    inspector = inspect(op.get_bind())
    if "concept_relation_evidence" not in inspector.get_table_names():
        op.create_table(
            "concept_relation_evidence",
            Column("id", PG_UUID(as_uuid=True), primary_key=True),
            Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False),
            Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False),
            Column("relation_id", PG_UUID(as_uuid=True), ForeignKey("concept_relations.id", ondelete="CASCADE"), nullable=False),
            Column("paper_id", PG_UUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
            Column("evidence", Text(), nullable=False),
            Column("confidence", Float(), nullable=False, server_default=text("1.0")),
            Column("analysis_version", String(128), nullable=False),
            UniqueConstraint("relation_id", "paper_id", "analysis_version", name="uq_relation_evidence_version"),
        )
        op.create_index("ix_concept_relation_evidence_relation_id", "concept_relation_evidence", ["relation_id"])
        op.create_index("ix_concept_relation_evidence_paper_id", "concept_relation_evidence", ["paper_id"])
        op.create_index("ix_concept_relation_evidence_analysis_version", "concept_relation_evidence", ["analysis_version"])

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_paper_chunks_embedding_hnsw "
        "ON paper_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_paper_chunks_embedding_hnsw")
    op.execute("DROP TABLE IF EXISTS concept_relation_evidence")

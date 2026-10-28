"""Add lightweight title and abstract embeddings for papers."""

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa

revision = "20260728_0008"
down_revision = "20260727_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The initial migration creates tables from the current model metadata.
    # Fresh databases therefore already contain this column.
    columns = sa.inspect(op.get_bind()).get_columns("papers")
    if not any(column["name"] == "abstract_embedding" for column in columns):
        op.add_column(
            "papers",
            sa.Column("abstract_embedding", Vector(1536), nullable=True),
        )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_papers_abstract_embedding_hnsw "
        "ON papers USING hnsw (abstract_embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_papers_abstract_embedding_hnsw")
    op.drop_column("papers", "abstract_embedding")

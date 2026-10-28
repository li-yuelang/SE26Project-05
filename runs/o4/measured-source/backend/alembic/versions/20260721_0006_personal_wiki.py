"""Add user-owned Wiki concepts without changing shared analysis facts."""

from alembic import op
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint, inspect, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID


revision = "20260721_0006"
down_revision = "20260721_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "user_concepts" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "user_concepts",
        Column("id", PG_UUID(as_uuid=True), primary_key=True),
        Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False),
        Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False),
        Column("user_id", PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        Column("name", String(255), nullable=False),
        Column("description", Text(), nullable=True),
        Column("category", String(100), nullable=True),
        Column("aliases", ARRAY(String()), nullable=False, server_default=text("ARRAY[]::varchar[]")),
        Column("hidden", Boolean(), nullable=False, server_default=text("false")),
        UniqueConstraint("user_id", "name", name="uq_user_concept_name"),
    )
    op.create_index("ix_user_concepts_user_id", "user_concepts", ["user_id"])
    op.create_index("ix_user_concepts_category", "user_concepts", ["category"])


def downgrade() -> None:
    if "user_concepts" in inspect(op.get_bind()).get_table_names():
        op.drop_table("user_concepts")

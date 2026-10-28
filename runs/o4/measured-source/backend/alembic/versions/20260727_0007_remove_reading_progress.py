"""Remove the reading progress feature and its stored history."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260727_0007"
down_revision = "f8080b2d4c79"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS reading_history")


def downgrade() -> None:
    op.create_table(
        "reading_history",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("paper_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "paper_id", name="uq_user_reading_history"),
    )
    op.create_index(
        op.f("ix_reading_history_paper_id"),
        "reading_history",
        ["paper_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reading_history_user_id"),
        "reading_history",
        ["user_id"],
        unique=False,
    )

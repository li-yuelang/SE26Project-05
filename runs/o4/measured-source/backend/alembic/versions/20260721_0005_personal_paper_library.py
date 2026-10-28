"""Add personal-library memberships while retaining a global paper cache."""

from alembic import op
from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint, inspect, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


revision = "20260721_0005"
down_revision = "20260720_0005"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    if "user_papers" not in _tables():
        op.create_table(
            "user_papers",
            Column("id", PG_UUID(as_uuid=True), primary_key=True),
            Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False),
            Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False),
            Column("user_id", PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            Column("paper_id", PG_UUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
            UniqueConstraint("user_id", "paper_id", name="uq_user_paper"),
        )
        op.create_index("ix_user_papers_user_id", "user_papers", ["user_id"])
        op.create_index("ix_user_papers_paper_id", "user_papers", ["paper_id"])

    # Existing papers are assigned to the creator of every task run that
    # returned them. New imports add this same association in the worker.
    op.execute(
        text(
            "INSERT INTO user_papers (id, created_at, updated_at, user_id, paper_id) "
            "SELECT gen_random_uuid(), now(), now(), task.creator_id, link.paper_id "
            "FROM fetch_task_run_papers link "
            "JOIN fetch_task_runs run ON run.id = link.run_id "
            "JOIN fetch_tasks task ON task.id = run.task_id "
            "WHERE task.creator_id IS NOT NULL "
            "ON CONFLICT (user_id, paper_id) DO NOTHING"
        )
    )


def downgrade() -> None:
    if "user_papers" in _tables():
        op.drop_table("user_papers")

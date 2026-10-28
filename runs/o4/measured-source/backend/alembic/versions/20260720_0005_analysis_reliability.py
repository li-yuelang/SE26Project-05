"""Add durable paper-analysis runs, transactional outbox and versioned rows.

This migration is intentionally additive.  The old ``papers.metadata_extra``
analysis object and legacy rows with a NULL ``analysis_run_id`` remain
readable so an installation can be rolled back or repaired in a later,
explicit data-migration step.
"""

from alembic import op
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    inspect,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

revision = "20260720_0005"
down_revision = ("20260716_0004", "20260717_0004")
branch_labels = None
depends_on = None

ACTIVE_RUN_SQL = (
    "status IN ('queued', 'downloading', 'parsing', 'chunking', 'extracting', "
    "'embedding', 'persisting', 'retry_wait')"
)


def _inspector():
    return inspect(op.get_bind())


def _tables() -> set[str]:
    return set(_inspector().get_table_names())


def _columns(table_name: str) -> set[str]:
    return {item["name"] for item in _inspector().get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {item["name"] for item in _inspector().get_indexes(table_name)}


def _unique_constraints(table_name: str) -> set[str]:
    return {item["name"] for item in _inspector().get_unique_constraints(table_name)}


def _foreign_keys(table_name: str) -> set[str | None]:
    return {item.get("name") for item in _inspector().get_foreign_keys(table_name)}


def _create_run_table() -> None:
    if "paper_analysis_runs" in _tables():
        return
    op.create_table(
        "paper_analysis_runs",
        Column("id", PG_UUID(as_uuid=True), primary_key=True),
        Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False),
        Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False),
        Column("paper_id", PG_UUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        Column("celery_task_id", String(255), nullable=True),
        Column("status", String(32), nullable=False, server_default=text("'queued'")),
        Column("stage", String(32), nullable=False, server_default=text("'queued'")),
        Column("attempt", Integer(), nullable=False, server_default=text("0")),
        Column("force", Boolean(), nullable=False, server_default=text("false")),
        Column("pipeline_version", String(128), nullable=False, server_default=text("'v1'")),
        Column("analysis_version", String(128), nullable=False, server_default=text("''")),
        Column("parser_version", String(128), nullable=False, server_default=text("'pymupdf-pdfplumber-v1'")),
        Column("prompt_version", String(128), nullable=False, server_default=text("'paper-analysis-v1'")),
        Column("llm_model", String(255), nullable=False, server_default=text("''")),
        Column("embedding_model", String(255), nullable=False, server_default=text("''")),
        Column("error_code", String(64), nullable=True),
        Column("error_message", Text(), nullable=True),
        Column("requested_by", PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        Column("queued_at", DateTime(timezone=True), server_default=text("now()"), nullable=False),
        Column("started_at", DateTime(timezone=True), nullable=True),
        Column("heartbeat_at", DateTime(timezone=True), nullable=True),
        Column("retry_after_at", DateTime(timezone=True), nullable=True),
        Column("finished_at", DateTime(timezone=True), nullable=True),
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
    )


def _create_run_indexes() -> None:
    existing = _indexes("paper_analysis_runs")
    if "uq_paper_analysis_active_run" not in existing:
        op.create_index(
            "uq_paper_analysis_active_run",
            "paper_analysis_runs",
            ["paper_id"],
            unique=True,
            postgresql_where=text(ACTIVE_RUN_SQL),
        )
    if "ix_paper_analysis_runs_paper_created" not in existing:
        op.create_index(
            "ix_paper_analysis_runs_paper_created",
            "paper_analysis_runs",
            ["paper_id", "created_at"],
        )
    if "uq_paper_analysis_celery_task_id" not in existing:
        op.create_index(
            "uq_paper_analysis_celery_task_id",
            "paper_analysis_runs",
            ["celery_task_id"],
            unique=True,
            postgresql_where=text("celery_task_id IS NOT NULL"),
        )
    if "ix_paper_analysis_runs_paper_id" not in existing:
        op.create_index("ix_paper_analysis_runs_paper_id", "paper_analysis_runs", ["paper_id"])
    if "ix_paper_analysis_runs_requested_by" not in existing:
        op.create_index(
            "ix_paper_analysis_runs_requested_by", "paper_analysis_runs", ["requested_by"]
        )
    if "ix_paper_analysis_runs_heartbeat_at" not in existing:
        op.create_index(
            "ix_paper_analysis_runs_heartbeat_at", "paper_analysis_runs", ["heartbeat_at"]
        )


def _ensure_run_columns() -> None:
    """Make a partially-created run table safe to upgrade again."""

    columns = _columns("paper_analysis_runs")
    if "analysis_version" not in columns:
        op.add_column(
            "paper_analysis_runs",
            Column("analysis_version", String(128), nullable=False, server_default=text("''")),
        )


def _create_outbox_table() -> None:
    if "task_outbox" in _tables():
        return
    op.create_table(
        "task_outbox",
        Column("id", PG_UUID(as_uuid=True), primary_key=True),
        Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False),
        Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False),
        Column("event_key", String(255), nullable=False),
        Column("event_type", String(128), nullable=False),
        Column("aggregate_type", String(64), nullable=False),
        Column("aggregate_id", PG_UUID(as_uuid=True), nullable=False),
        Column(
            "analysis_run_id",
            PG_UUID(as_uuid=True),
            ForeignKey("paper_analysis_runs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        Column("task_id", String(255), nullable=False),
        Column("payload", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
        Column("status", String(16), nullable=False, server_default=text("'pending'")),
        Column("attempts", Integer(), nullable=False, server_default=text("0")),
        Column("available_at", DateTime(timezone=True), server_default=text("now()"), nullable=False),
        Column("locked_at", DateTime(timezone=True), nullable=True),
        Column("sent_at", DateTime(timezone=True), nullable=True),
        Column("last_error", Text(), nullable=True),
        UniqueConstraint("event_key", name="uq_task_outbox_event_key"),
        CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'failed')",
            name="ck_task_outbox_status",
        ),
    )


def _create_outbox_indexes() -> None:
    existing = _indexes("task_outbox")
    if "ix_task_outbox_dispatch" not in existing:
        op.create_index("ix_task_outbox_dispatch", "task_outbox", ["status", "available_at"])
    if "ix_task_outbox_aggregate" not in existing:
        op.create_index(
            "ix_task_outbox_aggregate", "task_outbox", ["aggregate_type", "aggregate_id"]
        )
    if "ix_task_outbox_analysis_run_id" not in existing:
        op.create_index("ix_task_outbox_analysis_run_id", "task_outbox", ["analysis_run_id"])


def _add_version_columns() -> None:
    for table_name in (
        "paper_chunks",
        "paper_concepts",
        "paper_citations",
        "concept_relation_evidence",
    ):
        columns = _columns(table_name)
        if "analysis_run_id" not in columns:
            op.add_column(
                table_name,
                Column(
                    "analysis_run_id",
                    PG_UUID(as_uuid=True),
                    ForeignKey("paper_analysis_runs.id", ondelete="CASCADE"),
                    nullable=True,
                ),
            )
        if table_name != "concept_relation_evidence" and "analysis_version" not in columns:
            op.add_column(table_name, Column("analysis_version", String(128), nullable=True))

    for table_name in (
        "paper_chunks",
        "paper_concepts",
        "paper_citations",
        "concept_relation_evidence",
    ):
        indexes = _indexes(table_name)
        if f"ix_{table_name}_analysis_run_id" not in indexes:
            op.create_index(
                f"ix_{table_name}_analysis_run_id", table_name, ["analysis_run_id"]
            )
        if table_name != "concept_relation_evidence" and f"ix_{table_name}_analysis_version" not in indexes:
            op.create_index(
                f"ix_{table_name}_analysis_version", table_name, ["analysis_version"]
            )


def _replace_legacy_uniques() -> None:
    replacements = {
        "paper_chunks": ("uq_paper_chunk_index", "uq_paper_chunk_run_index", ["analysis_run_id", "chunk_index"]),
        "paper_concepts": ("uq_paper_concept", "uq_paper_concept_run", ["paper_id", "concept_id", "analysis_run_id"]),
        "paper_citations": (
            "uq_paper_citation",
            "uq_paper_citation_run",
            ["source_paper_id", "target_paper_id", "analysis_run_id"],
        ),
    }
    for table_name, (old_name, new_name, columns) in replacements.items():
        constraints = _unique_constraints(table_name)
        if old_name in constraints:
            op.drop_constraint(old_name, table_name, type_="unique")
        if new_name not in _unique_constraints(table_name):
            op.create_unique_constraint(new_name, table_name, columns)


def _add_active_run_pointer() -> None:
    columns = _columns("papers")
    if "active_analysis_run_id" not in columns:
        op.add_column("papers", Column("active_analysis_run_id", PG_UUID(as_uuid=True), nullable=True))
    if "ix_papers_active_analysis_run_id" not in _indexes("papers"):
        op.create_index("ix_papers_active_analysis_run_id", "papers", ["active_analysis_run_id"])
    if "fk_papers_active_analysis_run" not in _foreign_keys("papers"):
        op.create_foreign_key(
            "fk_papers_active_analysis_run",
            "papers",
            "paper_analysis_runs",
            ["active_analysis_run_id"],
            ["id"],
            ondelete="SET NULL",
        )


def upgrade() -> None:
    _create_run_table()
    _ensure_run_columns()
    _create_run_indexes()
    _create_outbox_table()
    _create_outbox_indexes()
    _add_version_columns()
    _replace_legacy_uniques()
    _add_active_run_pointer()


def downgrade() -> None:
    tables = _tables()
    if "papers" in tables and "fk_papers_active_analysis_run" in _foreign_keys("papers"):
        op.drop_constraint("fk_papers_active_analysis_run", "papers", type_="foreignkey")
    if "papers" in tables and "ix_papers_active_analysis_run_id" in _indexes("papers"):
        op.drop_index("ix_papers_active_analysis_run_id", table_name="papers")
    if "papers" in tables and "active_analysis_run_id" in _columns("papers"):
        op.drop_column("papers", "active_analysis_run_id")

    for table_name, (old_name, new_name, columns) in {
        "paper_chunks": ("uq_paper_chunk_index", "uq_paper_chunk_run_index", ["paper_id", "chunk_index"]),
        "paper_concepts": ("uq_paper_concept", "uq_paper_concept_run", ["paper_id", "concept_id"]),
        "paper_citations": (
            "uq_paper_citation",
            "uq_paper_citation_run",
            ["source_paper_id", "target_paper_id"],
        ),
    }.items():
        if table_name not in tables:
            continue
        if new_name in _unique_constraints(table_name):
            op.drop_constraint(new_name, table_name, type_="unique")
        if old_name not in _unique_constraints(table_name):
            op.create_unique_constraint(old_name, table_name, columns)

    for table_name in (
        "paper_chunks",
        "paper_concepts",
        "paper_citations",
        "concept_relation_evidence",
    ):
        if table_name not in tables:
            continue
        for index_name in (
            f"ix_{table_name}_analysis_run_id",
            f"ix_{table_name}_analysis_version",
        ):
            if index_name in _indexes(table_name):
                op.drop_index(index_name, table_name=table_name)
        if "analysis_run_id" in _columns(table_name):
            op.drop_column(table_name, "analysis_run_id")
        if table_name != "concept_relation_evidence" and "analysis_version" in _columns(table_name):
            op.drop_column(table_name, "analysis_version")

    if "task_outbox" in tables:
        op.drop_table("task_outbox")
    if "paper_analysis_runs" in tables:
        op.drop_table("paper_analysis_runs")

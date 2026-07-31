"""Split recurring fetch execution state into durable run history."""

from alembic import op
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    inspect,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

revision = "20260716_0003"
down_revision = "20260714_0002"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}


def _add_task_columns() -> None:
    columns = _columns("fetch_tasks")
    additions = {
        "name": Column("name", String(255), nullable=True),
        "description": Column("description", Text(), nullable=True),
        "keyword_match_mode": Column(
            "keyword_match_mode", String(8), nullable=False, server_default=text("'or'")
        ),
        "schedule_kind": Column(
            "schedule_kind", String(16), nullable=False, server_default=text("'manual'")
        ),
        "schedule_time": Column("schedule_time", Time(), nullable=True),
        "schedule_weekday": Column("schedule_weekday", SmallInteger(), nullable=True),
        "timezone": Column(
            "timezone", String(64), nullable=False, server_default=text("'Asia/Shanghai'")
        ),
        "is_enabled": Column("is_enabled", Boolean(), nullable=False, server_default=text("true")),
        "next_run_at": Column("next_run_at", DateTime(timezone=True), nullable=True),
        "initial_lookback_days": Column(
            "initial_lookback_days", Integer(), nullable=False, server_default=text("7")
        ),
        "max_results": Column("max_results", Integer(), nullable=False, server_default=text("50")),
        "auto_analyze": Column("auto_analyze", Boolean(), nullable=False, server_default=text("false")),
        "last_success_at": Column("last_success_at", DateTime(timezone=True), nullable=True),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("fetch_tasks", column)


def _create_run_tables() -> None:
    table_names = set(inspect(op.get_bind()).get_table_names())
    if "fetch_task_runs" not in table_names:
        op.create_table(
            "fetch_task_runs",
            Column("id", PG_UUID(as_uuid=True), primary_key=True),
            Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False),
            Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False),
            Column("task_id", PG_UUID(as_uuid=True), ForeignKey("fetch_tasks.id", ondelete="CASCADE"), nullable=False),
            Column("trigger_kind", String(16), nullable=False, server_default=text("'manual'")),
            Column("config_snapshot", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
            Column("window_start", DateTime(timezone=True), nullable=True),
            Column("window_end", DateTime(timezone=True), nullable=True),
            Column("celery_task_id", String(255), nullable=True),
            Column("status", String(32), nullable=False, server_default=text("'queued'")),
            Column("candidate_count", Integer(), nullable=False, server_default=text("0")),
            Column("new_count", Integer(), nullable=False, server_default=text("0")),
            Column("duplicate_count", Integer(), nullable=False, server_default=text("0")),
            Column("analysis_queued_count", Integer(), nullable=False, server_default=text("0")),
            Column("analysis_enqueue_failed_count", Integer(), nullable=False, server_default=text("0")),
            Column("page_count", Integer(), nullable=False, server_default=text("0")),
            Column("execution_log", JSONB(), nullable=False, server_default=text("'[]'::jsonb")),
            Column("error_message", Text(), nullable=True),
            Column("started_at", DateTime(timezone=True), nullable=True),
            Column("finished_at", DateTime(timezone=True), nullable=True),
        )
    if "fetch_task_run_papers" not in table_names:
        op.create_table(
            "fetch_task_run_papers",
            Column("id", PG_UUID(as_uuid=True), primary_key=True),
            Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False),
            Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False),
            Column(
                "run_id",
                PG_UUID(as_uuid=True),
                ForeignKey("fetch_task_runs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            Column(
                "paper_id", PG_UUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
            ),
            Column("result_kind", String(16), nullable=False, server_default=text("'inserted'")),
        )

    for table_name, column_name in (
        ("fetch_task_runs", "task_id"),
        ("fetch_task_runs", "created_at"),
        ("fetch_task_runs", "status"),
        ("fetch_task_run_papers", "run_id"),
        ("fetch_task_run_papers", "paper_id"),
    ):
        index_name = f"ix_{table_name}_{column_name}"
        if index_name not in _indexes(table_name):
            op.create_index(index_name, table_name, [column_name])

    run_indexes = _indexes("fetch_task_runs")
    if "uq_fetch_task_active_run" not in run_indexes:
        op.create_index(
            "uq_fetch_task_active_run",
            "fetch_task_runs",
            ["task_id"],
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        )
    if "ix_fetch_task_runs_task_created" not in run_indexes:
        op.create_index(
            "ix_fetch_task_runs_task_created", "fetch_task_runs", ["task_id", "created_at"]
        )


def _migrate_legacy_tasks() -> None:
    columns = _columns("fetch_tasks")
    bind = op.get_bind()

    if "name" in columns:
        bind.execute(
            text(
                "UPDATE fetch_tasks SET name = COALESCE(NULLIF(name, ''), task_type || ' 抓取任务') "
                "WHERE name IS NULL OR name = ''"
            )
        )
    if "status" in columns:
        bind.execute(
            text(
                "UPDATE fetch_tasks SET is_enabled = CASE WHEN status = 'paused' THEN false ELSE true END"
            )
        )
    if "schedule" in columns:
        bind.execute(
            text(
                "UPDATE fetch_tasks SET schedule_kind = CASE "
                "WHEN schedule ILIKE '每天%' THEN 'daily' "
                "WHEN schedule ILIKE '每周%' OR schedule ILIKE '周%' THEN 'weekly' "
                "ELSE 'manual' END"
            )
        )
        bind.execute(
            text(
                "UPDATE fetch_tasks SET schedule_time = "
                "substring(schedule from '([0-9]{1,2}:[0-9]{2})')::time "
                "WHERE schedule ~ '[0-9]{1,2}:[0-9]{2}'"
            )
        )
        bind.execute(
            text(
                "UPDATE fetch_tasks SET schedule_weekday = CASE "
                "WHEN schedule LIKE '%一%' THEN 1 WHEN schedule LIKE '%二%' THEN 2 "
                "WHEN schedule LIKE '%三%' THEN 3 WHEN schedule LIKE '%四%' THEN 4 "
                "WHEN schedule LIKE '%五%' THEN 5 WHEN schedule LIKE '%六%' THEN 6 "
                "WHEN schedule LIKE '%日%' OR schedule LIKE '%天%' THEN 7 ELSE NULL END "
                "WHERE schedule_kind = 'weekly'"
            )
        )

    if {"status", "execution_log", "started_at", "finished_at", "error_message"}.issubset(columns):
        bind.execute(
            text(
                "INSERT INTO fetch_task_runs "
                "(task_id, trigger_kind, config_snapshot, status, execution_log, error_message, "
                "started_at, finished_at, created_at, updated_at) "
                "SELECT f.id, 'initial', jsonb_build_object("
                "'task_type', f.task_type, 'keywords', COALESCE(f.keywords, '[]'::jsonb), "
                "'categories', COALESCE(f.categories, '[]'::jsonb), 'max_results', f.max_results, "
                "'initial_lookback_days', f.initial_lookback_days), "
                "CASE WHEN f.status IN ('failed', 'running') THEN 'failed' ELSE 'succeeded' END, "
                "COALESCE(f.execution_log, '[]'::jsonb), f.error_message, f.started_at, f.finished_at, "
                "COALESCE(f.started_at, f.created_at), COALESCE(f.finished_at, f.updated_at) "
                "FROM fetch_tasks f "
                "WHERE (f.started_at IS NOT NULL OR f.finished_at IS NOT NULL "
                "OR COALESCE(f.execution_log, '[]'::jsonb) <> '[]'::jsonb) "
                "AND NOT EXISTS (SELECT 1 FROM fetch_task_runs r WHERE r.task_id = f.id)"
            )
        )

    if "status" in columns:
        op.drop_column("fetch_tasks", "status")
    for legacy_column in ("schedule", "execution_log", "started_at", "finished_at", "error_message"):
        if legacy_column in columns:
            op.drop_column("fetch_tasks", legacy_column)

    op.alter_column("fetch_tasks", "name", nullable=False)


def upgrade() -> None:
    _add_task_columns()
    _create_run_tables()
    _migrate_legacy_tasks()


def downgrade() -> None:
    op.drop_table("fetch_task_run_papers")
    op.drop_table("fetch_task_runs")
    for column_name in (
        "name",
        "description",
        "keyword_match_mode",
        "schedule_kind",
        "schedule_time",
        "schedule_weekday",
        "timezone",
        "is_enabled",
        "next_run_at",
        "initial_lookback_days",
        "max_results",
        "auto_analyze",
        "last_success_at",
    ):
        if column_name in _columns("fetch_tasks"):
            op.drop_column("fetch_tasks", column_name)

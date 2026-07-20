"""Read-only PostgreSQL/Redis analysis-state diagnostic.

Usage:
    uv run python scripts/analysis_diagnostics.py
    uv run python scripts/analysis_diagnostics.py --per-paper --output report.json

The command never updates application tables or deletes Redis keys.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import redis
from sqlalchemy import create_engine, text

from app.config import settings


def _redis_value_size(client: redis.Redis, key: str) -> int:
    kind = client.type(key)
    if kind == b"list" or kind == "list":
        return int(client.llen(key))
    if kind == b"hash" or kind == "hash":
        return int(client.hlen(key))
    if kind == b"set" or kind == "set":
        return int(client.scard(key))
    if kind == b"zset" or kind == "zset":
        return int(client.zcard(key))
    if kind == b"stream" or kind == "stream":
        return int(client.xlen(key))
    return 1


def _redis_report() -> dict[str, Any]:
    broker = redis.Redis.from_url(settings.redis_broker_url or settings.redis_url)
    result = redis.Redis.from_url(
        settings.redis_result_backend_url or settings.redis_url,
        decode_responses=True,
    )
    broker.ping()
    result.ping()

    result_statuses: Counter[str] = Counter()
    result_keys = 0
    for key in result.scan_iter(match="celery-task-meta-*"):
        result_keys += 1
        raw = result.get(key)
        try:
            result_statuses[str(json.loads(raw or "{}").get("status", "UNKNOWN"))] += 1
        except (TypeError, json.JSONDecodeError):
            result_statuses["INVALID"] += 1

    unacked: dict[str, int] = {}
    for key in broker.scan_iter(match="*unacked*"):
        key_text = key.decode() if isinstance(key, bytes) else str(key)
        unacked[key_text] = _redis_value_size(broker, key)

    queues = {}
    for queue in ("analysis", "default", "arxiv"):
        queues[queue] = int(broker.llen(queue))

    return {
        "broker_ping": True,
        "result_backend_ping": True,
        "result_keys": result_keys,
        "result_statuses": dict(sorted(result_statuses.items())),
        "unacked_keys": unacked,
        "unacked_total": sum(unacked.values()),
        "queue_lengths": queues,
    }


def _postgres_report(include_papers: bool) -> dict[str, Any]:
    url = settings.database_url.replace("+asyncpg", "+psycopg")
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as connection:
        version = str(connection.execute(text("select version()")).scalar_one())
        revision = connection.execute(
            text("select version_num from alembic_version")
        ).scalar_one_or_none()
        extensions = {
            row[0]: row[1]
            for row in connection.execute(
                text(
                    "select extname, extversion from pg_extension "
                    "where extname in ('vector', 'pg_trgm') order by extname"
                )
            ).all()
        }
        schema_objects = {
            name: bool(
                connection.execute(
                    text("select to_regclass(:object_name)"),
                    {"object_name": f"public.{name}"},
                ).scalar_one()
            )
            for name in ("paper_analysis_runs", "task_outbox")
        }
        paper_counts = {
            row[0] or "NULL": int(row[1])
            for row in connection.execute(
                text("select parsed_status, count(*) from papers group by parsed_status order by parsed_status")
            ).all()
        }
        json_counts = {
            row[0] or "NULL": int(row[1])
            for row in connection.execute(
                text(
                    "select coalesce(metadata_extra->'analysis'->>'status', 'NULL'), count(*) "
                    "from papers group by 1 order by 1"
                )
            ).all()
        }
        run_counts = {}
        if schema_objects["paper_analysis_runs"]:
            run_counts = {
                row[0]: int(row[1])
                for row in connection.execute(
                    text(
                        "select status, count(*) from paper_analysis_runs "
                        "group by status order by status"
                    )
                ).all()
            }
        alignment_query = (
            "select p.parsed_status, "
            "coalesce(p.metadata_extra->'analysis'->>'status', 'NULL'), "
            "coalesce(r.status, 'NULL'), count(*) "
            "from papers p "
            "left join lateral (select status from paper_analysis_runs "
            "where paper_id = p.id order by created_at desc limit 1) r on true "
            "group by 1, 2, 3 order by 1, 2, 3"
            if schema_objects["paper_analysis_runs"]
            else "select p.parsed_status, "
            "coalesce(p.metadata_extra->'analysis'->>'status', 'NULL'), "
            "'NULL', count(*) from papers p group by 1, 2 order by 1, 2"
        )
        alignment_rows = [
            {
                "parsed_status": row[0] or "NULL",
                "json_status": row[1] or "NULL",
                "run_status": row[2] or "NULL",
                "count": int(row[3]),
            }
            for row in connection.execute(
                text(alignment_query)
            ).all()
        ]
        chunks = int(connection.execute(text("select count(*) from paper_chunks")).scalar_one())
        papers = []
        if include_papers:
            run_projection = (
                "r.status, r.stage, r.heartbeat_at"
                if schema_objects["paper_analysis_runs"]
                else "NULL, NULL, NULL"
            )
            run_join = (
                "left join lateral (select status, stage, heartbeat_at "
                "from paper_analysis_runs where paper_id = p.id "
                "order by created_at desc limit 1) r on true"
                if schema_objects["paper_analysis_runs"]
                else ""
            )
            papers = [
                {
                    "paper_id": row[0],
                    "parsed_status": row[1],
                    "json_status": row[2],
                    "run_status": row[3],
                    "run_stage": row[4],
                    "heartbeat_at": str(row[5]) if row[5] else None,
                }
                for row in connection.execute(
                    text(
                        "select p.id::text, p.parsed_status, "
                        "coalesce(p.metadata_extra->'analysis'->>'status', 'NULL'), "
                        f"{run_projection} from papers p {run_join} order by p.id"
                    )
                ).all()
            ]

    engine.dispose()
    return {
        "postgres_version": version,
        "alembic_revision": revision,
        "extensions": extensions,
        "schema_objects": schema_objects,
        "paper_parsed_status": paper_counts,
        "paper_json_status": json_counts,
        "analysis_run_status": run_counts,
        "state_alignment": alignment_rows,
        "paper_chunks": chunks,
        "papers": papers,
    }


def build_report(include_papers: bool = False) -> dict[str, Any]:
    return {"postgres": _postgres_report(include_papers), "redis": _redis_report()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only paper-analysis state report")
    parser.add_argument("--per-paper", action="store_true", help="include one row per paper")
    parser.add_argument("--output", type=Path, help="write JSON report to this path")
    args = parser.parse_args()
    report = build_report(include_papers=args.per_paper)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()

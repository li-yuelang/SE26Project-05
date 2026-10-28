"""Create a deterministic synthetic dataset in an explicitly selected local test DB.

Run from backend/: uv run --locked python scripts/seed_o4.py --count 1000
Requires DATABASE_URL and O4_TEST_PASSWORD in the process environment.
No downloads, embedding calls, deletion, or password changes.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.paper import Paper
from app.models.user import User

PREFIX = "o4-synthetic-"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1000)
    args = parser.parse_args()
    if not 1 <= args.count <= 100000:
        parser.error("--count must be between 1 and 100000")
    url = os.environ.get("DATABASE_URL", "")
    if urlsplit(url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("DATABASE_URL must explicitly select a local PostgreSQL test database")
    password = os.environ.get("O4_TEST_PASSWORD", "")
    if len(password) < 12:
        parser.error("Set O4_TEST_PASSWORD to at least 12 characters; it is never printed")

    engine = create_engine(url.replace("+asyncpg", "+psycopg"))
    try:
        with Session(engine) as session:
            user = session.scalar(select(User).where(User.username == "o4_bench"))
            if user is None:
                session.add(User(
                    id=uuid5(NAMESPACE_URL, "papermate:o4:benchmark-user"),
                    username="o4_bench", email="o4_bench@example.com",
                    password_hash=hash_password(password), display_name="O4 benchmark",
                ))
            elif not verify_password(password, user.password_hash):
                raise ValueError("Existing o4_bench account uses a different password; no changes made")
            rows = []
            for i in range(1, args.count + 1):
                arxiv_id = f"{PREFIX}{i:06d}"
                rows.append(dict(
                    id=uuid5(NAMESPACE_URL, "papermate:" + arxiv_id), arxiv_id=arxiv_id,
                    title=f"Synthetic O4 paper {i:06d}: reproducible systems measurements",
                    authors=["Synthetic Author A", "Synthetic Author B"],
                    abstract=(f"Synthetic experimental record {i:06d}. "
                              + "Fixed dataset for local resource measurements. " * 8),
                    categories=["cs.SE"], primary_category="cs.SE", parsed_status="pending",
                    published_at=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=i),
                    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    pdf_url=f"https://example.invalid/{arxiv_id}.pdf",
                    arxiv_url=f"https://example.invalid/{arxiv_id}",
                ))
            for offset in range(0, len(rows), 500):
                session.execute(insert(Paper).values(rows[offset:offset + 500])
                                .on_conflict_do_nothing(index_elements=[Paper.arxiv_id]))
            session.commit()
            synthetic = session.scalar(select(func.count()).select_from(Paper)
                                       .where(Paper.arxiv_id.startswith(PREFIX)))
            total = session.scalar(select(func.count()).select_from(Paper))
            print(json.dumps({"dataset": "o4-synthetic-v1", "requested": args.count,
                              "synthetic_papers": synthetic, "total_papers": total,
                              "username": "o4_bench", "email": "o4_bench@example.com"}))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

"""Compatibility copy of the historical user bio migration.

Some deployed databases recorded this migration as ``20260716_0004`` while
the repository later renamed the same migration to ``20260717_0004`` during a
branch conflict resolution.  Keep both revision identifiers in the graph so
Alembic can upgrade either deployment safely.  The operation is intentionally
idempotent because both revisions add the same column.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260716_0004"
down_revision = "20260716_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "bio" not in columns:
        op.add_column("users", sa.Column("bio", sa.String(length=200), nullable=True))


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "bio" in columns:
        op.drop_column("users", "bio")

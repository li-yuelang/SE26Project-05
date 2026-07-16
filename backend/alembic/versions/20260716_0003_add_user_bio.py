"""Add profile biography to users."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260716_0003"
down_revision = "20260714_0002"
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

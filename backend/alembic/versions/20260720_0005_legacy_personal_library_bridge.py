"""Bridge a legacy personal-library revision retained by deployed databases."""


revision = "20260720_0005"
down_revision = "20260717_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """The legacy schema is already present on databases stamped with this revision."""


def downgrade() -> None:
    """No schema changes were introduced by this compatibility bridge."""


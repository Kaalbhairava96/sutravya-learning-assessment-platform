"""Establish the initial migration baseline before domain tables are approved."""

from alembic import op

revision = "0001_backend_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No candidate or exam schema is in scope for the backend foundation milestone.
    pass


def downgrade() -> None:
    pass

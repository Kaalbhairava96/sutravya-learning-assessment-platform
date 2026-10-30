"""Mark pre-launch verification challenges and registrations as internal tests.

Revision ID: 0005_internal_test_flags
Revises: 0004_registration_accounts
"""

from alembic import context, op
import sqlalchemy as sa


revision = "0005_internal_test_flags"
down_revision = "0004_registration_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_registrations_candidate_event", "registrations", type_="unique")
    op.add_column(
        "verification_challenges",
        sa.Column("is_internal_test", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "registrations",
        sa.Column("is_internal_test", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index(
        "uq_registrations_candidate_event_official",
        "registrations",
        ["candidate_id", "event_key"],
        unique=True,
        postgresql_where=sa.text("is_internal_test IS FALSE"),
        sqlite_where=sa.text("is_internal_test = 0"),
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError(
            "Cannot render this downgrade offline: live checks are required to avoid reclassifying internal test data."
        )
    bind = op.get_bind()
    internal_registrations = bind.execute(
        sa.text("SELECT 1 FROM registrations WHERE is_internal_test IS TRUE LIMIT 1")
    ).first()
    internal_challenges = bind.execute(
        sa.text("SELECT 1 FROM verification_challenges WHERE is_internal_test IS TRUE LIMIT 1")
    ).first()
    if internal_registrations is not None or internal_challenges is not None:
        raise RuntimeError("Cannot remove internal-test markers while internal test data exists.")
    op.drop_index("uq_registrations_candidate_event_official", table_name="registrations")
    op.create_unique_constraint(
        "uq_registrations_candidate_event", "registrations", ["candidate_id", "event_key"]
    )
    op.drop_column("registrations", "is_internal_test")
    op.drop_column("verification_challenges", "is_internal_test")

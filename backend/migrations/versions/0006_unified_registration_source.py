"""Record unified registration provenance while preserving legacy test records.

Revision ID: 0006_reg_source
Revises: 0005_internal_test_flags
"""

from alembic import context, op
import sqlalchemy as sa


revision = "0006_reg_source"
down_revision = "0005_internal_test_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not context.is_offline_mode():
        duplicate = op.get_bind().execute(
            sa.text(
                "SELECT candidate_id, event_key FROM registrations "
                "WHERE is_internal_test IS FALSE "
                "GROUP BY candidate_id, event_key HAVING count(*) > 1 LIMIT 1"
            )
        ).first()
        if duplicate is not None:
            raise RuntimeError(
                "Cannot unify registrations while duplicate candidate/event rows exist; "
                "review and resolve them without deleting candidate data before retrying."
            )

    source_default = sa.text("'public_registration'")
    op.add_column(
        "registrations",
        sa.Column("registration_source", sa.String(length=32), server_default=source_default, nullable=False),
    )
    op.add_column(
        "verification_challenges",
        sa.Column("registration_source", sa.String(length=32), server_default=source_default, nullable=False),
    )
    op.execute(
        "UPDATE registrations SET registration_source = 'legacy_internal_test' WHERE is_internal_test IS TRUE"
    )
    op.execute(
        "UPDATE verification_challenges SET registration_source = 'legacy_internal_test' WHERE is_internal_test IS TRUE"
    )
    op.create_check_constraint(
        "ck_registrations_registration_source",
        "registrations",
        "registration_source IN ('team_prelaunch', 'public_registration', 'legacy_internal_test')",
    )
    op.create_check_constraint(
        "ck_verification_challenges_registration_source",
        "verification_challenges",
        "registration_source IN ('team_prelaunch', 'public_registration', 'legacy_internal_test')",
    )
    # Migration 0005's partial unique index already prevents duplicate official
    # registrations while allowing a preserved legacy test row beside one real row.


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError(
            "Cannot render this downgrade offline: live checks are required to preserve team pre-launch provenance."
        )
    bind = op.get_bind()
    team_registrations = bind.execute(
        sa.text("SELECT 1 FROM registrations WHERE registration_source = 'team_prelaunch' LIMIT 1")
    ).first()
    legacy_registrations = bind.execute(
        sa.text("SELECT 1 FROM registrations WHERE registration_source = 'legacy_internal_test' LIMIT 1")
    ).first()
    team_challenges = bind.execute(
        sa.text("SELECT 1 FROM verification_challenges WHERE registration_source = 'team_prelaunch' LIMIT 1")
    ).first()
    legacy_challenges = bind.execute(
        sa.text("SELECT 1 FROM verification_challenges WHERE registration_source = 'legacy_internal_test' LIMIT 1")
    ).first()
    if any(value is not None for value in (
        team_registrations, legacy_registrations, team_challenges, legacy_challenges,
    )):
        raise RuntimeError("Cannot downgrade while team or legacy registration-source classifications exist.")
    op.drop_constraint("ck_verification_challenges_registration_source", "verification_challenges", type_="check")
    op.drop_constraint("ck_registrations_registration_source", "registrations", type_="check")
    op.drop_column("verification_challenges", "registration_source")
    op.drop_column("registrations", "registration_source")

"""Classify historical internal records without changing identities or IDs.

Revision ID: 0007_legacy_classification
Revises: 0006_reg_source
"""

from alembic import context, op
import sqlalchemy as sa


revision = "0007_legacy_classification"
down_revision = "0006_reg_source"
branch_labels = None
depends_on = None

_REGISTRATION_CHECK = "ck_registrations_registration_source"
_CHALLENGE_CHECK = "ck_verification_challenges_registration_source"
_SOURCE_VALUES = "registration_source IN ('team_prelaunch', 'public_registration', 'legacy_internal_test')"


def _source_rows_exist(bind, table: str) -> bool:
    row = bind.execute(
        sa.text(
            f"SELECT 1 FROM {table} "
            "WHERE registration_source = 'legacy_internal_test' OR is_internal_test IS TRUE LIMIT 1"
        )
    ).first()
    return row is not None


def upgrade() -> None:
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())
        expected = {
            "registrations": _REGISTRATION_CHECK,
            "verification_challenges": _CHALLENGE_CHECK,
        }
        for table, constraint_name in expected.items():
            check_names = {item["name"] for item in inspector.get_check_constraints(table)}
            if constraint_name not in check_names:
                raise RuntimeError(
                    f"Cannot classify legacy records: expected source check {constraint_name} is missing."
                )

    # Remove the older two-value checks before assigning the new classification.
    op.drop_constraint(_CHALLENGE_CHECK, "verification_challenges", type_="check")
    op.drop_constraint(_REGISTRATION_CHECK, "registrations", type_="check")
    op.execute(
        "UPDATE registrations SET registration_source = 'legacy_internal_test' "
        "WHERE is_internal_test IS TRUE"
    )
    op.execute(
        "UPDATE verification_challenges SET registration_source = 'legacy_internal_test' "
        "WHERE is_internal_test IS TRUE"
    )
    op.create_check_constraint(_REGISTRATION_CHECK, "registrations", _SOURCE_VALUES)
    op.create_check_constraint(_CHALLENGE_CHECK, "verification_challenges", _SOURCE_VALUES)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError(
            "Cannot render this downgrade offline: live checks are required to preserve legacy classifications."
        )
    bind = op.get_bind()
    if _source_rows_exist(bind, "registrations") or _source_rows_exist(bind, "verification_challenges"):
        raise RuntimeError(
            "Cannot downgrade while legacy internal-test records exist; their source classification would be lost."
        )

    op.drop_constraint(_CHALLENGE_CHECK, "verification_challenges", type_="check")
    op.drop_constraint(_REGISTRATION_CHECK, "registrations", type_="check")
    op.create_check_constraint(
        _REGISTRATION_CHECK,
        "registrations",
        "registration_source IN ('team_prelaunch', 'public_registration', 'legacy_internal_test')",
    )
    op.create_check_constraint(
        _CHALLENGE_CHECK,
        "verification_challenges",
        "registration_source IN ('team_prelaunch', 'public_registration', 'legacy_internal_test')",
    )

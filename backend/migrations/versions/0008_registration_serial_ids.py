"""Create the global serial sequence used in new Registration IDs.

Revision ID: 0008_registration_serial_ids
Revises: 0007_legacy_classification
"""

from alembic import context, op
import sqlalchemy as sa


revision = "0008_registration_serial_ids"
down_revision = "0007_legacy_classification"
branch_labels = None
depends_on = None

SEQUENCE_NAME = "registration_id_serial_seq"
MAX_SERIAL = 99_999_999_999


def upgrade() -> None:
    op.execute(
        f"CREATE SEQUENCE {SEQUENCE_NAME} START WITH 1 INCREMENT BY 1 "
        f"MINVALUE 1 MAXVALUE {MAX_SERIAL} NO CYCLE"
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError(
            "Cannot render this downgrade offline: live checks are required to prevent losing allocated Registration IDs."
        )

    bind = op.get_bind()
    new_format_registration = bind.execute(
        sa.text(
            "SELECT 1 FROM registrations "
            "WHERE registration_id ~ '^SUT-[0-9]{4}/[0-9]{2}/[0-9]{2}-[0-9]{11}$' "
            "LIMIT 1"
        )
    ).first()
    last_value, is_called = bind.execute(
        sa.text(f"SELECT last_value, is_called FROM {SEQUENCE_NAME}")
    ).one()
    if new_format_registration is not None or is_called or last_value > 1:
        raise RuntimeError(
            "Cannot drop the Registration ID sequence: new-format IDs or allocated serials may exist."
        )
    op.execute(f"DROP SEQUENCE {SEQUENCE_NAME}")

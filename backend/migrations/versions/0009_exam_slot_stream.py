"""Add an explicit assessment stream to each exam slot.

Revision ID: 0009_exam_slot_stream
Revises: 0008_registration_serial_ids
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_exam_slot_stream"
down_revision = "0008_registration_serial_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("exam_slots", sa.Column("stream", sa.String(length=32), nullable=True))
    op.create_check_constraint(
        "ck_exam_slots_stream_approved",
        "exam_slots",
        "stream IS NULL OR stream IN ('paramedical', 'nursing', 'mbbs_1st_year')",
    )
    op.create_index(
        "ix_exam_slots_event_stream_start",
        "exam_slots",
        ["event_key", "stream", "starts_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_exam_slots_event_stream_start", table_name="exam_slots")
    op.drop_constraint("ck_exam_slots_stream_approved", "exam_slots", type_="check")
    op.drop_column("exam_slots", "stream")

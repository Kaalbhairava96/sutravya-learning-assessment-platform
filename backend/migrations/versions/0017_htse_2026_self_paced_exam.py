"""Create the three self-paced HTSE 2026 exam windows.

Revision ID: 0017_htse_2026_self_paced_exam
Revises: 0016_admin_password_resets
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from alembic import context, op
import sqlalchemy as sa


revision = "0017_htse_2026_self_paced_exam"
down_revision = "0016_admin_password_resets"
branch_labels = None
depends_on = None

EVENT_KEY = "BHC-2026"
STREAMS = ("nursing", "paramedical", "pharmacy")
IST = ZoneInfo("Asia/Kolkata")


def upgrade() -> None:
    offline = context.is_offline_mode()
    connection = op.get_bind()

    op.drop_constraint("ck_exam_slots_stream_approved", "exam_slots", type_="check")
    op.create_check_constraint(
        "ck_exam_slots_stream_approved",
        "exam_slots",
        "stream IS NULL OR stream IN ('nursing', 'paramedical', 'pharmacy')",
    )

    if not offline:
        existing = connection.execute(
            sa.text("SELECT stream FROM exam_slots WHERE event_key = 'BHC-2026' AND stream IN ('nursing', 'paramedical', 'pharmacy')")
        ).fetchall()
        if existing:
            raise RuntimeError("HTSE 2026 stream slots already exist; refusing to create duplicates.")

    for stream in STREAMS:
        # op.execute works both with a live connection and Alembic SQL output.
        op.execute(sa.text(f"""
            INSERT INTO exam_slots (id, event_key, stream, starts_at, ends_at, capacity, created_at)
            VALUES (
                gen_random_uuid(),
                'BHC-2026',
                '{stream}',
                TIMESTAMPTZ '2026-12-06 10:00:00+05:30',
                TIMESTAMPTZ '2026-12-06 18:00:00+05:30',
                1500,
                CURRENT_TIMESTAMP
            )
        """))

    # Assign existing active Nursing/Paramedical/Pharmacy candidates. Older
    # Medical history is preserved and deliberately not reclassified.
    op.execute(sa.text("""
        UPDATE registrations AS r
        SET exam_slot_id = s.id
        FROM exam_slots AS s
        WHERE r.event_key = 'BHC-2026'
          AND r.is_internal_test IS FALSE
          AND r.status = 'active'
          AND r.registration_source IN ('public_registration', 'team_prelaunch')
          AND r.stream = s.stream
          AND s.event_key = 'BHC-2026'
          AND r.stream IN ('nursing', 'paramedical', 'pharmacy')
    """))


def downgrade() -> None:
    offline = context.is_offline_mode()
    connection = op.get_bind()
    if not offline:
        has_attempts = connection.execute(
            sa.text("""
                SELECT 1 FROM exam_attempts a
                JOIN exam_slots s ON s.id = a.exam_slot_id
                WHERE s.event_key = 'BHC-2026'
                  AND s.stream IN ('nursing', 'paramedical', 'pharmacy')
                LIMIT 1
            """)
        ).first()
        if has_attempts:
            raise RuntimeError("Cannot downgrade HTSE 2026 exam windows after candidate attempts exist.")

    op.execute(sa.text("""
        UPDATE registrations SET exam_slot_id = NULL
        WHERE exam_slot_id IN (
            SELECT id FROM exam_slots
            WHERE event_key = 'BHC-2026'
              AND stream IN ('nursing', 'paramedical', 'pharmacy')
        )
    """))
    op.execute(sa.text("""
        DELETE FROM exam_slots
        WHERE event_key = 'BHC-2026'
          AND stream IN ('nursing', 'paramedical', 'pharmacy')
    """))
    op.drop_constraint("ck_exam_slots_stream_approved", "exam_slots", type_="check")
    op.create_check_constraint(
        "ck_exam_slots_stream_approved",
        "exam_slots",
        "stream IS NULL OR stream IN ('paramedical', 'nursing', 'mbbs_ug', 'mbbs_pg', 'mbbs_1st_year')",
    )

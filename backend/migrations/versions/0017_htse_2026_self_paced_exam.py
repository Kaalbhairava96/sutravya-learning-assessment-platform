"""Create the three self-paced HTSE 2026 exam windows.

Official question banks are provisioned directly into the protected database;
practice questions and answer keys remain separate from the candidate exam API.

Revision ID: 0017_htse_2026_self_paced_exam
Revises: 0016_admin_password_resets
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from alembic import op
import sqlalchemy as sa


revision = "0017_htse_2026_self_paced_exam"
down_revision = "0016_admin_password_resets"
branch_labels = None
depends_on = None

EVENT_KEY = "BHC-2026"
STREAMS = ("nursing", "paramedical", "pharmacy")
IST = ZoneInfo("Asia/Kolkata")


def upgrade() -> None:
    connection = op.get_bind()
    op.drop_constraint("ck_exam_slots_stream_approved", "exam_slots", type_="check")
    op.create_check_constraint(
        "ck_exam_slots_stream_approved",
        "exam_slots",
        "stream IS NULL OR stream IN ('nursing', 'paramedical', 'pharmacy')",
    )

    existing = connection.execute(
        sa.text("SELECT stream FROM exam_slots WHERE event_key = :event_key AND stream IN ('nursing', 'paramedical', 'pharmacy')"),
        {"event_key": EVENT_KEY},
    ).fetchall()
    if existing:
        raise RuntimeError("HTSE 2026 stream slots already exist; refusing to create duplicates.")

    now = datetime.now(timezone.utc)
    starts_at = datetime(2026, 12, 6, 10, 0, tzinfo=IST).astimezone(timezone.utc)
    ends_at = datetime(2026, 12, 6, 18, 0, tzinfo=IST).astimezone(timezone.utc)
    for stream in STREAMS:
        connection.execute(
            sa.text("""
                INSERT INTO exam_slots (id, event_key, stream, starts_at, ends_at, capacity, created_at)
                VALUES (gen_random_uuid(), :event_key, :stream, :starts_at, :ends_at, :capacity, :created_at)
            """),
            {
                "event_key": EVENT_KEY, "stream": stream,
                "starts_at": starts_at, "ends_at": ends_at,
                "capacity": 1500, "created_at": now,
            },
        )

    # Attach existing active Nursing and Paramedical candidates to the new window.
    # Historic Medical registrations remain untouched and are not reclassified.
    connection.execute(
        sa.text("""
            UPDATE registrations AS r
            SET exam_slot_id = s.id
            FROM exam_slots AS s
            WHERE r.event_key = :event_key
              AND r.is_internal_test IS FALSE
              AND r.status = 'active'
              AND r.registration_source IN ('public_registration', 'team_prelaunch')
              AND r.stream = s.stream
              AND s.event_key = :event_key
              AND r.stream IN ('nursing', 'paramedical', 'pharmacy')
        """),
        {"event_key": EVENT_KEY},
    )


def downgrade() -> None:
    connection = op.get_bind()
    has_attempts = connection.execute(
        sa.text("""
            SELECT 1 FROM exam_attempts a
            JOIN exam_slots s ON s.id = a.exam_slot_id
            WHERE s.event_key = :event_key AND s.stream IN ('nursing', 'paramedical', 'pharmacy')
            LIMIT 1
        """),
        {"event_key": EVENT_KEY},
    ).first()
    if has_attempts:
        raise RuntimeError("Cannot downgrade HTSE 2026 exam windows after candidate attempts exist.")

    connection.execute(
        sa.text("""
            UPDATE registrations SET exam_slot_id = NULL
            WHERE exam_slot_id IN (
                SELECT id FROM exam_slots
                WHERE event_key = :event_key AND stream IN ('nursing', 'paramedical', 'pharmacy')
            )
        """),
        {"event_key": EVENT_KEY},
    )
    connection.execute(
        sa.text("DELETE FROM exam_slots WHERE event_key = :event_key AND stream IN ('nursing', 'paramedical', 'pharmacy')"),
        {"event_key": EVENT_KEY},
    )
    op.drop_constraint("ck_exam_slots_stream_approved", "exam_slots", type_="check")
    op.create_check_constraint(
        "ck_exam_slots_stream_approved",
        "exam_slots",
        "stream IS NULL OR stream IN ('paramedical', 'nursing', 'mbbs_ug', 'mbbs_pg', 'mbbs_1st_year')",
    )

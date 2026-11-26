"""Seed the three HTSE 2026 self-paced exam streams.

Revision ID: 0017_htse_2026_self_paced_exam
Revises: 0016_admin_password_resets
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
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
SOURCE_PATH = Path(__file__).resolve().parents[3] / "assets" / "htse_2026_question_banks.json"


def upgrade() -> None:
    connection = op.get_bind()

    op.drop_constraint("ck_exam_slots_stream_approved", "exam_slots", type_="check")
    op.create_check_constraint(
        "ck_exam_slots_stream_approved",
        "exam_slots",
        "stream IS NULL OR stream IN ('nursing', 'paramedical', 'pharmacy')",
    )

    if not SOURCE_PATH.is_file():
        raise RuntimeError(f"HTSE 2026 question-bank seed file is missing: {SOURCE_PATH}")
    banks = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    if set(banks) != set(STREAMS):
        raise RuntimeError("HTSE seed must contain exactly Nursing, Paramedical and Pharmacy banks.")

    now = datetime.now(timezone.utc)
    starts_at = datetime(2026, 12, 6, 10, 0, tzinfo=IST).astimezone(timezone.utc)
    ends_at = datetime(2026, 12, 6, 18, 0, tzinfo=IST).astimezone(timezone.utc)
    slot_ids: dict[str, str] = {}
    bank_ids: dict[str, str] = {}

    existing_slots = connection.execute(
        sa.text("SELECT stream FROM exam_slots WHERE event_key = :event_key AND stream IN :streams"),
        {"event_key": EVENT_KEY, "streams": STREAMS},
    ).fetchall()
    if existing_slots:
        raise RuntimeError("HTSE 2026 stream slots already exist; refusing to seed duplicate slots.")

    for stream in STREAMS:
        bank_data = banks[stream]
        questions = bank_data.get("questions", [])
        subjects = bank_data.get("subjects", [])
        if len(questions) != 100 or len(subjects) != 5:
            raise RuntimeError(f"{stream} bank must contain 100 questions across five subjects.")
        counts = {subject["key"]: 0 for subject in subjects}
        for question in questions:
            if question.get("subjectKey") not in counts:
                raise RuntimeError(f"Unknown subject key in {stream} bank: {question.get('subjectKey')}")
            if len(question.get("options", [])) != 4 or question.get("answer") not in (0, 1, 2, 3):
                raise RuntimeError(f"Invalid MCQ structure in {stream} bank: {question.get('id')}")
            counts[question["subjectKey"]] += 1
        if any(count != 20 for count in counts.values()):
            raise RuntimeError(f"{stream} bank must contain exactly 20 questions in each subject.")

        bank_id = str(uuid4())
        slot_id = str(uuid4())
        bank_ids[stream] = bank_id
        slot_ids[stream] = slot_id
        connection.execute(
            sa.text("""
                INSERT INTO question_banks (id, bank_code, title, description, created_at, updated_at)
                VALUES (:id, :bank_code, :title, :description, :created_at, :updated_at)
            """),
            {
                "id": bank_id,
                "bank_code": stream,
                "title": f"{bank_data['label']} HTSE 2026",
                "description": bank_data.get("description") or "HTSE 2026 original 100-question stream bank; five common subjects with 20 questions each.",
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            sa.text("""
                INSERT INTO scoring_rules
                    (id, question_bank_id, rule_code, correct_points, incorrect_points, unanswered_points, created_at, updated_at)
                VALUES
                    (:id, :question_bank_id, 'htse_2026', 1, -0.25, 0, :created_at, :updated_at)
            """),
            {"id": str(uuid4()), "question_bank_id": bank_id, "created_at": now, "updated_at": now},
        )
        connection.execute(
            sa.text("""
                INSERT INTO exam_slots (id, event_key, stream, starts_at, ends_at, capacity, created_at)
                VALUES (:id, :event_key, :stream, :starts_at, :ends_at, :capacity, :created_at)
            """),
            {
                "id": slot_id, "event_key": EVENT_KEY, "stream": stream,
                "starts_at": starts_at, "ends_at": ends_at, "capacity": 1500, "created_at": now,
            },
        )

        question_rows = []
        option_rows = []
        for item in questions:
            question_id = str(uuid4())
            question_rows.append({
                "id": question_id,
                "question_bank_id": bank_id,
                "question_text": item["question"].strip(),
                "category": item.get("topic"),
                "section": item["subjectKey"],
                "difficulty": item.get("difficulty", "moderate").lower(),
                "time_limit_seconds": 20,
                "explanation": item.get("explanation"),
                "source_reference": f"SUTRAVYA original HTSE 2026 {stream} bank",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            })
            for position, option_text in enumerate(item["options"]):
                option_rows.append({
                    "id": str(uuid4()),
                    "question_id": question_id,
                    "identifier": "ABCD"[position],
                    "option_text": option_text.strip(),
                    "is_correct": position == item["answer"],
                })

        connection.execute(
            sa.text("""
                INSERT INTO questions
                    (id, question_bank_id, question_text, category, section, difficulty,
                     time_limit_seconds, explanation, source_reference, is_active, created_at, updated_at)
                VALUES
                    (:id, :question_bank_id, :question_text, :category, :section, :difficulty,
                     :time_limit_seconds, :explanation, :source_reference, :is_active, :created_at, :updated_at)
            """),
            question_rows,
        )
        connection.execute(
            sa.text("""
                INSERT INTO answer_options (id, question_id, identifier, option_text, is_correct)
                VALUES (:id, :question_id, :identifier, :option_text, :is_correct)
            """),
            option_rows,
        )

    # New registrations in the three public streams are automatically attached to
    # their stream window during email verification. Assign existing eligible
    # Nursing and Paramedical candidates without changing historic Medical rows.
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
    in_progress_or_submitted = connection.execute(
        sa.text("""
            SELECT 1 FROM exam_attempts a
            JOIN exam_slots s ON s.id = a.exam_slot_id
            WHERE s.event_key = :event_key AND s.stream IN ('nursing', 'paramedical', 'pharmacy')
            LIMIT 1
        """),
        {"event_key": EVENT_KEY},
    ).first()
    if in_progress_or_submitted:
        raise RuntimeError("Cannot downgrade seeded HTSE streams after candidate attempts exist.")

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
        sa.text("""
            DELETE FROM answer_options WHERE question_id IN (
                SELECT q.id FROM questions q
                JOIN question_banks b ON b.id = q.question_bank_id
                WHERE b.bank_code IN ('nursing', 'paramedical', 'pharmacy')
            )
        """)
    )
    connection.execute(
        sa.text("""
            DELETE FROM questions WHERE question_bank_id IN (
                SELECT id FROM question_banks WHERE bank_code IN ('nursing', 'paramedical', 'pharmacy')
            )
        """)
    )
    connection.execute(
        sa.text("""
            DELETE FROM scoring_rules WHERE question_bank_id IN (
                SELECT id FROM question_banks WHERE bank_code IN ('nursing', 'paramedical', 'pharmacy')
            )
        """)
    )
    connection.execute(
        sa.text("DELETE FROM question_banks WHERE bank_code IN ('nursing', 'paramedical', 'pharmacy')")
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

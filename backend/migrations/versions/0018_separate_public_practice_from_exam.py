"""Remove public practice MCQs from confidential official exam banks.

The candidate practice papers remain in the static mock-test assets. They must
never double as the official exam, because their correct answers are public.
The bank shells and approved scoring rules are retained so the organiser can
load confidential papers through the authenticated admin import endpoint.

Revision ID: 0018_sep_practice_exam
Revises: 0017_htse_2026_self_paced_exam
"""
from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "0018_sep_practice_exam"
down_revision = "0017_htse_2026_self_paced_exam"
branch_labels = None
depends_on = None

STREAMS = ("nursing", "paramedical", "pharmacy")


def upgrade() -> None:
    # Fail closed if any candidate has already started an attempt against these
    # question banks. No answer-key changes are allowed after exam attempts exist.
    if not context.is_offline_mode():
        connection = op.get_bind()
        attempt = connection.execute(sa.text("""
            SELECT 1
            FROM exam_attempts a
            JOIN question_banks b ON b.id = a.question_bank_id
            WHERE b.bank_code IN ('nursing', 'paramedical', 'pharmacy')
            LIMIT 1
        """)).first()
        if attempt is not None:
            raise RuntimeError(
                "Cannot separate practice and official question banks after an exam attempt exists."
            )

    op.execute(sa.text("""
        DELETE FROM answer_options
        WHERE question_id IN (
            SELECT q.id
            FROM questions q
            JOIN question_banks b ON b.id = q.question_bank_id
            WHERE b.bank_code IN ('nursing', 'paramedical', 'pharmacy')
        )
    """))
    op.execute(sa.text("""
        DELETE FROM questions
        WHERE question_bank_id IN (
            SELECT id FROM question_banks
            WHERE bank_code IN ('nursing', 'paramedical', 'pharmacy')
        )
    """))
    op.execute(sa.text("""
        UPDATE question_banks
        SET description = 'Official HTSE 2026 confidential examination bank. Awaiting approved organiser import; public practice MCQs are maintained separately.',
            updated_at = CURRENT_TIMESTAMP
        WHERE bank_code IN ('nursing', 'paramedical', 'pharmacy')
    """))


def downgrade() -> None:
    # The deleted rows were public practice copies and must not be restored as
    # official assessment questions. Keep offline SQL generation deterministic,
    # but refuse an online downgrade rather than silently re-expose practice keys.
    if context.is_offline_mode():
        op.execute(sa.text("-- irreversible: confidential exam bank must be re-imported after downgrade"))
        return
    raise RuntimeError(
        "This security migration is intentionally irreversible. Re-import an approved confidential question bank."
    )

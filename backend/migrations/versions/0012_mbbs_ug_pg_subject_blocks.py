"""Allow MBBS UG/PG slots and subject-specific section keys."""
from alembic import op

revision = "0012_mbbs_ug_pg_subject_blocks"
down_revision = "0011_qualinova_paid_registration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_exam_slots_stream_approved", "exam_slots", type_="check")
    op.create_check_constraint(
        "ck_exam_slots_stream_approved",
        "exam_slots",
        "stream IS NULL OR stream IN ('paramedical', 'nursing', 'mbbs_ug', 'mbbs_pg', 'mbbs_1st_year')",
    )
    op.drop_constraint("ck_questions_approved_section", "questions", type_="check")
    op.create_check_constraint(
        "ck_questions_approved_section",
        "questions",
        "length(trim(section)) > 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_questions_approved_section", "questions", type_="check")
    op.create_check_constraint(
        "ck_questions_approved_section",
        "questions",
        "section IN ('anatomy', 'physiology', 'biology', 'quantitative_reasoning', 'english_communication')",
    )
    op.drop_constraint("ck_exam_slots_stream_approved", "exam_slots", type_="check")
    op.create_check_constraint(
        "ck_exam_slots_stream_approved",
        "exam_slots",
        "stream IS NULL OR stream IN ('paramedical', 'nursing', 'mbbs_1st_year')",
    )

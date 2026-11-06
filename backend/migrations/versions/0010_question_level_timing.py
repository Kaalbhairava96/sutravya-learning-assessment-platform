"""Add per-question timing, sections and candidate presentation snapshots.

Revision ID: 0010_question_level_timing
Revises: 0009_exam_slot_stream
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_question_level_timing"
down_revision = "0009_exam_slot_stream"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("section", sa.String(length=40), nullable=False, server_default="biology"))
    op.add_column("questions", sa.Column("difficulty", sa.String(length=20), nullable=False, server_default="easy"))
    op.add_column("questions", sa.Column("time_limit_seconds", sa.Integer(), nullable=False, server_default="20"))
    op.create_check_constraint(
        "ck_questions_approved_section", "questions",
        "section IN ('anatomy', 'physiology', 'biology', 'quantitative_reasoning', 'english_communication')",
    )
    op.create_check_constraint(
        "ck_questions_difficulty", "questions", "difficulty IN ('easy', 'moderate')"
    )
    op.create_check_constraint(
        "ck_questions_time_limit", "questions", "time_limit_seconds BETWEEN 15 AND 60"
    )
    op.add_column("candidate_responses", sa.Column("position", sa.Integer(), nullable=True))
    op.add_column("candidate_responses", sa.Column("presented_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("candidate_responses", sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("candidate_responses", sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("candidate_responses", sa.Column("option_order", sa.JSON(), nullable=True))
    op.create_unique_constraint(
        "uq_responses_attempt_position", "candidate_responses", ["attempt_id", "position"]
    )
    op.create_index(
        "ix_candidate_responses_attempt_position", "candidate_responses", ["attempt_id", "position"]
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_responses_attempt_position", table_name="candidate_responses")
    op.drop_constraint("uq_responses_attempt_position", "candidate_responses", type_="unique")
    op.drop_column("candidate_responses", "option_order")
    op.drop_column("candidate_responses", "answered_at")
    op.drop_column("candidate_responses", "deadline_at")
    op.drop_column("candidate_responses", "presented_at")
    op.drop_column("candidate_responses", "position")
    op.drop_constraint("ck_questions_time_limit", "questions", type_="check")
    op.drop_constraint("ck_questions_difficulty", "questions", type_="check")
    op.drop_constraint("ck_questions_approved_section", "questions", type_="check")
    op.drop_column("questions", "time_limit_seconds")
    op.drop_column("questions", "difficulty")
    op.drop_column("questions", "section")

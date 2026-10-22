"""Add core candidate, assessment, scoring, result, and audit storage.

Revision ID: 0002_core_application_schema
Revises: 0001_backend_foundation
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_core_application_schema"
down_revision = "0001_backend_foundation"
branch_labels = None
depends_on = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_candidates"),
    )

    op.create_table(
        "question_banks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bank_code", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_question_banks"),
        sa.UniqueConstraint("bank_code", name="uq_question_banks_bank_code"),
    )

    op.create_table(
        "exam_slots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_key", sa.String(length=100), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_exam_slots_end_after_start"),
        sa.CheckConstraint("capacity IS NULL OR capacity > 0", name="ck_exam_slots_positive_capacity"),
        sa.PrimaryKeyConstraint("id", name="pk_exam_slots"),
    )
    op.create_index("ix_exam_slots_event_start", "exam_slots", ["event_key", "starts_at"], unique=False)

    op.create_table(
        "admin_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role_key", sa.String(length=80), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.false(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_admin_users"),
    )
    op.create_index("uq_admin_users_email_lower", "admin_users", [sa.text("lower(email)")], unique=True)

    op.create_table(
        "registrations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("event_key", sa.String(length=100), nullable=False),
        sa.Column("exam_slot_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name="fk_registrations_candidate_id_candidates", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["exam_slot_id"], ["exam_slots.id"], name="fk_registrations_exam_slot_id_exam_slots", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_registrations"),
        sa.UniqueConstraint("candidate_id", "event_key", name="uq_registrations_candidate_event"),
    )
    op.create_index("ix_registrations_exam_slot_id", "registrations", ["exam_slot_id"], unique=False)

    op.create_table(
        "questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("question_bank_id", sa.Uuid(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("source_reference", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.false(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["question_bank_id"], ["question_banks.id"], name="fk_questions_question_bank_id_question_banks", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_questions"),
        sa.UniqueConstraint("question_bank_id", "id", name="uq_questions_bank_id_id"),
    )
    op.create_index("ix_questions_question_bank_id", "questions", ["question_bank_id"], unique=False)

    op.create_table(
        "answer_options",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("identifier", sa.String(length=8), nullable=False),
        sa.Column("option_text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], name="fk_answer_options_question_id_questions", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_answer_options"),
        sa.UniqueConstraint("question_id", "id", name="uq_answer_options_question_id_id"),
        sa.UniqueConstraint("question_id", "identifier", name="uq_answer_options_question_identifier"),
    )
    op.create_index(
        "uq_answer_options_one_correct_per_question",
        "answer_options",
        ["question_id"],
        unique=True,
        postgresql_where=sa.text("is_correct IS TRUE"),
    )

    op.create_table(
        "scoring_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("question_bank_id", sa.Uuid(), nullable=False),
        sa.Column("rule_code", sa.String(length=80), nullable=False),
        sa.Column("correct_points", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("incorrect_points", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("unanswered_points", sa.Numeric(precision=10, scale=3), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["question_bank_id"], ["question_banks.id"], name="fk_scoring_rules_question_bank_id_question_banks", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_scoring_rules"),
        sa.UniqueConstraint("question_bank_id", "rule_code", name="uq_scoring_rules_bank_code"),
    )

    op.create_table(
        "exam_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("registration_id", sa.Uuid(), nullable=False),
        sa.Column("exam_slot_id", sa.Uuid(), nullable=False),
        sa.Column("question_bank_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("attempt_number > 0", name="ck_exam_attempts_positive_number"),
        sa.ForeignKeyConstraint(["exam_slot_id"], ["exam_slots.id"], name="fk_exam_attempts_exam_slot_id_exam_slots", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["question_bank_id"], ["question_banks.id"], name="fk_exam_attempts_question_bank_id_question_banks", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["registration_id"], ["registrations.id"], name="fk_exam_attempts_registration_id_registrations", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_exam_attempts"),
        sa.UniqueConstraint("registration_id", "attempt_number", name="uq_attempts_registration_number"),
    )
    op.create_index("ix_exam_attempts_exam_slot_id", "exam_attempts", ["exam_slot_id"], unique=False)

    op.create_table(
        "candidate_responses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("selected_option_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["attempt_id"], ["exam_attempts.id"], name="fk_candidate_responses_attempt_id_exam_attempts", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], name="fk_candidate_responses_question_id_questions", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["question_id", "selected_option_id"],
            ["answer_options.question_id", "answer_options.id"],
            name="fk_responses_option_belongs_to_question",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_candidate_responses"),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_responses_attempt_question"),
    )
    op.create_index("ix_candidate_responses_question_id", "candidate_responses", ["question_id"], unique=False)

    op.create_table(
        "results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("approved_by_admin_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["approved_by_admin_id"], ["admin_users.id"], name="fk_results_approved_by_admin_id_admin_users", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["attempt_id"], ["exam_attempts.id"], name="fk_results_attempt_id_exam_attempts", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_results"),
        sa.UniqueConstraint("attempt_id", name="uq_results_attempt_id"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_admin_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["actor_admin_id"], ["admin_users.id"], name="fk_audit_events_actor_admin_id_admin_users", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"], unique=False)
    op.create_index("ix_audit_events_actor_admin_id", "audit_events", ["actor_admin_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_events_actor_admin_id", table_name="audit_events")
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("results")
    op.drop_index("ix_candidate_responses_question_id", table_name="candidate_responses")
    op.drop_table("candidate_responses")
    op.drop_index("ix_exam_attempts_exam_slot_id", table_name="exam_attempts")
    op.drop_table("exam_attempts")
    op.drop_table("scoring_rules")
    op.drop_index("uq_answer_options_one_correct_per_question", table_name="answer_options")
    op.drop_table("answer_options")
    op.drop_index("ix_questions_question_bank_id", table_name="questions")
    op.drop_table("questions")
    op.drop_index("ix_registrations_exam_slot_id", table_name="registrations")
    op.drop_table("registrations")
    op.drop_index("uq_admin_users_email_lower", table_name="admin_users")
    op.drop_table("admin_users")
    op.drop_index("ix_exam_slots_event_start", table_name="exam_slots")
    op.drop_table("exam_slots")
    op.drop_table("question_banks")
    op.drop_table("candidates")

"""Private persistence models for future assessment workflows.

These models define storage only. They do not implement registration, exam delivery,
scoring, authorization, or result-release behavior.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid


class Base(DeclarativeBase):
    """Metadata root imported by Alembic for model discovery."""

    metadata = MetaData(
        naming_convention={
            "pk": "pk_%(table_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        }
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=func.now(),
    )


class Candidate(TimestampMixin, Base):
    __tablename__ = "candidates"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    # Contact fields are nullable until QualiNova approves the registration form.
    full_name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(32))

    registrations: Mapped[list["Registration"]] = relationship(back_populates="candidate")


class QuestionBank(TimestampMixin, Base):
    __tablename__ = "question_banks"
    __table_args__ = (UniqueConstraint("bank_code", name="uq_question_banks_bank_code"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    bank_code: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    questions: Mapped[list["Question"]] = relationship(back_populates="question_bank")
    attempts: Mapped[list["ExamAttempt"]] = relationship(back_populates="question_bank")
    scoring_rules: Mapped[list["ScoringRule"]] = relationship(back_populates="question_bank")


class ExamSlot(Base):
    __tablename__ = "exam_slots"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_exam_slots_end_after_start"),
        CheckConstraint("capacity IS NULL OR capacity > 0", name="ck_exam_slots_positive_capacity"),
        Index("ix_exam_slots_event_start", "event_key", "starts_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    event_key: Mapped[str] = mapped_column(String(100), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Capacity stays unset until QualiNova confirms concurrency limits.
    capacity: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    registrations: Mapped[list["Registration"]] = relationship(
        back_populates="exam_slot", foreign_keys="Registration.exam_slot_id"
    )
    attempts: Mapped[list["ExamAttempt"]] = relationship(
        back_populates="exam_slot", foreign_keys="ExamAttempt.exam_slot_id"
    )


class Registration(TimestampMixin, Base):
    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint("candidate_id", "event_key", name="uq_registrations_candidate_event"),
        Index("ix_registrations_exam_slot_id", "exam_slot_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("candidates.id", ondelete="RESTRICT", name="fk_registrations_candidate_id_candidates"),
        nullable=False,
    )
    event_key: Mapped[str] = mapped_column(String(100), nullable=False)
    exam_slot_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("exam_slots.id", ondelete="RESTRICT", name="fk_registrations_exam_slot_id_exam_slots"),
    )
    status: Mapped[str | None] = mapped_column(String(40))

    candidate: Mapped[Candidate] = relationship(back_populates="registrations")
    exam_slot: Mapped[ExamSlot | None] = relationship(
        back_populates="registrations", foreign_keys=[exam_slot_id]
    )
    attempts: Mapped[list["ExamAttempt"]] = relationship(back_populates="registration")


class Question(TimestampMixin, Base):
    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("question_bank_id", "id", name="uq_questions_bank_id_id"),
        Index("ix_questions_question_bank_id", "question_bank_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    question_bank_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_banks.id", ondelete="RESTRICT", name="fk_questions_question_bank_id_question_banks"),
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(120))
    explanation: Mapped[str | None] = mapped_column(Text)
    source_reference: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())

    question_bank: Mapped[QuestionBank] = relationship(back_populates="questions")
    options: Mapped[list["AnswerOption"]] = relationship(
        back_populates="question", order_by="AnswerOption.identifier"
    )
    responses: Mapped[list["CandidateResponse"]] = relationship(back_populates="question")


class AnswerOption(Base):
    __tablename__ = "answer_options"
    __table_args__ = (
        UniqueConstraint("question_id", "identifier", name="uq_answer_options_question_identifier"),
        UniqueConstraint("question_id", "id", name="uq_answer_options_question_id_id"),
        # At most one correct option per question; application validation must also require one.
        Index(
            "uq_answer_options_one_correct_per_question",
            "question_id",
            unique=True,
            postgresql_where=text("is_correct IS TRUE"),
            sqlite_where=text("is_correct = 1"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="RESTRICT", name="fk_answer_options_question_id_questions"),
        nullable=False,
    )
    identifier: Mapped[str] = mapped_column(String(8), nullable=False)
    option_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Private server-side scoring data. Never include this field in candidate API schemas.
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())

    question: Mapped[Question] = relationship(back_populates="options")


class ScoringRule(TimestampMixin, Base):
    __tablename__ = "scoring_rules"
    __table_args__ = (
        UniqueConstraint("question_bank_id", "rule_code", name="uq_scoring_rules_bank_code"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    question_bank_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_banks.id", ondelete="RESTRICT", name="fk_scoring_rules_question_bank_id_question_banks"),
        nullable=False,
    )
    rule_code: Mapped[str] = mapped_column(String(80), nullable=False)
    # Nullable and without defaults: values await approved marks/negative-marking policy.
    correct_points: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    incorrect_points: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    unanswered_points: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))

    question_bank: Mapped[QuestionBank] = relationship(back_populates="scoring_rules")


class ExamAttempt(TimestampMixin, Base):
    __tablename__ = "exam_attempts"
    __table_args__ = (
        UniqueConstraint("registration_id", "attempt_number", name="uq_attempts_registration_number"),
        CheckConstraint("attempt_number > 0", name="ck_exam_attempts_positive_number"),
        Index("ix_exam_attempts_exam_slot_id", "exam_slot_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    registration_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("registrations.id", ondelete="RESTRICT", name="fk_exam_attempts_registration_id_registrations"),
        nullable=False,
    )
    exam_slot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("exam_slots.id", ondelete="RESTRICT", name="fk_exam_attempts_exam_slot_id_exam_slots"),
        nullable=False,
    )
    question_bank_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_banks.id", ondelete="RESTRICT", name="fk_exam_attempts_question_bank_id_question_banks"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str | None] = mapped_column(String(40))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    registration: Mapped[Registration] = relationship(back_populates="attempts")
    exam_slot: Mapped[ExamSlot] = relationship(back_populates="attempts", foreign_keys=[exam_slot_id])
    question_bank: Mapped[QuestionBank] = relationship(back_populates="attempts")
    responses: Mapped[list["CandidateResponse"]] = relationship(back_populates="attempt")
    result: Mapped["Result | None"] = relationship(back_populates="attempt", uselist=False)


class CandidateResponse(TimestampMixin, Base):
    __tablename__ = "candidate_responses"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_responses_attempt_question"),
        ForeignKeyConstraint(
            ["question_id", "selected_option_id"],
            ["answer_options.question_id", "answer_options.id"],
            name="fk_responses_option_belongs_to_question",
        ),
        Index("ix_candidate_responses_question_id", "question_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    attempt_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("exam_attempts.id", ondelete="RESTRICT", name="fk_candidate_responses_attempt_id_exam_attempts"),
        nullable=False,
    )
    question_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="RESTRICT", name="fk_candidate_responses_question_id_questions"),
        nullable=False,
    )
    # Null is allowed for an unanswered question; composite FK binds selections to their question.
    selected_option_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))

    attempt: Mapped[ExamAttempt] = relationship(back_populates="responses")
    question: Mapped[Question] = relationship(back_populates="responses")


class AdminUser(TimestampMixin, Base):
    __tablename__ = "admin_users"
    __table_args__ = (
        Index("uq_admin_users_email_lower", text("lower(email)"), unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    # Store only a password hash; password authentication is not implemented in this milestone.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_key: Mapped[str | None] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())

    approved_results: Mapped[list["Result"]] = relationship(
        back_populates="approved_by_admin", foreign_keys="Result.approved_by_admin_id"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="actor")


class Result(TimestampMixin, Base):
    __tablename__ = "results"
    __table_args__ = (UniqueConstraint("attempt_id", name="uq_results_attempt_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    attempt_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("exam_attempts.id", ondelete="RESTRICT", name="fk_results_attempt_id_exam_attempts"),
        nullable=False,
    )
    score: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    approved_by_admin_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="RESTRICT", name="fk_results_approved_by_admin_id_admin_users"),
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    attempt: Mapped[ExamAttempt] = relationship(back_populates="result")
    approved_by_admin: Mapped[AdminUser | None] = relationship(
        back_populates="approved_results", foreign_keys=[approved_by_admin_id]
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_created_at", "created_at"),
        Index("ix_audit_events_actor_admin_id", "actor_admin_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    actor_admin_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="RESTRICT", name="fk_audit_events_actor_admin_id_admin_users"),
    )
    request_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(80))
    target_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    actor: Mapped[AdminUser | None] = relationship(back_populates="audit_events")

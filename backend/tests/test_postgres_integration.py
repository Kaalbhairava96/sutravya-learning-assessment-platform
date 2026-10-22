"""PostgreSQL-only integrity checks for the approved disposable test database.

Run from backend/ with APP_ENV=test and DATABASE_URL set to the exact guarded
target. Every test uses synthetic records inside an outer transaction that is
rolled back; expected integrity failures are isolated with savepoints.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from alembic.runtime.migration import MigrationContext
from sqlalchemy import func, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.config import Settings
from app.database import create_database_engine
from app.models import (
    AnswerOption,
    Candidate,
    CandidateResponse,
    ExamAttempt,
    ExamSlot,
    Question,
    QuestionBank,
    Registration,
)


class PostgreSQLIntegrityTests(unittest.TestCase):
    """Exercise constraints on PostgreSQL without committing fixture data."""

    engine: Engine

    @classmethod
    def setUpClass(cls) -> None:
        # Do not read backend/.env: integration runs must explicitly configure
        # the current process and pass the same Settings guard as migrations.
        settings = Settings.from_env(
            environ=dict(os.environ),
            dotenv_path=Path(os.devnull),
        )
        if settings.app_env != "test":
            raise RuntimeError("PostgreSQL integration tests require APP_ENV=test.")

        cls.engine = create_database_engine(settings, poolclass=NullPool)
        try:
            with cls.engine.connect() as connection:
                database_name, database_user = connection.execute(
                    text("SELECT current_database(), current_user")
                ).one()
                if database_name != "sutravya_m3_test":
                    raise RuntimeError("PostgreSQL integration tests connected to an unapproved database.")
                if database_user != "sutravya_m3_test":
                    raise RuntimeError("PostgreSQL integration tests connected as an unapproved database user.")

                revision = MigrationContext.configure(connection).get_current_revision()
                if revision != "0002_core_application_schema":
                    raise RuntimeError("PostgreSQL integration tests require schema revision 0002_core_application_schema.")
        except Exception:
            cls.engine.dispose()
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        cls.engine.dispose()

    def setUp(self) -> None:
        self.connection: Connection = self.engine.connect()
        self.outer_transaction = self.connection.begin()
        self.session = Session(
            bind=self.connection,
            join_transaction_mode="create_savepoint",
        )
        self.addCleanup(self.rollback_test_fixture)

        suffix = uuid4().hex
        now = datetime.now(timezone.utc)
        self.candidate = Candidate(full_name="Synthetic Integration Candidate")
        self.bank = QuestionBank(bank_code=f"PG-TEST-{suffix}", title="Synthetic integration bank")
        self.slot = ExamSlot(
            event_key=f"PG-TEST-EVENT-{suffix}",
            starts_at=now,
            ends_at=now + timedelta(hours=1),
        )
        self.session.add_all([self.candidate, self.bank, self.slot])
        self.session.flush()

        self.registration = Registration(
            candidate_id=self.candidate.id,
            event_key=self.slot.event_key,
            exam_slot_id=self.slot.id,
        )
        self.question_one = Question(
            question_bank_id=self.bank.id,
            question_text="Synthetic PostgreSQL integration prompt one.",
        )
        self.question_two = Question(
            question_bank_id=self.bank.id,
            question_text="Synthetic PostgreSQL integration prompt two.",
        )
        self.session.add_all([self.registration, self.question_one, self.question_two])
        self.session.flush()

        self.option_one_correct = AnswerOption(
            question_id=self.question_one.id,
            identifier="A",
            option_text="Synthetic choice one A.",
            is_correct=True,
        )
        self.option_one_other = AnswerOption(
            question_id=self.question_one.id,
            identifier="B",
            option_text="Synthetic choice one B.",
            is_correct=False,
        )
        self.option_two_correct = AnswerOption(
            question_id=self.question_two.id,
            identifier="A",
            option_text="Synthetic choice two A.",
            is_correct=True,
        )
        self.session.add_all(
            [self.option_one_correct, self.option_one_other, self.option_two_correct]
        )
        self.session.flush()

        self.attempt = ExamAttempt(
            registration_id=self.registration.id,
            exam_slot_id=self.slot.id,
            question_bank_id=self.bank.id,
            attempt_number=1,
        )
        self.session.add(self.attempt)
        self.session.flush()
        self.response = CandidateResponse(
            attempt_id=self.attempt.id,
            question_id=self.question_one.id,
            selected_option_id=self.option_one_correct.id,
        )
        self.session.add(self.response)
        self.session.flush()

    def rollback_test_fixture(self) -> None:
        self.session.close()
        if self.outer_transaction.is_active:
            self.outer_transaction.rollback()
        self.connection.close()

    def assert_constraint_violation(self, constraint_name: str, record: object) -> None:
        with self.assertRaises(IntegrityError) as raised:
            with self.session.begin_nested():
                self.session.add(record)
                self.session.flush()

        diagnostic = getattr(raised.exception.orig, "diag", None)
        self.assertIsNotNone(diagnostic, "Expected a PostgreSQL diagnostic for the integrity violation.")
        self.assertEqual(diagnostic.constraint_name, constraint_name)

    def test_foreign_key_rejects_registration_with_unknown_candidate(self) -> None:
        invalid_registration = Registration(
            candidate_id=uuid4(),
            event_key=f"PG-INVALID-{uuid4().hex}",
            exam_slot_id=None,
        )
        self.assert_constraint_violation(
            "fk_registrations_candidate_id_candidates",
            invalid_registration,
        )

    def test_duplicate_candidate_registration_is_rejected(self) -> None:
        duplicate = Registration(
            candidate_id=self.candidate.id,
            event_key=self.registration.event_key,
            exam_slot_id=self.slot.id,
        )
        self.assert_constraint_violation("uq_registrations_candidate_event", duplicate)

    def test_duplicate_attempt_number_for_registration_is_rejected(self) -> None:
        duplicate = ExamAttempt(
            registration_id=self.registration.id,
            exam_slot_id=self.slot.id,
            question_bank_id=self.bank.id,
            attempt_number=1,
        )
        self.assert_constraint_violation("uq_attempts_registration_number", duplicate)

    def test_duplicate_response_for_attempt_and_question_is_rejected(self) -> None:
        duplicate = CandidateResponse(
            attempt_id=self.attempt.id,
            question_id=self.question_one.id,
            selected_option_id=self.option_one_other.id,
        )
        self.assert_constraint_violation("uq_responses_attempt_question", duplicate)

    def test_response_rejects_option_belonging_to_another_question(self) -> None:
        second_attempt = ExamAttempt(
            registration_id=self.registration.id,
            exam_slot_id=self.slot.id,
            question_bank_id=self.bank.id,
            attempt_number=2,
        )
        self.session.add(second_attempt)
        self.session.flush()

        mismatched_response = CandidateResponse(
            attempt_id=second_attempt.id,
            question_id=self.question_one.id,
            selected_option_id=self.option_two_correct.id,
        )
        self.assert_constraint_violation(
            "fk_responses_option_belongs_to_question",
            mismatched_response,
        )

    def test_partial_unique_index_allows_at_most_one_correct_option(self) -> None:
        second_correct_option = AnswerOption(
            question_id=self.question_one.id,
            identifier="C",
            option_text="Synthetic additional choice.",
            is_correct=True,
        )
        self.assert_constraint_violation(
            "uq_answer_options_one_correct_per_question",
            second_correct_option,
        )

    def test_savepoint_rolls_back_violation_and_outer_transaction_is_usable(self) -> None:
        duplicate = Registration(
            candidate_id=self.candidate.id,
            event_key=self.registration.event_key,
            exam_slot_id=self.slot.id,
        )
        self.assert_constraint_violation("uq_registrations_candidate_event", duplicate)

        count_after_rollback = self.session.scalar(
            select(func.count())
            .select_from(Registration)
            .where(Registration.candidate_id == self.candidate.id)
        )
        self.assertEqual(count_after_rollback, 1)

        recovered_registration = Registration(
            candidate_id=self.candidate.id,
            event_key=f"PG-RECOVERY-{uuid4().hex}",
            exam_slot_id=self.slot.id,
        )
        self.session.add(recovered_registration)
        self.session.flush()
        self.assertIsNotNone(recovered_registration.id)


if __name__ == "__main__":
    unittest.main()

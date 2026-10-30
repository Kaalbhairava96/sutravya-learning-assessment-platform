"""PostgreSQL-only integrity checks for the approved disposable test database.

Run with SUTRAVYA_POSTGRES_TEST_DATABASE_URL set to the approved disposable
target, migrated to the current head. This dedicated variable is isolated from
other tests' temporary DATABASE_URL overrides. Most tests use an outer transaction that
is rolled back; the concurrent challenge test commits only unique synthetic
records and deletes those exact records in cleanup.
"""

from __future__ import annotations

import os
import time
import unittest
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier, Lock
from urllib.parse import urlsplit
from uuid import uuid4

from alembic.runtime.migration import MigrationContext
from sqlalchemy import delete, func, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.config import Settings
from app.database import create_database_engine
from app.models import (
    AnswerOption,
    Candidate,
    CandidateSession,
    CandidateResponse,
    ExamAttempt,
    ExamSlot,
    Question,
    QuestionBank,
    Registration,
    VerificationChallenge,
)
from app.registration import (
    REGISTRATION_OTP_PURPOSE,
    _new_registration_id,
    create_registration_challenge,
    verify_registration_email,
)
from app.verification import (
    ChallengeVerification,
    OTP_PURPOSE,
    digest_destination,
    digest_otp,
    verify_and_consume_challenge,
)


class PostgreSQLIntegrityTests(unittest.TestCase):
    """Exercise constraints on PostgreSQL without committing fixture data."""

    engine: Engine
    settings: Settings

    @classmethod
    def setUpClass(cls) -> None:
        # Read only a dedicated test variable. Never inherit another test's
        # DATABASE_URL override or read backend/.env.
        test_database_url = os.environ.get("SUTRAVYA_POSTGRES_TEST_DATABASE_URL", "").strip()
        if not test_database_url:
            raise RuntimeError(
                "PostgreSQL integration tests require SUTRAVYA_POSTGRES_TEST_DATABASE_URL "
                "for the approved disposable database."
            )
        settings = Settings.from_env(
            environ={
                "APP_ENV": "test",
                "LOG_LEVEL": "CRITICAL",
                "DATABASE_URL": test_database_url,
            },
            dotenv_path=Path(os.devnull),
        )
        if settings.app_env != "test":
            raise RuntimeError("PostgreSQL integration tests require APP_ENV=test.")
        if urlsplit(settings.database_url).username != "sutravya_m3_test":
            raise RuntimeError("PostgreSQL integration tests require the approved disposable database user.")

        cls.engine = create_database_engine(settings, poolclass=NullPool)
        cls.settings = settings
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
                if revision != "0008_registration_serial_ids":
                    raise RuntimeError("PostgreSQL integration tests require schema revision 0008_registration_serial_ids.")
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

    def create_synthetic_verification_fixture(
        self,
        *,
        created_at: datetime | None = None,
        expires_at: datetime | None = None,
        consumed_at: datetime | None = None,
    ) -> tuple[UUID, UUID, str, Settings, str]:
        settings = replace(
            self.settings,
            otp_hmac_pepper="postgres-integration-test-only-pepper-with-at-least-32-bytes",
        )
        candidate_id = uuid4()
        challenge_id = uuid4()
        email = f"otp-{candidate_id.hex}@example.invalid"
        otp = "004271"
        now = datetime.now(timezone.utc)
        challenge_created_at = created_at or now
        challenge_expires_at = expires_at or (now + timedelta(minutes=5))
        challenge = VerificationChallenge(
            id=challenge_id,
            candidate_id=candidate_id,
            channel="email",
            purpose=OTP_PURPOSE,
            destination_digest=digest_destination(
                email,
                settings=settings,
                candidate_id=candidate_id,
                channel="email",
            ),
            otp_digest=digest_otp(
                otp,
                settings=settings,
                challenge_id=challenge_id,
                candidate_id=candidate_id,
                channel="email",
            ),
            created_at=challenge_created_at,
            expires_at=challenge_expires_at,
            consumed_at=consumed_at,
        )
        with Session(self.engine) as setup_session, setup_session.begin():
            setup_session.add_all(
                [
                    Candidate(
                        id=candidate_id,
                        full_name="Synthetic OTP integration candidate",
                        email=email,
                    ),
                    challenge,
                ]
            )
        return candidate_id, challenge_id, email, settings, otp

    def cleanup_synthetic_verification_fixture(self, candidate_id: UUID, challenge_id: UUID) -> None:
        with Session(self.engine) as cleanup_session, cleanup_session.begin():
            cleanup_session.execute(
                delete(VerificationChallenge).where(VerificationChallenge.id == challenge_id)
            )
            cleanup_session.execute(delete(Candidate).where(Candidate.id == candidate_id))

    def run_concurrent_attempts_while_candidate_is_locked(
        self,
        candidate_id: UUID,
        attempt_count: int,
        attempt: Callable[[Session, int], object],
    ) -> list[object]:
        """Hold the candidate lock until PostgreSQL reports every worker waiting on it."""
        holder = Session(self.engine)
        holder_transaction = holder.begin()
        holder.scalar(select(Candidate.id).where(Candidate.id == candidate_id).with_for_update())
        ready = Barrier(attempt_count + 1)
        worker_pids: list[int] = []

        def worker(index: int) -> object:
            with Session(self.engine) as session, session.begin():
                worker_pids.append(session.scalar(text("SELECT pg_backend_pid()")))
                ready.wait(timeout=10)
                return attempt(session, index)

        executor = ThreadPoolExecutor(max_workers=attempt_count)
        try:
            futures = [executor.submit(worker, index) for index in range(attempt_count)]
            ready.wait(timeout=10)
            lock_waiters = 0
            deadline = time.monotonic() + 10
            with self.engine.connect() as monitor:
                while time.monotonic() < deadline:
                    lock_waiters = monitor.scalar(
                        text(
                            "SELECT count(*) FROM pg_stat_activity "
                            "WHERE pid = ANY(CAST(:pids AS integer[])) "
                            "AND wait_event_type = 'Lock'"
                        ),
                        {"pids": worker_pids},
                    )
                    if lock_waiters == attempt_count:
                        break
                    time.sleep(0.02)
            self.assertEqual(
                lock_waiters,
                attempt_count,
                "Workers did not all enter a PostgreSQL row-lock wait before release.",
            )
            holder_transaction.commit()
            return [future.result(timeout=15) for future in futures]
        finally:
            if holder_transaction.is_active:
                holder_transaction.rollback()
            holder.close()
            executor.shutdown(wait=True, cancel_futures=True)

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

    def test_concurrent_registrations_receive_unique_postgresql_sequence_ids(self) -> None:
        worker_count = 8
        start = Barrier(worker_count)
        candidate_ids: list[UUID] = []
        lock = Lock()
        now = datetime.now(timezone.utc)
        settings = replace(
            self.settings,
            otp_hmac_pepper="postgres-registration-id-test-pepper-at-least-32-bytes",
        )

        def register(index: int) -> tuple[UUID, str]:
            with Session(self.engine) as session:
                pending = create_registration_challenge(
                    session,
                    settings=settings,
                    name=f"Synthetic Sequence Candidate {index}",
                    email=f"sequence-{uuid4().hex}@example.invalid",
                    mobile=f"98765432{index:02d}",
                    stream="nursing",
                    now=now,
                )
                with lock:
                    candidate_ids.append(pending.candidate_id)
                start.wait(timeout=15)
                outcome, summary = verify_registration_email(
                    session,
                    settings=settings,
                    challenge_id=pending.challenge_id,
                    otp=pending.otp,
                    now=now + timedelta(seconds=1),
                )
                if outcome != ChallengeVerification.VERIFIED or summary is None:
                    raise AssertionError("Synthetic registration failed verification.")
                return pending.candidate_id, summary.registration_id

        try:
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                rows = list(executor.map(register, range(worker_count)))
            identifiers = [registration_id for _candidate_id, registration_id in rows]
            self.assertEqual(len(set(identifiers)), worker_count)
            for registration_id in identifiers:
                self.assertRegex(registration_id, r"^SUT-[0-9]{4}/[0-9]{2}/[0-9]{2}-[0-9]{11}$")
        finally:
            if candidate_ids:
                with Session(self.engine) as cleanup_session, cleanup_session.begin():
                    cleanup_session.execute(
                        delete(CandidateSession).where(CandidateSession.candidate_id.in_(candidate_ids))
                    )
                    cleanup_session.execute(
                        delete(VerificationChallenge).where(VerificationChallenge.candidate_id.in_(candidate_ids))
                    )
                    cleanup_session.execute(
                        delete(Registration).where(Registration.candidate_id.in_(candidate_ids))
                    )
                    cleanup_session.execute(delete(Candidate).where(Candidate.id.in_(candidate_ids)))

    def test_duplicate_candidate_registration_is_rejected(self) -> None:
        duplicate = Registration(
            candidate_id=self.candidate.id,
            event_key=self.registration.event_key,
            exam_slot_id=self.slot.id,
        )
        self.assert_constraint_violation("uq_registrations_candidate_event_official", duplicate)

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
        self.assert_constraint_violation("uq_registrations_candidate_event_official", duplicate)

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

    def test_concurrent_requests_can_consume_a_challenge_only_once(self) -> None:
        candidate_id, challenge_id, _email, settings, otp = self.create_synthetic_verification_fixture()
        try:
            outcomes = self.run_concurrent_attempts_while_candidate_is_locked(
                candidate_id,
                2,
                lambda session, _index: verify_and_consume_challenge(
                    session,
                    settings=settings,
                    candidate_id=candidate_id,
                    challenge_id=challenge_id,
                    channel="email",
                    otp=otp,
                ),
            )
            self.assertEqual(outcomes.count(ChallengeVerification.VERIFIED), 1)
            self.assertEqual(outcomes.count(ChallengeVerification.CONSUMED), 1)
            with Session(self.engine) as check_session:
                persisted = check_session.get(VerificationChallenge, challenge_id)
                candidate = check_session.get(Candidate, candidate_id)
                self.assertIsNotNone(persisted.consumed_at)
                self.assertIsNotNone(candidate.email_verified_at)
        finally:
            self.cleanup_synthetic_verification_fixture(candidate_id, challenge_id)

    def test_concurrent_incorrect_attempts_cannot_exceed_limit(self) -> None:
        candidate_id, challenge_id, _email, settings, _otp = self.create_synthetic_verification_fixture()
        incorrect_otp = "999999"
        try:
            outcomes = self.run_concurrent_attempts_while_candidate_is_locked(
                candidate_id,
                settings.otp_max_attempts,
                lambda session, _index: verify_and_consume_challenge(
                    session,
                    settings=settings,
                    candidate_id=candidate_id,
                    challenge_id=challenge_id,
                    channel="email",
                    otp=incorrect_otp,
                ),
            )
            self.assertEqual(
                outcomes.count(ChallengeVerification.INVALID_CODE),
                settings.otp_max_attempts - 1,
            )
            self.assertEqual(outcomes.count(ChallengeVerification.ATTEMPTS_EXHAUSTED), 1)
            with Session(self.engine) as check_session:
                persisted = check_session.get(VerificationChallenge, challenge_id)
                candidate = check_session.get(Candidate, candidate_id)
                self.assertEqual(persisted.attempt_count, settings.otp_max_attempts)
                self.assertIsNone(candidate.email_verified_at)

            with Session(self.engine) as session, session.begin():
                extra_attempt = verify_and_consume_challenge(
                    session,
                    settings=settings,
                    candidate_id=candidate_id,
                    challenge_id=challenge_id,
                    channel="email",
                    otp=incorrect_otp,
                )
                self.assertEqual(extra_attempt, ChallengeVerification.ATTEMPTS_EXHAUSTED)
            with Session(self.engine) as check_session:
                persisted = check_session.get(VerificationChallenge, challenge_id)
                self.assertEqual(persisted.attempt_count, settings.otp_max_attempts)
        finally:
            self.cleanup_synthetic_verification_fixture(candidate_id, challenge_id)

    def test_stale_candidate_contact_is_refreshed_after_lock(self) -> None:
        candidate_id, challenge_id, old_email, settings, otp = self.create_synthetic_verification_fixture()
        new_email = f"changed-{candidate_id.hex}@example.invalid"
        stale_session = Session(self.engine, expire_on_commit=False)
        try:
            stale_candidate = stale_session.get(Candidate, candidate_id)
            self.assertEqual(stale_candidate.email, old_email)
            stale_session.commit()

            with Session(self.engine) as change_session, change_session.begin():
                changed_candidate = change_session.get(Candidate, candidate_id)
                changed_candidate.email = new_email

            with stale_session.begin():
                outcome = verify_and_consume_challenge(
                    stale_session,
                    settings=settings,
                    candidate_id=candidate_id,
                    challenge_id=challenge_id,
                    channel="email",
                    otp=otp,
                )
            self.assertEqual(outcome, ChallengeVerification.INVALIDATED)

            with Session(self.engine) as check_session:
                persisted = check_session.get(VerificationChallenge, challenge_id)
                candidate = check_session.get(Candidate, candidate_id)
                self.assertEqual(candidate.email, new_email)
                self.assertIsNone(candidate.email_verified_at)
                self.assertIsNotNone(persisted.invalidated_at)
                self.assertIsNone(persisted.consumed_at)
        finally:
            stale_session.close()
            self.cleanup_synthetic_verification_fixture(candidate_id, challenge_id)

    def test_verification_state_rolls_back_together_on_transaction_failure(self) -> None:
        candidate_id, challenge_id, _email, settings, otp = self.create_synthetic_verification_fixture()
        try:
            with self.assertRaisesRegex(RuntimeError, "simulated transaction failure"):
                with Session(self.engine) as session, session.begin():
                    outcome = verify_and_consume_challenge(
                        session,
                        settings=settings,
                        candidate_id=candidate_id,
                        challenge_id=challenge_id,
                        channel="email",
                        otp=otp,
                    )
                    self.assertEqual(outcome, ChallengeVerification.VERIFIED)
                    raise RuntimeError("simulated transaction failure")

            with Session(self.engine) as check_session:
                persisted = check_session.get(VerificationChallenge, challenge_id)
                candidate = check_session.get(Candidate, candidate_id)
                self.assertIsNone(persisted.consumed_at)
                self.assertIsNone(candidate.email_verified_at)
        finally:
            self.cleanup_synthetic_verification_fixture(candidate_id, challenge_id)

    def test_expired_and_consumed_challenges_are_rejected(self) -> None:
        now = datetime.now(timezone.utc)
        expired_candidate_id, expired_challenge_id, _email, settings, otp = (
            self.create_synthetic_verification_fixture(
                created_at=now - timedelta(minutes=10),
                expires_at=now - timedelta(minutes=5),
            )
        )
        consumed_candidate_id, consumed_challenge_id, _email, _settings, _otp = (
            self.create_synthetic_verification_fixture(
                created_at=now - timedelta(minutes=1),
                expires_at=now + timedelta(minutes=4),
                consumed_at=now - timedelta(seconds=1),
            )
        )
        try:
            with Session(self.engine) as session, session.begin():
                expired = verify_and_consume_challenge(
                    session,
                    settings=settings,
                    candidate_id=expired_candidate_id,
                    challenge_id=expired_challenge_id,
                    channel="email",
                    otp=otp,
                    now=now,
                )
                self.assertEqual(expired, ChallengeVerification.EXPIRED)
            with Session(self.engine) as session, session.begin():
                consumed = verify_and_consume_challenge(
                    session,
                    settings=settings,
                    candidate_id=consumed_candidate_id,
                    challenge_id=consumed_challenge_id,
                    channel="email",
                    otp=otp,
                    now=now,
                )
                self.assertEqual(consumed, ChallengeVerification.CONSUMED)
        finally:
            self.cleanup_synthetic_verification_fixture(expired_candidate_id, expired_challenge_id)
            self.cleanup_synthetic_verification_fixture(consumed_candidate_id, consumed_challenge_id)

    def test_concurrent_duplicate_verified_email_registration_allows_one_winner(self) -> None:
        settings = replace(
            self.settings,
            otp_hmac_pepper="postgres-integration-test-only-pepper-with-at-least-32-bytes",
        )
        now = datetime.now(timezone.utc)
        shared_email = f"duplicate-{uuid4().hex}@example.invalid"
        otp = "004271"
        candidate_ids = [uuid4(), uuid4()]
        challenge_ids = [uuid4(), uuid4()]
        with Session(self.engine) as setup, setup.begin():
            for index, candidate_id in enumerate(candidate_ids):
                challenge_id = challenge_ids[index]
                candidate = Candidate(
                    id=candidate_id,
                    full_name=f"Synthetic duplicate email candidate {index}",
                    email=shared_email,
                    pending_stream="nursing",
                )
                challenge = VerificationChallenge(
                    id=challenge_id,
                    candidate_id=candidate_id,
                    channel="email",
                    purpose=REGISTRATION_OTP_PURPOSE,
                    destination_digest=digest_destination(
                        shared_email, settings=settings, candidate_id=candidate_id,
                        channel="email", purpose=REGISTRATION_OTP_PURPOSE,
                    ),
                    otp_digest=digest_otp(
                        otp, settings=settings, challenge_id=challenge_id,
                        candidate_id=candidate_id, channel="email", purpose=REGISTRATION_OTP_PURPOSE,
                    ),
                    created_at=now,
                    expires_at=now + timedelta(minutes=5),
                )
                setup.add_all([candidate, challenge])

        ready = Barrier(2)

        def verify(challenge_id):
            try:
                with Session(self.engine) as session:
                    ready.wait(timeout=10)
                    return verify_registration_email(
                        session, settings=settings, challenge_id=challenge_id, otp=otp, now=now,
                    )
            except IntegrityError:
                return "duplicate_verified_email_rejected"

        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(verify, challenge_ids))
            self.assertEqual(outcomes.count("duplicate_verified_email_rejected"), 1)
            successful = [value for value in outcomes if value != "duplicate_verified_email_rejected"]
            self.assertEqual(len(successful), 1)
            self.assertEqual(successful[0][0], ChallengeVerification.VERIFIED)
            with Session(self.engine) as check:
                registration_count = check.scalar(
                    select(func.count()).select_from(Registration).where(
                        Registration.candidate_id.in_(candidate_ids)
                    )
                )
                verified_count = check.scalar(
                    select(func.count()).select_from(Candidate).where(
                        Candidate.id.in_(candidate_ids), Candidate.email_verified_at.is_not(None)
                    )
                )
                self.assertEqual(registration_count, 1)
                self.assertEqual(verified_count, 1)
        finally:
            with Session(self.engine) as cleanup, cleanup.begin():
                cleanup.execute(delete(Registration).where(Registration.candidate_id.in_(candidate_ids)))
                cleanup.execute(delete(VerificationChallenge).where(VerificationChallenge.id.in_(challenge_ids)))
                cleanup.execute(delete(Candidate).where(Candidate.id.in_(candidate_ids)))


if __name__ == "__main__":
    unittest.main()

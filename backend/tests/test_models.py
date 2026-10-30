from __future__ import annotations

import os
import runpy
from contextlib import redirect_stdout
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, configure_mappers

from app.models import (
    AdminUser,
    AnswerOption,
    Base,
    Candidate,
    CandidateResponse,
    ExamAttempt,
    ExamSlot,
    Question,
    QuestionBank,
    Registration,
    Result,
    VerificationChallenge,
)


class ModelSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        configure_mappers()
        self.engine = create_engine("sqlite+pysqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _record) -> None:
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.candidate = Candidate(full_name="Test Candidate")
        self.bank = QuestionBank(bank_code="TEST-NURSING", title="Test bank")
        now = datetime.now(timezone.utc)
        self.slot = ExamSlot(
            event_key="TEST-EVENT",
            starts_at=now,
            ends_at=now + timedelta(hours=1),
            capacity=None,
        )
        self.session.add_all([self.candidate, self.bank, self.slot])
        self.session.flush()
        self.registration = Registration(
            candidate_id=self.candidate.id,
            event_key="TEST-EVENT",
            exam_slot_id=self.slot.id,
        )
        self.question = Question(question_bank_id=self.bank.id, question_text="Test prompt")
        self.question.options.extend(
            [
                AnswerOption(identifier="A", option_text="Choice A", is_correct=True),
                AnswerOption(identifier="B", option_text="Choice B", is_correct=False),
            ]
        )
        self.session.add_all([self.registration, self.question])
        self.session.flush()
        self.attempt = ExamAttempt(
            registration_id=self.registration.id,
            exam_slot_id=self.slot.id,
            question_bank_id=self.bank.id,
            attempt_number=1,
        )
        self.session.add(self.attempt)
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_requested_entities_and_question_bank_are_registered(self) -> None:
        expected = {
            "candidates", "registrations", "exam_slots", "questions", "answer_options",
            "exam_attempts", "candidate_responses", "scoring_rules", "results",
            "admin_users", "audit_events", "question_banks", "verification_challenges",
            "candidate_sessions", "rate_limit_buckets",
        }
        self.assertEqual(set(Base.metadata.tables), expected)

    def test_relationships_and_foreign_keys_are_registered(self) -> None:
        self.assertIn("candidate", inspect(Registration).relationships)
        self.assertIn("exam_slot", inspect(Registration).relationships)
        self.assertIn("question_bank", inspect(Question).relationships)
        self.assertIn("options", inspect(Question).relationships)
        self.assertIn("responses", inspect(ExamAttempt).relationships)
        self.assertIn("result", inspect(ExamAttempt).relationships)
        self.assertTrue(Base.metadata.tables["registrations"].foreign_keys)
        self.assertTrue(Base.metadata.tables["candidate_responses"].foreign_key_constraints)
        self.assertIn("verification_challenges", inspect(Candidate).relationships)
        self.assertIn("candidate", inspect(VerificationChallenge).relationships)

    def test_candidate_contact_pair_unique_only_after_both_contacts_are_verified(self) -> None:
        now = datetime.now(timezone.utc)
        first = Candidate(
            email="Nurse@example.invalid",
            phone="+911234567890",
            email_verified_at=now,
            phone_verified_at=now,
        )
        second = Candidate(
            email="nurse@example.invalid",
            phone="+911234567890",
            email_verified_at=now,
            phone_verified_at=now,
        )
        self.session.add(first)
        self.session.flush()
        self.session.add(second)
        with self.assertRaises(IntegrityError):
            self.session.flush()
        self.session.rollback()

        unverified_duplicate = Candidate(email="nurse@example.invalid", phone="+911234567890")
        self.session.add(unverified_duplicate)
        self.session.commit()

    def test_verification_challenge_persists_digest_and_lifecycle_fields_only(self) -> None:
        challenge = VerificationChallenge(
            candidate_id=self.candidate.id,
            channel="mobile",
            purpose="contact_verification",
            destination_digest="b" * 64,
            otp_digest="a" * 64,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        self.session.add(challenge)
        self.session.flush()
        columns = set(Base.metadata.tables["verification_challenges"].columns.keys())
        self.assertIn("otp_digest", columns)
        self.assertIn("attempt_count", columns)
        self.assertIn("consumed_at", columns)
        self.assertIn("invalidated_at", columns)
        self.assertNotIn("otp", columns)
        self.assertNotIn("code", columns)

    def test_question_options_relationship_and_one_correct_option_limit(self) -> None:
        question = self.session.get(Question, self.question.id)
        self.assertEqual(len(question.options), 2)
        self.assertTrue(any(option.is_correct for option in question.options))
        self.session.add(AnswerOption(question_id=question.id, identifier="C", option_text="Choice C", is_correct=True))
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_duplicate_candidate_registration_is_rejected(self) -> None:
        self.session.add(
            Registration(candidate_id=self.candidate.id, event_key="TEST-EVENT", exam_slot_id=self.slot.id)
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_duplicate_attempt_number_for_registration_is_rejected(self) -> None:
        self.session.add(
            ExamAttempt(
                registration_id=self.registration.id,
                exam_slot_id=self.slot.id,
                question_bank_id=self.bank.id,
                attempt_number=1,
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_duplicate_response_and_option_from_another_question_are_rejected(self) -> None:
        correct_option = next(option for option in self.question.options if option.identifier == "A")
        response = CandidateResponse(
            attempt_id=self.attempt.id,
            question_id=self.question.id,
            selected_option_id=correct_option.id,
        )
        self.session.add(response)
        self.session.commit()

        self.session.add(
            CandidateResponse(
                attempt_id=self.attempt.id,
                question_id=self.question.id,
                selected_option_id=correct_option.id,
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

        another = Question(question_bank_id=self.bank.id, question_text="Another prompt")
        another.options.append(AnswerOption(identifier="A", option_text="Unrelated option"))
        self.session.add(another)
        self.session.commit()
        self.session.add(
            CandidateResponse(
                attempt_id=self.attempt.id,
                question_id=self.question.id,
                selected_option_id=another.options[0].id,
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_one_result_per_attempt_and_case_insensitive_admin_email(self) -> None:
        admin = AdminUser(email="Admin@Example.invalid", password_hash="test-hash", is_active=False)
        self.session.add(admin)
        self.session.flush()
        self.session.add(Result(attempt_id=self.attempt.id, score=Decimal("5.250")))
        self.session.commit()
        self.session.add(Result(attempt_id=self.attempt.id, score=Decimal("5.250")))
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

        self.session.add(AdminUser(email="admin@example.invalid", password_hash="another-test-hash"))
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_password_hash_only_and_scoring_fields_are_unresolved_nullable_decimals(self) -> None:
        admin_columns = set(Base.metadata.tables["admin_users"].columns.keys())
        self.assertIn("password_hash", admin_columns)
        self.assertNotIn("password", admin_columns)
        scoring = Base.metadata.tables["scoring_rules"].columns
        for name in ("correct_points", "incorrect_points", "unanswered_points"):
            self.assertTrue(scoring[name].nullable)
            self.assertEqual(str(scoring[name].type), "NUMERIC(10, 3)")
        self.assertEqual(Base.metadata.tables["results"].c.score.type.precision, 12)
        self.assertEqual(Base.metadata.tables["results"].c.score.type.scale, 3)

    def test_alembic_discovers_new_revision_and_metadata(self) -> None:
        config = Config("alembic.ini")
        script = ScriptDirectory.from_config(config)
        self.assertEqual(script.get_heads(), ["0008_registration_serial_ids"])
        revision = script.get_revision("0002_core_application_schema")
        self.assertEqual(revision.down_revision, "0001_backend_foundation")
        verification_revision = script.get_revision("0003_secure_verify")
        self.assertEqual(verification_revision.down_revision, "0002_core_application_schema")
        account_revision = script.get_revision("0004_registration_accounts")
        self.assertEqual(account_revision.down_revision, "0003_secure_verify")
        internal_test_revision = script.get_revision("0005_internal_test_flags")
        self.assertEqual(internal_test_revision.down_revision, "0004_registration_accounts")
        unified_source_revision = script.get_revision("0006_reg_source")
        self.assertEqual(unified_source_revision.down_revision, "0005_internal_test_flags")
        legacy_classification_revision = script.get_revision("0007_legacy_classification")
        self.assertEqual(legacy_classification_revision.down_revision, "0006_reg_source")
        registration_serial_revision = script.get_revision("0008_registration_serial_ids")
        self.assertEqual(registration_serial_revision.down_revision, "0007_legacy_classification")
        self.assertEqual(len(Base.metadata.tables), 15)

    def test_migration_renders_offline_without_database(self) -> None:
        test_env = {
            "APP_ENV": "test",
            "LOG_LEVEL": "CRITICAL",
            "DATABASE_URL": "postgresql+psycopg://test:test@127.0.0.1:55432/sutravya_m3_test",
        }
        with patch.dict(os.environ, test_env), patch("app.config._read_dotenv", return_value={}):
            output = StringIO()
            with redirect_stdout(output):
                command.upgrade(Config("alembic.ini"), "head", sql=True)
        sql = output.getvalue()
        for table_name in Base.metadata.tables:
            self.assertIn(f"CREATE TABLE {table_name}", sql)
        for table in Base.metadata.tables.values():
            for constraint in table.constraints:
                if constraint.name is not None:
                    self.assertIn(f"CONSTRAINT {constraint.name}", sql)
        self.assertIn("uq_answer_options_one_correct_per_question", sql)
        self.assertIn("uq_admin_users_email_lower", sql)
        self.assertIn("uq_candidates_verified_contact_pair", sql)
        self.assertIn("CREATE UNIQUE INDEX uq_candidates_verified_email", sql)
        self.assertIn("registration_source", sql)
        self.assertIn("uq_registrations_candidate_event_official", sql)
        self.assertIn(
            "UPDATE registrations SET registration_source = 'legacy_internal_test' WHERE is_internal_test IS TRUE",
            sql,
        )
        self.assertIn(
            "UPDATE verification_challenges SET registration_source = 'legacy_internal_test' WHERE is_internal_test IS TRUE",
            sql,
        )
        self.assertIn("'legacy_internal_test'", sql)
        self.assertIn("WHERE is_internal_test IS FALSE", sql)
        self.assertNotIn("DELETE FROM registrations", sql)
        self.assertNotIn("DELETE FROM candidates", sql)
        self.assertNotIn("UPDATE registrations SET registration_id", sql)
        self.assertNotIn("UPDATE registrations SET candidate_id", sql)
        self.assertNotIn("SET is_internal_test", sql)
        self.assertNotIn("SELECT lower(email)", sql)
        self.assertIn("DROP CONSTRAINT ck_registrations_registration_source", sql)
        self.assertIn("DROP CONSTRAINT ck_verification_challenges_registration_source", sql)
        self.assertIn("UPDATE verification_challenges SET registration_source = 'legacy_internal_test'", sql)
        self.assertLess(
            sql.rfind("DROP CONSTRAINT ck_registrations_registration_source"),
            sql.rfind("UPDATE registrations SET registration_source = 'legacy_internal_test'"),
        )
        self.assertNotIn("DELETE FROM", sql)
        self.assertIn("CREATE SEQUENCE registration_id_serial_seq", sql)
        self.assertIn("START WITH 1", sql)
        self.assertIn("INCREMENT BY 1", sql)
        self.assertIn("MAXVALUE 99999999999", sql)

    def test_verification_migration_downgrade_renders_only_new_schema_removal(self) -> None:
        test_env = {
            "APP_ENV": "test",
            "LOG_LEVEL": "CRITICAL",
            "DATABASE_URL": "postgresql+psycopg://test:test@127.0.0.1:55432/sutravya_m3_test",
        }
        with patch.dict(os.environ, test_env), patch("app.config._read_dotenv", return_value={}):
            output = StringIO()
            with redirect_stdout(output):
                command.downgrade(
                    Config("alembic.ini"),
                    "0003_secure_verify:0002_core_application_schema",
                    sql=True,
                )
        sql = output.getvalue()
        self.assertIn("DROP TABLE verification_challenges", sql)
        self.assertIn("DROP INDEX uq_candidates_verified_contact_pair", sql)
        self.assertIn("DROP COLUMN email_verified_at", sql)
        self.assertIn("DROP COLUMN phone_verified_at", sql)

    def test_registration_migration_downgrade_fails_closed_offline(self) -> None:
        test_env = {
            "APP_ENV": "test",
            "LOG_LEVEL": "CRITICAL",
            "DATABASE_URL": "postgresql+psycopg://test:test@127.0.0.1:55432/sutravya_m3_test",
        }
        with patch.dict(os.environ, test_env), patch("app.config._read_dotenv", return_value={}):
            output = StringIO()
            with redirect_stdout(output), self.assertRaisesRegex(
                RuntimeError, "live checks are required"
            ):
                command.downgrade(Config("alembic.ini"), "head:base", sql=True)
        self.assertNotIn("DROP TABLE candidate_sessions", output.getvalue())
        self.assertNotIn("DROP TABLE rate_limit_buckets", output.getvalue())

    def test_registration_source_downgrade_refuses_to_drop_legacy_classification(self) -> None:
        migration = runpy.run_path("migrations/versions/0007_legacy_classification.py")
        legacy_row = object()

        class FakeResult:
            def __init__(self, row):
                self.row = row

            def first(self):
                return self.row

        bind = type("FakeBind", (), {})()

        def execute(statement):
            sql = str(statement)
            if "registrations" in sql and "legacy_internal_test" in sql:
                return FakeResult(legacy_row)
            return FakeResult(None)

        bind.execute = execute
        with (
            patch("alembic.context.is_offline_mode", return_value=False),
            patch("alembic.op.get_bind", return_value=bind),
            patch("alembic.op.drop_constraint") as drop_constraint,
        ):
            with self.assertRaisesRegex(RuntimeError, "legacy internal-test records exist"):
                migration["downgrade"]()
        drop_constraint.assert_not_called()

    def test_registration_id_sequence_downgrade_fails_closed_when_id_or_serial_was_allocated(self) -> None:
        migration = runpy.run_path("migrations/versions/0008_registration_serial_ids.py")

        class FakeResult:
            def __init__(self, row):
                self.row = row

            def first(self):
                return self.row

            def one(self):
                return self.row

        for registration_exists, sequence_called in ((True, False), (False, True)):
            with self.subTest(registration_exists=registration_exists, sequence_called=sequence_called):
                bind = type("FakeBind", (), {})()

                def execute(statement):
                    sql = str(statement)
                    if "WHERE registration_id ~" in sql:
                        return FakeResult((1,) if registration_exists else None)
                    return FakeResult((1, sequence_called))

                bind.execute = execute
                with (
                    patch("alembic.context.is_offline_mode", return_value=False),
                    patch("alembic.op.get_bind", return_value=bind),
                    patch("alembic.op.execute") as execute,
                ):
                    with self.assertRaisesRegex(RuntimeError, "new-format IDs or allocated serials"):
                        migration["downgrade"]()
                execute.assert_not_called()

    def test_registration_source_fields_default_to_public_without_touching_legacy_flags(self) -> None:
        registration = Base.metadata.tables["registrations"]
        challenges = Base.metadata.tables["verification_challenges"]
        for table in (registration, challenges):
            source = table.c.registration_source
            self.assertFalse(source.nullable)
            self.assertEqual(source.default.arg, "public_registration")
            self.assertEqual(str(source.server_default.arg), "'public_registration'")
        self.assertIn("ck_registrations_registration_source", {c.name for c in registration.constraints})
        self.assertIn("ck_verification_challenges_registration_source", {c.name for c in challenges.constraints})
        registration_source_check = next(
            c for c in registration.constraints if c.name == "ck_registrations_registration_source"
        )
        self.assertIn("legacy_internal_test", str(registration_source_check.sqltext))
        self.assertIn("uq_registrations_candidate_event_official", {i.name for i in registration.indexes})


if __name__ == "__main__":
    unittest.main()

"""Security and lifecycle tests for the candidate exam service."""
from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.exam_service import (
    ExamError,
    exam_availability,
    get_attempt,
    save_answer,
    start_exam,
    submit_exam,
)
from app.models import (
    AnswerOption,
    Base,
    Candidate,
    CandidateSession,
    ExamSlot,
    Question,
    QuestionBank,
    Registration,
    ScoringRule,
)

RAW_TOKEN = "synthetic-exam-session-token"
NOW = datetime(2026, 12, 4, 10, 5, tzinfo=timezone.utc)


class CandidateExamServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _record) -> None:
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.session = self.factory()
        self.addCleanup(self.session.close)
        self.addCleanup(self.engine.dispose)
        candidate = Candidate(
            full_name="Synthetic Candidate",
            email="exam-candidate@example.invalid",
            phone="+919876543210",
            email_verified_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
        )
        self.session.add(candidate)
        self.session.flush()
        slot = ExamSlot(
            event_key="BHC-2026",
            starts_at=datetime(2026, 12, 4, 10, 0, tzinfo=timezone.utc),
            ends_at=datetime(2026, 12, 4, 11, 0, tzinfo=timezone.utc),
            capacity=1000,
        )
        bank = QuestionBank(bank_code="paramedical", title="Paramedical HTSE 2026")
        self.session.add_all([slot, bank])
        self.session.flush()
        self.registration = Registration(
            candidate_id=candidate.id,
            event_key="BHC-2026",
            registration_id="SUT-2026/11/20-00000000001",
            stream="paramedical",
            exam_slot_id=slot.id,
            status="active",
            registration_source="public_registration",
        )
        self.session.add(self.registration)
        self.session.add(CandidateSession(
            candidate_id=candidate.id,
            token_digest=hashlib.sha256(RAW_TOKEN.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        ))
        self.questions: list[Question] = []
        self.correct_options: list[AnswerOption] = []
        self.wrong_options: list[AnswerOption] = []
        for index in range(100):
            question = Question(
                question_bank_id=bank.id,
                question_text=f"Synthetic question {index + 1}",
                category="General",
                is_active=True,
            )
            self.session.add(question)
            self.session.flush()
            options = [
                AnswerOption(question_id=question.id, identifier=label, option_text=f"Option {label}", is_correct=(label == "A"))
                for label in ("A", "B", "C", "D")
            ]
            self.session.add_all(options)
            self.questions.append(question)
            self.correct_options.append(options[0])
            self.wrong_options.append(options[1])
        self.session.add(ScoringRule(
            question_bank_id=bank.id,
            rule_code="htse_2026",
            correct_points=Decimal("1"),
            incorrect_points=Decimal("0"),
            unanswered_points=Decimal("0"),
        ))
        self.session.commit()
        self.slot = slot
        self.bank = bank

    def test_availability_requires_configured_stream_bank_and_reports_slot(self) -> None:
        data = exam_availability(self.session, RAW_TOKEN, now=NOW)
        self.assertTrue(data["eligible"])
        self.assertTrue(data["assigned"])
        self.assertEqual(data["stream"], "paramedical")
        self.assertTrue(data["question_bank_ready"])
        self.assertEqual(data["question_count"], 100)

    def test_start_hides_answer_key_saves_answers_and_reveals_review_after_submit(self) -> None:
        started = start_exam(self.session, RAW_TOKEN, now=NOW)
        self.assertEqual(started["status"], "in_progress")
        self.assertEqual(len(started["questions"]), 100)
        self.assertNotIn("correct_option", started["questions"][0])
        self.assertNotIn("is_correct", started["questions"][0])
        attempt_id = started["attempt_id"]
        first = self.questions[0]
        second = self.questions[1]

        self.assertTrue(save_answer(
            self.session, RAW_TOKEN, attempt_id=__import__("uuid").UUID(attempt_id),
            question_id=first.id, option_id=self.correct_options[0].id, now=NOW + timedelta(minutes=1),
        )["saved"])
        save_answer(
            self.session, RAW_TOKEN, attempt_id=__import__("uuid").UUID(attempt_id),
            question_id=second.id, option_id=self.wrong_options[1].id, now=NOW + timedelta(minutes=1),
        )
        resumed = get_attempt(self.session, RAW_TOKEN, attempt_id=__import__("uuid").UUID(attempt_id), now=NOW + timedelta(minutes=2))
        self.assertEqual(resumed["questions"][0]["selected_option_id"], str(self.correct_options[0].id))
        self.assertNotIn("correct_option", resumed["questions"][0])

        result = submit_exam(
            self.session, RAW_TOKEN, attempt_id=__import__("uuid").UUID(attempt_id),
            now=NOW + timedelta(minutes=5),
        )
        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["score"], "1.000")
        self.assertEqual(result["correct_count"], 1)
        self.assertEqual(result["incorrect_count"], 1)
        self.assertEqual(result["unanswered_count"], 98)
        self.assertEqual(result["total_questions"], 100)
        self.assertEqual(result["review"][0]["correct_option"]["identifier"], "A")
        self.assertTrue(result["review"][0]["is_correct"])
        self.assertFalse(result["review"][1]["is_correct"])

        repeated = submit_exam(
            self.session, RAW_TOKEN, attempt_id=__import__("uuid").UUID(attempt_id),
            now=NOW + timedelta(minutes=6),
        )
        self.assertEqual(repeated["score"], result["score"])
        with self.assertRaises(ExamError) as locked:
            save_answer(
                self.session, RAW_TOKEN, attempt_id=__import__("uuid").UUID(attempt_id),
                question_id=first.id, option_id=self.wrong_options[0].id,
                now=NOW + timedelta(minutes=6),
            )
        self.assertEqual(locked.exception.code, "attempt_not_in_progress")

    def test_answer_cannot_be_saved_after_thirty_minute_deadline(self) -> None:
        started = start_exam(self.session, RAW_TOKEN, now=NOW)
        with self.assertRaises(ExamError) as expired:
            save_answer(
                self.session, RAW_TOKEN, attempt_id=__import__("uuid").UUID(started["attempt_id"]),
                question_id=self.questions[0].id, option_id=self.correct_options[0].id,
                now=NOW + timedelta(minutes=31),
            )
        self.assertEqual(expired.exception.code, "exam_time_expired")

    def test_wrong_question_option_pair_is_rejected(self) -> None:
        started = start_exam(self.session, RAW_TOKEN, now=NOW)
        with self.assertRaises(ExamError) as invalid:
            save_answer(
                self.session, RAW_TOKEN, attempt_id=__import__("uuid").UUID(started["attempt_id"]),
                question_id=self.questions[0].id, option_id=self.wrong_options[1].id,
                now=NOW + timedelta(minutes=1),
            )
        self.assertEqual(invalid.exception.code, "invalid_question_or_option")

    def test_unauthenticated_candidate_cannot_access_exam(self) -> None:
        with self.assertRaises(ExamError) as rejected:
            exam_availability(self.session, None, now=NOW)
        self.assertEqual(rejected.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()

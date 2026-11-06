"""Security and lifecycle tests for the candidate exam service."""
from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID
from decimal import Decimal

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.exam_service import (
    ExamError,
    exam_availability,
    get_attempt,
    get_current_attempt,
    get_question,
    record_integrity_event,
    save_answer,
    start_exam,
    skip_question,
    submit_exam,
)
from app.models import (
    AnswerOption,
    Base,
    Candidate,
    CandidateSession,
    AuditEvent,
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
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.session.close)
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
            stream="paramedical",
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
                section=("anatomy", "physiology", "biology", "quantitative_reasoning", "english_communication")[index // 20],
                difficulty="easy" if index % 2 == 0 else "moderate",
                time_limit_seconds=20 + (index % 5),
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
            incorrect_points=Decimal("-0.25"),
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
        self.assertEqual(started["total_questions"], 100)
        self.assertNotIn("questions", started)
        first = get_question(self.session, RAW_TOKEN, attempt_id=UUID(started["attempt_id"]), position=0, now=NOW)
        self.assertEqual(first["section"], "anatomy")
        self.assertGreaterEqual(first["time_limit_seconds"], 20)
        self.assertEqual(len(first["options"]), 4)
        self.assertNotIn("correct_option", first)
        first_id = UUID(first["question_id"])
        first_index = next(i for i, q in enumerate(self.questions) if q.id == first_id)
        correct_id = next(o.id for o in self.questions[first_index].options if o.is_correct)
        self.assertTrue(save_answer(
            self.session, RAW_TOKEN, attempt_id=UUID(started["attempt_id"]),
            question_id=first_id, option_id=correct_id, now=NOW + timedelta(seconds=3),
        )["saved"])
        second = get_question(self.session, RAW_TOKEN, attempt_id=UUID(started["attempt_id"]), position=1, now=NOW + timedelta(seconds=4))
        second_id = UUID(second["question_id"])
        second_index = next(i for i, q in enumerate(self.questions) if q.id == second_id)
        wrong_id = next(o.id for o in self.questions[second_index].options if not o.is_correct)
        self.assertTrue(save_answer(
            self.session, RAW_TOKEN, attempt_id=UUID(started["attempt_id"]),
            question_id=second_id, option_id=wrong_id, now=NOW + timedelta(seconds=5),
        )["saved"])
        self.session.rollback()
        result = submit_exam(self.session, RAW_TOKEN, attempt_id=UUID(started["attempt_id"]), now=NOW + timedelta(seconds=6))
        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["score"], "0.750")
        self.assertEqual(result["correct_count"], 1)
        self.assertEqual(result["incorrect_count"], 1)
        self.assertEqual(result["unanswered_count"], 98)
        self.assertEqual(result["total_questions"], 100)
        repeated = submit_exam(self.session, RAW_TOKEN, attempt_id=UUID(started["attempt_id"]), now=NOW + timedelta(seconds=7))
        self.assertEqual(repeated["score"], result["score"])

    def test_candidates_cannot_skip_a_live_question_or_return_after_passing(self) -> None:
        started = start_exam(self.session, RAW_TOKEN, now=NOW)
        attempt_id = UUID(started["attempt_id"])
        first = get_question(self.session, RAW_TOKEN, attempt_id=attempt_id, position=0, now=NOW)
        with self.assertRaises(ExamError) as locked:
            get_question(self.session, RAW_TOKEN, attempt_id=attempt_id, position=1, now=NOW + timedelta(seconds=1))
        self.assertEqual(locked.exception.code, "question_time_not_complete")
        skipped = skip_question(
            self.session, RAW_TOKEN, attempt_id=attempt_id, position=0,
            now=NOW + timedelta(seconds=2),
        )
        self.assertTrue(skipped["skipped"])
        second = get_question(
            self.session, RAW_TOKEN, attempt_id=attempt_id, position=1,
            now=NOW + timedelta(seconds=3),
        )
        self.assertEqual(second["position"], 1)
        with self.assertRaises(ExamError) as passed:
            get_question(self.session, RAW_TOKEN, attempt_id=attempt_id, position=0, now=NOW + timedelta(seconds=4))
        self.assertEqual(passed.exception.code, "question_already_passed")

    def test_question_timer_is_server_enforced_and_unanswered_is_zero(self) -> None:
        started = start_exam(self.session, RAW_TOKEN, now=NOW)
        question = get_question(self.session, RAW_TOKEN, attempt_id=UUID(started["attempt_id"]), position=0, now=NOW)
        question_id = UUID(question["question_id"])
        index = next(i for i, q in enumerate(self.questions) if q.id == question_id)
        wrong_id = next(o.id for o in self.questions[index].options if not o.is_correct)
        with self.assertRaises(ExamError) as expired:
            save_answer(
                self.session, RAW_TOKEN, attempt_id=UUID(started["attempt_id"]),
                question_id=question_id, option_id=wrong_id,
                now=NOW + timedelta(seconds=question["time_limit_seconds"] + 1),
            )
        self.assertEqual(expired.exception.code, "question_time_expired")
        self.session.rollback()
        result = submit_exam(self.session, RAW_TOKEN, attempt_id=UUID(started["attempt_id"]), now=NOW + timedelta(seconds=60))
        self.assertEqual(result["unanswered_count"], 100)
        self.assertEqual(result["score"], "0.000")

    def test_current_attempt_supports_resume_and_persisted_result_review(self) -> None:
        started = start_exam(self.session, RAW_TOKEN, now=NOW)
        get_question(self.session, RAW_TOKEN, attempt_id=UUID(started["attempt_id"]), position=0, now=NOW)
        self.session.rollback()
        current = get_current_attempt(self.session, RAW_TOKEN, now=NOW + timedelta(minutes=1))
        self.assertEqual(current["attempt"]["status"], "in_progress")
        self.assertEqual(current["attempt"]["current_position"], 0)
        self.session.rollback()
        submit_exam(self.session, RAW_TOKEN, attempt_id=UUID(started["attempt_id"]), now=NOW + timedelta(minutes=2))
        self.session.rollback()
        current_result = get_current_attempt(self.session, RAW_TOKEN, now=NOW + timedelta(minutes=3))
        self.assertEqual(current_result["attempt"]["status"], "submitted")
        self.assertEqual(len(current_result["attempt"]["review"]), 100)

    def test_wrong_question_option_pair_is_rejected(self) -> None:
        started = start_exam(self.session, RAW_TOKEN, now=NOW)
        attempt_id = UUID(started["attempt_id"])
        question = get_question(self.session, RAW_TOKEN, attempt_id=attempt_id, position=0, now=NOW)
        wrong_question_option_id = UUID(question["options"][0]["option_id"])
        skip_question(self.session, RAW_TOKEN, attempt_id=attempt_id, position=0, now=NOW + timedelta(seconds=1))
        other = get_question(self.session, RAW_TOKEN, attempt_id=attempt_id, position=1, now=NOW + timedelta(seconds=2))
        with self.assertRaises(ExamError) as invalid:
            save_answer(
                self.session, RAW_TOKEN, attempt_id=attempt_id,
                question_id=UUID(other["question_id"]), option_id=wrong_question_option_id,
                now=NOW + timedelta(seconds=3),
            )
        self.assertEqual(invalid.exception.code, "invalid_question_or_option")

    def test_quarter_mark_negative_score_is_applied(self) -> None:
        started = start_exam(self.session, RAW_TOKEN, now=NOW)
        attempt_id = UUID(started["attempt_id"])
        for position in range(4):
            question = get_question(self.session, RAW_TOKEN, attempt_id=attempt_id, position=position, now=NOW + timedelta(seconds=position))
            question_id = UUID(question["question_id"])
            question_index = next(i for i, item in enumerate(self.questions) if item.id == question_id)
            wrong_id = next(option.id for option in self.questions[question_index].options if not option.is_correct)
            save_answer(
                self.session, RAW_TOKEN, attempt_id=attempt_id,
                question_id=question_id, option_id=wrong_id,
                now=NOW + timedelta(seconds=position + 1),
            )
        self.session.rollback()
        result = submit_exam(self.session, RAW_TOKEN, attempt_id=attempt_id, now=NOW + timedelta(seconds=10))
        self.assertEqual(result["incorrect_count"], 4)
        self.assertEqual(result["score"], "-1.000")

    def test_integrity_events_are_audited_for_active_candidate_attempts(self) -> None:
        started = start_exam(self.session, RAW_TOKEN, now=NOW)
        attempt_id = UUID(started["attempt_id"])
        recorded = record_integrity_event(
            self.session, RAW_TOKEN, attempt_id=attempt_id,
            event_type="candidate_tab_hidden",
        )
        self.assertTrue(recorded["recorded"])
        self.session.rollback()
        event = self.session.query(AuditEvent).filter_by(
            action="candidate_tab_hidden", target_id=attempt_id
        ).one()
        self.assertEqual(event.target_type, "exam_attempt")
        with self.assertRaises(ExamError) as invalid:
            record_integrity_event(
                self.session, RAW_TOKEN, attempt_id=attempt_id,
                event_type="candidate_ip_address",
            )
        self.assertEqual(invalid.exception.code, "invalid_integrity_event")

    def test_unauthenticated_candidate_cannot_access_exam(self) -> None:
        with self.assertRaises(ExamError) as rejected:
            exam_availability(self.session, None, now=NOW)
        self.assertEqual(rejected.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()

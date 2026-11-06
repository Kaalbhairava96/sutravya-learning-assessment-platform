"""Organiser API authorization, slot provisioning and question-bank import tests."""
from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.config import Settings
from app.models import Base, Candidate, Registration
from app.registration import EVENT_KEY
_test_environment = {
    "APP_ENV": "test",
    "LOG_LEVEL": "CRITICAL",
    "DATABASE_URL": "postgresql+psycopg://synthetic:synthetic@127.0.0.1:55432/sutravya_m3_test",
}
with patch.dict(os.environ, _test_environment), patch("app.config._read_dotenv", return_value={}):
    from app.main import (
        AdminQuestionBankRequest,
        AdminQuestionRequest,
        AdminOptionRequest,
        AdminSlotAssignmentRequest,
        AdminSlotRequest,
        create_app,
    )

TEST_DATABASE_URL = "postgresql+psycopg://synthetic:synthetic@127.0.0.1:55432/sutravya_m3_test"
ADMIN_KEY = "synthetic-admin-api-key-at-least-32-bytes"


def request_for(application, path: str, method: str = "POST") -> Request:
    return Request({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": b"", "headers": [(b"host", b"test.local")],
        "client": ("198.51.100.20", 43100), "server": ("test.local", 80), "app": application,
    })


def endpoint(application, path: str):
    return next(route.endpoint for route in application.routes if getattr(route, "path", None) == path)


class AssessmentAdminApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _record) -> None:
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.addCleanup(self.engine.dispose)
        settings = Settings(
            app_env="test", log_level="CRITICAL", database_url=TEST_DATABASE_URL,
            admin_api_key=ADMIN_KEY,
        )
        self.application = create_app(settings, session_factory=self.factory)
        with self.factory() as session:
            candidate = Candidate(
                full_name="Admin Test Candidate", email="admin-test@example.invalid",
                phone="+919876543210", email_verified_at=datetime.now(timezone.utc),
            )
            session.add(candidate)
            session.flush()
            session.add(Registration(
                candidate_id=candidate.id, event_key=EVENT_KEY,
                registration_id="SUT-2026/11/06-00000000001",
                stream="paramedical", status="active", registration_source="public_registration",
            ))
            session.commit()

    def test_admin_routes_fail_closed_without_valid_key(self) -> None:
        overview = endpoint(self.application, "/api/admin/assessment/overview")
        request = request_for(self.application, "/api/admin/assessment/overview", "GET")
        with self.assertRaises(HTTPException) as rejected:
            overview(request, x_admin_key="wrong-key")
        self.assertEqual(rejected.exception.status_code, 403)

        no_admin = create_app(
            Settings(app_env="test", log_level="CRITICAL", database_url=TEST_DATABASE_URL),
            session_factory=self.factory,
        )
        with self.assertRaises(HTTPException) as missing:
            endpoint(no_admin, "/api/admin/assessment/overview")(
                request_for(no_admin, "/api/admin/assessment/overview", "GET"), x_admin_key=None,
            )
        self.assertEqual(missing.exception.status_code, 503)

    def test_create_stream_slot_and_assign_only_matching_registrations(self) -> None:
        create_slot = endpoint(self.application, "/api/admin/assessment/slots")
        starts = datetime.now(timezone.utc) + timedelta(days=2)
        created = create_slot(
            AdminSlotRequest(
                stream="paramedical", starts_at=starts,
                ends_at=starts + timedelta(hours=1), capacity=1000,
            ),
            request_for(self.application, "/api/admin/assessment/slots"),
            x_admin_key=ADMIN_KEY,
        )
        self.assertEqual(created["stream"], "paramedical")
        assign = endpoint(self.application, "/api/admin/assessment/slots/{slot_id}/assign")
        assigned = assign(
            __import__("uuid").UUID(created["slot_id"]),
            AdminSlotAssignmentRequest(registration_ids=["SUT-2026/11/06-00000000001"]),
            request_for(self.application, "/api/admin/assessment/slots/assign"),
            x_admin_key=ADMIN_KEY,
        )
        self.assertEqual(assigned["assigned_count"], 1)
        with self.factory() as session:
            row = session.query(Registration).one()
            self.assertEqual(str(row.exam_slot_id), created["slot_id"])

    def test_import_exactly_one_hundred_mcqs_and_overview_counts(self) -> None:
        options = [
            AdminOptionRequest(identifier=identifier, option_text=f"Option {identifier}")
            for identifier in ("A", "B", "C", "D")
        ]
        questions = [
            AdminQuestionRequest(
                question_text=f"Approved synthetic question {number}",
                section=("anatomy", "physiology", "biology", "quantitative_reasoning", "english_communication")[(number - 1) // 20],
                difficulty="easy" if number % 2 == 0 else "moderate",
                time_limit_seconds=20 + (number % 5),
                category="General",
                explanation="Synthetic explanation",
                options=options,
                correct_identifier="A",
            )
            for number in range(1, 101)
        ]
        payload = AdminQuestionBankRequest(
            stream="paramedical", title="Paramedical HTSE 2026",
            description="Test paper", correct_points=Decimal("1"),
            questions=questions,
        )
        imported = endpoint(self.application, "/api/admin/assessment/question-banks/import")(
            payload,
            request_for(self.application, "/api/admin/assessment/question-banks/import"),
            x_admin_key=ADMIN_KEY,
        )
        self.assertEqual(imported["question_count"], 100)
        self.assertEqual(imported["negative_marking"], True)
        self.assertEqual(imported["incorrect_points"], "-0.25")
        overview = endpoint(self.application, "/api/admin/assessment/overview")(
            request_for(self.application, "/api/admin/assessment/overview", "GET"),
            x_admin_key=ADMIN_KEY,
        )
        self.assertEqual(overview["streams"]["paramedical"]["question_count"], 100)
        self.assertEqual(overview["streams"]["paramedical"]["registrations"], 1)
        with self.factory() as session:
            from app.models import Question, ScoringRule
            bank = session.query(Question).first().question_bank
            rule = session.query(ScoringRule).filter_by(question_bank_id=bank.id).one()
            self.assertEqual(str(rule.correct_points), "1.000")
            self.assertEqual(str(rule.incorrect_points), "-0.250")
            self.assertEqual(session.query(Question).filter_by(section="anatomy").count(), 20)
            self.assertEqual(session.query(Question).filter_by(section="physiology").count(), 20)
            self.assertEqual(session.query(Question).filter_by(section="biology").count(), 20)
            self.assertEqual(session.query(Question).filter_by(section="quantitative_reasoning").count(), 20)
            self.assertEqual(session.query(Question).filter_by(section="english_communication").count(), 20)


if __name__ == "__main__":
    unittest.main()

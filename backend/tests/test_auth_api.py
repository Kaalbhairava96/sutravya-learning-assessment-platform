"""Direct FastAPI route tests; SQLite only, no dotenv or network access."""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import unittest
import csv
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from unittest.mock import Mock, patch
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request
from fastapi import HTTPException

from app.config import Settings
from app.email_provider import EmailDeliveryError
from app.models import Base, Candidate, Registration, VerificationChallenge
from app.registration import LOGIN_OTP_PURPOSE, REGISTRATION_OTP_PURPOSE, create_login_challenge, verify_login_email
from app.logging_config import SafeJsonFormatter


_test_environment = {
    "APP_ENV": "test",
    "LOG_LEVEL": "CRITICAL",
    "DATABASE_URL": "postgresql+psycopg://synthetic:synthetic@127.0.0.1:55432/sutravya_m3_test",
}
with patch.dict(os.environ, _test_environment), patch("app.config._read_dotenv", return_value={}):
    from app.main import app as module_app, create_app

from app.main import (
    _log_email_delivery_failure,
    REGISTRATION_CLOSES_AT,
    REGISTRATION_OPENS_AT,
    SESSION_COOKIE,
    ConfirmationResendRequest,
    EmailOtpRequest,
    EmailRequest,
    LoginVerifyRequest,
    RegistrationRequest,
    ResendOtpRequest,
)


TEST_DATABASE_URL = _test_environment["DATABASE_URL"]
PEPPER = "api-test-pepper-value-with-at-least-32-bytes"
INTERNAL_CODE = "synthetic-internal-test-code"
EXPORT_CODE = "synthetic-export-secret-value-at-least-32-characters-long"


def route_endpoint(application, path: str):
    return next(route.endpoint for route in application.routes if getattr(route, "path", None) == path)


def request_for(application, path: str, *, method: str = "POST", cookie: str | None = None, extra_headers: dict[str, str] | None = None) -> Request:
    headers = [(b"host", b"test.local")]
    if cookie:
        headers.append((b"cookie", cookie.encode("ascii")))
    for name, value in (extra_headers or {}).items():
        headers.append((name.lower().encode("ascii"), value.encode("utf-8")))
    return Request({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": b"", "headers": headers, "client": ("198.51.100.20", 43100),
        "server": ("test.local", 80), "app": application,
    })


class PasswordlessApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.window_time = patch(
            "app.main._registration_now",
            return_value=datetime(2026, 11, 2, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
        )
        self.window_time.start()
        self.addCleanup(self.window_time.stop)
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _record) -> None:
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.settings = Settings(
            app_env="test", log_level="CRITICAL", database_url=TEST_DATABASE_URL,
            otp_hmac_pepper=PEPPER,
        )
        self.sent_codes: list[dict] = []

        def sender(**kwargs):
            self.sent_codes.append(kwargs)

        self.application = create_app(
            self.settings, session_factory=self.factory, email_sender=sender,
            confirmation_sender=lambda **kwargs: None,
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def _capture_startup_config_event(self, *, api_key: str | None, sender: str | None) -> tuple[str, dict]:
        settings = Settings(
            app_env="test", log_level="INFO", database_url=TEST_DATABASE_URL,
            otp_hmac_pepper=PEPPER, resend_api_key=api_key, resend_from_email=sender,
        )
        application = create_app(settings, session_factory=self.factory)
        logger = logging.getLogger("sutravya.api")
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(SafeJsonFormatter())
        logger.addHandler(handler)
        try:
            for startup_handler in application.router.on_startup:
                startup_handler()
        finally:
            logger.removeHandler(handler)
        serialized = output.getvalue()
        return serialized, json.loads(serialized)

    def test_startup_email_runtime_check_logs_only_expected_safe_fields(self) -> None:
        api_key = "synthetic-startup-api-key"
        sender = "SUTRAVYA <noreply@mail.sutravya.in>"
        serialized, event = self._capture_startup_config_event(api_key=api_key, sender=sender)
        self.assertEqual(event["event"], "email_runtime_config_check")
        self.assertTrue(event["resend_key_present"])
        self.assertEqual(event["resend_key_fingerprint"], hashlib.sha256(api_key.encode()).hexdigest()[:12])
        self.assertTrue(event["resend_sender_expected_match"])
        self.assertTrue(event["resend_sender_domain_match"])
        self.assertNotIn(api_key, serialized)
        self.assertNotIn(hashlib.sha256(api_key.encode()).hexdigest(), serialized)
        self.assertNotIn(sender, serialized)
        self.assertNotIn("noreply@mail.sutravya.in", serialized)

    def test_startup_email_runtime_check_reports_missing_and_mismatched_configuration_safely(self) -> None:
        serialized, event = self._capture_startup_config_event(
            api_key=None, sender="SUTRAVYA <noreply@other.example>",
        )
        self.assertFalse(event["resend_key_present"])
        self.assertEqual(event["resend_key_fingerprint"], "missing")
        self.assertFalse(event["resend_sender_expected_match"])
        self.assertFalse(event["resend_sender_domain_match"])
        self.assertNotIn("noreply@other.example", serialized)

        _serialized, event = self._capture_startup_config_event(
            api_key=None, sender="Other Sender <noreply@mail.sutravya.in>",
        )
        self.assertFalse(event["resend_sender_expected_match"])
        self.assertTrue(event["resend_sender_domain_match"])

    def test_registration_then_email_otp_login_and_cookie_session(self) -> None:
        start = route_endpoint(self.application, "/api/registrations/start")
        result = start(
            RegistrationRequest(
                full_name="Synthetic API Candidate", mobile="9876543210",
                email="api@example.invalid", stream="nursing",
            ),
            request_for(self.application, "/api/registrations/start"),
        )
        self.assertEqual(self.sent_codes[-1]["purpose"], REGISTRATION_OTP_PURPOSE)

        verify_registration = route_endpoint(self.application, "/api/registrations/verify-email")
        registered = verify_registration(
            EmailOtpRequest(challenge_id=result["challenge_id"], otp=self.sent_codes[-1]["otp"]),
            request_for(self.application, "/api/registrations/verify-email"),
        )
        self.assertRegex(registered["registration_id"], r"^SUT26-[A-F0-9]{16}$")
        self.assertTrue(registered["confirmation_email_sent"])

        request_login = route_endpoint(self.application, "/api/auth/request-otp")
        known_message = request_login(
            EmailRequest(email="api@example.invalid"), request_for(self.application, "/api/auth/request-otp")
        )
        self.assertEqual(self.sent_codes[-1]["purpose"], LOGIN_OTP_PURPOSE)
        unknown_message = request_login(
            EmailRequest(email="unknown@example.invalid"), request_for(self.application, "/api/auth/request-otp")
        )
        self.assertEqual(known_message, unknown_message)

        response = __import__("starlette.responses", fromlist=["Response"]).Response()
        verify_login = route_endpoint(self.application, "/api/auth/verify-otp")
        verified = verify_login(
            LoginVerifyRequest(email="api@example.invalid", otp=self.sent_codes[-1]["otp"]),
            request_for(self.application, "/api/auth/verify-otp"),
            response,
        )
        self.assertEqual(verified, {"status": "authenticated"})
        cookie = SimpleCookie()
        cookie.load(response.headers["set-cookie"])
        session_token = cookie[SESSION_COOKIE].value
        self.assertTrue(cookie[SESSION_COOKIE]["httponly"])
        self.assertEqual(cookie[SESSION_COOKIE]["samesite"], "lax")

        current = route_endpoint(self.application, "/api/auth/session")
        summary = current(request_for(
            self.application, "/api/auth/session", method="GET", cookie=f"{SESSION_COOKIE}={session_token}"
        ))
        self.assertEqual(summary["registration_id"], registered["registration_id"])
        self.assertEqual(summary["email"], "api@example.invalid")
        self.assertNotIn("candidate_id", summary)

        logout = route_endpoint(self.application, "/api/auth/logout")
        logout_response = __import__("starlette.responses", fromlist=["Response"]).Response()
        logout(request_for(self.application, "/api/auth/logout", cookie=f"{SESSION_COOKIE}={session_token}"), logout_response)
        with self.assertRaises(HTTPException) as unauthorized:
            current(request_for(self.application, "/api/auth/session", method="GET", cookie=f"{SESSION_COOKIE}={session_token}"))
        self.assertEqual(unauthorized.exception.status_code, 401)

    def test_registration_opening_boundary_is_inclusive_and_earlier_time_is_blocked(self) -> None:
        start = route_endpoint(self.application, "/api/registrations/start")
        payload = RegistrationRequest(
            full_name="Opening Boundary", mobile="9876543210",
            email="opening-boundary@example.invalid", stream="paramedical",
        )
        before_open = REGISTRATION_OPENS_AT - timedelta(seconds=1)
        with patch("app.main._registration_now", return_value=before_open):
            with self.assertRaises(HTTPException) as rejected:
                start(payload, request_for(self.application, "/api/registrations/start"))
        self.assertEqual(rejected.exception.status_code, 403)
        self.assertIn("Internal testing access", rejected.exception.detail)
        self.assertEqual(self.sent_codes, [])

        with patch("app.main._registration_now", return_value=REGISTRATION_OPENS_AT):
            started = start(payload, request_for(self.application, "/api/registrations/start"))
        self.assertIn("challenge_id", started)
        self.assertEqual(len(self.sent_codes), 1)

    def test_email_verification_is_allowed_at_the_last_instant_of_closing_date(self) -> None:
        start = route_endpoint(self.application, "/api/registrations/start")
        with patch("app.main._registration_now", return_value=datetime(2026, 11, 15, 23, 55, tzinfo=ZoneInfo("Asia/Kolkata"))):
            started = start(
                RegistrationRequest(
                    full_name="Closing Boundary", mobile="9876543210",
                    email="closing-boundary@example.invalid", stream="nursing",
                ),
                request_for(self.application, "/api/registrations/start"),
            )
        closing_instant = REGISTRATION_CLOSES_AT - timedelta(microseconds=1)
        with patch("app.main._registration_now", return_value=closing_instant):
            verified = route_endpoint(self.application, "/api/registrations/verify-email")(
                EmailOtpRequest(challenge_id=started["challenge_id"], otp=self.sent_codes[-1]["otp"]),
                request_for(self.application, "/api/registrations/verify-email"),
            )
        self.assertRegex(verified["registration_id"], r"^SUT26-[A-F0-9]{16}$")

    def test_expired_registration_window_blocks_start_verify_and_otp_resend(self) -> None:
        start = route_endpoint(self.application, "/api/registrations/start")
        with patch("app.main._registration_now", return_value=REGISTRATION_OPENS_AT):
            started = start(
                RegistrationRequest(
                    full_name="After Deadline", mobile="9876543210",
                    email="after-deadline@example.invalid", stream="mbbs_1st_year",
                ),
                request_for(self.application, "/api/registrations/start"),
            )
        emails_before_expiry = len(self.sent_codes)
        with patch("app.main._registration_now", return_value=REGISTRATION_CLOSES_AT):
            for path, invoke in (
                ("/api/registrations/start", lambda: start(
                    RegistrationRequest(
                        full_name="Late Candidate", mobile="9876543211",
                        email="late-candidate@example.invalid", stream="nursing",
                    ), request_for(self.application, "/api/registrations/start"),
                )),
                ("/api/registrations/verify-email", lambda: route_endpoint(self.application, path)(
                    EmailOtpRequest(challenge_id=started["challenge_id"], otp=self.sent_codes[-1]["otp"]),
                    request_for(self.application, path),
                )),
                ("/api/registrations/resend-otp", lambda: route_endpoint(self.application, path)(
                    ResendOtpRequest(challenge_id=started["challenge_id"]), request_for(self.application, path),
                )),
            ):
                with self.subTest(path=path), self.assertRaises(HTTPException) as rejected:
                    invoke()
                self.assertEqual(rejected.exception.status_code, 410)
                self.assertIn("Registration closed", rejected.exception.detail)
        self.assertEqual(len(self.sent_codes), emails_before_expiry)
        with self.factory() as session:
            self.assertEqual(session.query(Registration).count(), 0)

    def test_all_three_streams_are_accepted_during_registration_window(self) -> None:
        start = route_endpoint(self.application, "/api/registrations/start")
        for index, stream in enumerate(("paramedical", "nursing", "mbbs_1st_year")):
            with self.subTest(stream=stream):
                result = start(
                    RegistrationRequest(
                        full_name="Stream Candidate", mobile=f"987654321{index}",
                        email=f"stream-{stream}@example.invalid", stream=stream,
                    ),
                    request_for(self.application, "/api/registrations/start"),
                )
                self.assertIn("challenge_id", result)

    def _internal_app(self):
        settings = Settings(
            app_env="test", log_level="CRITICAL", database_url=TEST_DATABASE_URL,
            otp_hmac_pepper=PEPPER, internal_test_mode=True,
            internal_test_access_code=INTERNAL_CODE,
        )
        return create_app(
            settings, session_factory=self.factory, email_sender=lambda **kwargs: self.sent_codes.append(kwargs),
            confirmation_sender=lambda **_kwargs: None,
        )

    def _start_payload(self, email="internal@example.invalid"):
        return RegistrationRequest(full_name="Internal Rehearsal", mobile="9876543210", email=email, stream="nursing")

    def _at(self, value):
        return patch("app.main._registration_now", return_value=value)

    def test_internal_mode_disabled_rejects_prelaunch_registration(self) -> None:
        start = route_endpoint(self.application, "/api/registrations/start")
        with self._at(datetime(2026, 10, 31, 23, 59, tzinfo=ZoneInfo("Asia/Kolkata"))):
            with self.assertRaises(HTTPException) as rejected:
                start(self._start_payload(), request_for(self.application, "/api/registrations/start"))
        self.assertEqual(rejected.exception.status_code, 403)
        self.assertEqual(self.sent_codes, [])

    def test_internal_mode_correct_code_creates_team_prelaunch_challenge_not_internal_test(self) -> None:
        application = self._internal_app()
        with self._at(datetime(2026, 10, 31, 23, 59, tzinfo=ZoneInfo("Asia/Kolkata"))):
            result = route_endpoint(application, "/api/registrations/start")(
                self._start_payload(),
                request_for(application, "/api/registrations/start", extra_headers={"X-Internal-Test-Code": INTERNAL_CODE}),
            )
        with self.factory() as session:
            challenge = session.get(VerificationChallenge, UUID(result["challenge_id"]))
            self.assertFalse(challenge.is_internal_test)
            self.assertEqual(challenge.registration_source, "team_prelaunch")

    def test_incorrect_internal_code_is_rejected(self) -> None:
        application = self._internal_app()
        with self._at(datetime(2026, 10, 31, 23, 59, tzinfo=ZoneInfo("Asia/Kolkata"))):
            with self.assertRaises(HTTPException) as rejected:
                route_endpoint(application, "/api/registrations/start")(
                    self._start_payload(),
                    request_for(application, "/api/registrations/start", extra_headers={"X-Internal-Test-Code": "wrong"}),
                )
        self.assertEqual(rejected.exception.status_code, 403)
        self.assertEqual(self.sent_codes, [])

    def test_team_prelaunch_verification_creates_normal_candidate_eligible_for_login(self) -> None:
        application = self._internal_app()
        header = {"X-Internal-Test-Code": INTERNAL_CODE}
        with self._at(datetime(2026, 10, 31, 23, 59, tzinfo=ZoneInfo("Asia/Kolkata"))):
            started = route_endpoint(application, "/api/registrations/start")(
                self._start_payload(), request_for(application, "/api/registrations/start", extra_headers=header),
            )
            verified = route_endpoint(application, "/api/registrations/verify-email")(
                EmailOtpRequest(challenge_id=started["challenge_id"], otp=self.sent_codes[-1]["otp"]),
                request_for(application, "/api/registrations/verify-email", extra_headers=header),
            )
        self.assertEqual(verified["registration_source"], "team_prelaunch")
        with self.factory() as session:
            registration = session.query(Registration).one()
            candidate = session.get(Candidate, registration.candidate_id)
            candidate_email = candidate.email
            self.assertFalse(registration.is_internal_test)
            self.assertEqual(registration.status, "active")
            self.assertEqual(registration.registration_source, "team_prelaunch")
        with self.factory() as session:
            login_challenge = create_login_challenge(
                session, settings=application.state.settings, email=candidate_email,
            )
            self.assertIsNotNone(login_challenge)
            outcome, login = verify_login_email(
                session, settings=application.state.settings, email=candidate_email, otp=login_challenge.otp,
            )
        self.assertEqual(outcome.value, "verified")
        self.assertIsNotNone(login)
        self.assertEqual(login.registration_id, verified["registration_id"])

    def test_internal_resend_requires_code_and_keeps_team_registration_source(self) -> None:
        application = self._internal_app()
        header = {"X-Internal-Test-Code": INTERNAL_CODE}
        with self._at(datetime(2026, 10, 31, 23, 59, tzinfo=ZoneInfo("Asia/Kolkata"))):
            started = route_endpoint(application, "/api/registrations/start")(
                self._start_payload(), request_for(application, "/api/registrations/start", extra_headers=header),
            )
            resend = route_endpoint(application, "/api/registrations/resend-otp")
            with self.assertRaises(HTTPException) as rejected:
                resend(ResendOtpRequest(challenge_id=started["challenge_id"]), request_for(application, "/api/registrations/resend-otp"))
            self.assertEqual(rejected.exception.status_code, 403)
            with self.factory() as session:
                session.get(VerificationChallenge, UUID(started["challenge_id"])).created_at = datetime(
                    2026, 10, 31, 18, 25, tzinfo=timezone.utc
                )
                session.commit()
            resent = resend(
                ResendOtpRequest(challenge_id=started["challenge_id"]),
                request_for(application, "/api/registrations/resend-otp", extra_headers=header),
            )
        with self.factory() as session:
            replacement = session.get(VerificationChallenge, UUID(resent["challenge_id"]))
            self.assertFalse(replacement.is_internal_test)
            self.assertEqual(replacement.registration_source, "team_prelaunch")

    def test_public_registration_opens_without_code_and_has_public_source(self) -> None:
        with self._at(REGISTRATION_OPENS_AT):
            started = route_endpoint(self.application, "/api/registrations/start")(
                self._start_payload("official@example.invalid"), request_for(self.application, "/api/registrations/start"),
            )
        with self.factory() as session:
            challenge = session.get(VerificationChallenge, UUID(started["challenge_id"]))
            self.assertFalse(challenge.is_internal_test)
            self.assertEqual(challenge.registration_source, "public_registration")

    def test_team_prelaunch_candidate_needs_no_second_registration_on_opening_day(self) -> None:
        application = self._internal_app()
        code_header = {"X-Internal-Test-Code": INTERNAL_CODE}
        payload = self._start_payload("same-candidate@example.invalid")
        with self._at(datetime(2026, 10, 31, 23, 59, tzinfo=ZoneInfo("Asia/Kolkata"))):
            internal = route_endpoint(application, "/api/registrations/start")(
                payload, request_for(application, "/api/registrations/start", extra_headers=code_header),
            )
        with self._at(REGISTRATION_OPENS_AT):
            team_result = route_endpoint(application, "/api/registrations/verify-email")(
                EmailOtpRequest(challenge_id=internal["challenge_id"], otp=self.sent_codes[-1]["otp"]),
                request_for(application, "/api/registrations/verify-email"),
            )
        self.assertEqual(team_result["registration_source"], "team_prelaunch")
        with self._at(REGISTRATION_OPENS_AT):
            duplicate_attempt = route_endpoint(application, "/api/registrations/start")(
                payload, request_for(application, "/api/registrations/start"),
            )
        self.assertNotIn("challenge_id", duplicate_attempt)
        with self.factory() as session:
            self.assertEqual(session.query(Registration).count(), 1)

    def test_prelaunch_access_code_is_unnecessary_at_open_for_new_public_registration(self) -> None:
        application = self._internal_app()
        header = {"X-Internal-Test-Code": INTERNAL_CODE}
        with self._at(REGISTRATION_OPENS_AT):
            started = route_endpoint(application, "/api/registrations/start")(
                self._start_payload("public-after-open@example.invalid"),
                request_for(application, "/api/registrations/start"),
            )
        with self.factory() as session:
            self.assertEqual(
                session.get(VerificationChallenge, UUID(started["challenge_id"])).registration_source,
                "public_registration",
            )

    def test_closing_boundary_rejects_internal_and_public_start_verify_and_resend(self) -> None:
        application = self._internal_app()
        header = {"X-Internal-Test-Code": INTERNAL_CODE}
        with self._at(datetime(2026, 10, 31, 23, 59, tzinfo=ZoneInfo("Asia/Kolkata"))):
            started = route_endpoint(application, "/api/registrations/start")(
                self._start_payload(), request_for(application, "/api/registrations/start", extra_headers=header),
            )
        operations = (
            ("start", lambda: route_endpoint(application, "/api/registrations/start")(
                self._start_payload("late@example.invalid"), request_for(application, "/api/registrations/start"))),
            ("verify", lambda: route_endpoint(application, "/api/registrations/verify-email")(
                EmailOtpRequest(challenge_id=started["challenge_id"], otp=self.sent_codes[-1]["otp"]), request_for(application, "/api/registrations/verify-email"))),
            ("resend", lambda: route_endpoint(application, "/api/registrations/resend-otp")(
                ResendOtpRequest(challenge_id=started["challenge_id"]), request_for(application, "/api/registrations/resend-otp"))),
        )
        with self._at(REGISTRATION_CLOSES_AT):
            for name, invoke in operations:
                with self.subTest(operation=name), self.assertRaises(HTTPException) as rejected:
                    invoke()
                self.assertEqual(rejected.exception.status_code, 410)
            with self.assertRaises(HTTPException) as internal_start:
                route_endpoint(application, "/api/registrations/start")(
                    self._start_payload("late-internal@example.invalid"),
                    request_for(application, "/api/registrations/start", extra_headers=header),
                )
            self.assertEqual(internal_start.exception.status_code, 410)

    def test_internal_testing_cors_header_is_allowed(self) -> None:
        settings = Settings(
            app_env="test", log_level="CRITICAL", database_url=TEST_DATABASE_URL,
            otp_hmac_pepper=PEPPER, cors_origins=("https://assessment.sutravya.in",),
        )
        application = create_app(settings, session_factory=self.factory)
        cors = next(middleware for middleware in application.user_middleware if middleware.cls.__name__ == "CORSMiddleware")
        self.assertIn("X-Internal-Test-Code", cors.kwargs["allow_headers"])

    def _export_app_with_synthetic_rows(self):
        settings = Settings(
            app_env="test", log_level="CRITICAL", database_url=TEST_DATABASE_URL,
            otp_hmac_pepper=PEPPER, registration_export_key=EXPORT_CODE,
        )
        application = create_app(settings, session_factory=self.factory)
        with self.factory() as session:
            team = Candidate(
                full_name='=HYPERLINK("https://formula.invalid","click")',
                email="team@example.invalid", phone="+919876543210",
                email_verified_at=datetime(2026, 10, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
            )
            public = Candidate(
                full_name="Public Candidate", email="public@example.invalid", phone="+919876543211",
                email_verified_at=datetime(2026, 11, 2, tzinfo=ZoneInfo("Asia/Kolkata")),
            )
            session.add_all([team, public])
            session.flush()
            session.add_all([
                Registration(
                    candidate_id=team.id, event_key="BHC-2026", registration_id="SUT26-TEAMTEST",
                    stream="nursing", status="active", registration_source="team_prelaunch",
                ),
                Registration(
                    candidate_id=team.id, event_key="BHC-2026", registration_id="SUT26-LEGACYTEST",
                    stream="nursing", status="active", is_internal_test=True,
                    registration_source="legacy_internal_test",
                ),
                Registration(
                    candidate_id=public.id, event_key="BHC-2026", registration_id="SUT26-PUBLICTEST",
                    stream="paramedical", status="active", registration_source="public_registration",
                ),
            ])
            session.commit()
        return application

    def test_registration_export_requires_configured_key_and_rejects_invalid_token(self) -> None:
        endpoint = route_endpoint(self.application, "/api/admin/registrations/export")
        with self.assertRaises(HTTPException) as missing_config:
            endpoint(request_for(self.application, "/api/admin/registrations/export"))
        self.assertEqual(missing_config.exception.status_code, 503)
        application = self._export_app_with_synthetic_rows()
        with self.assertRaises(HTTPException) as unauthorized:
            route_endpoint(application, "/api/admin/registrations/export")(
                request_for(application, "/api/admin/registrations/export"),
                x_registration_export_key="incorrect-export-key",
            )
        self.assertEqual(unauthorized.exception.status_code, 403)

    def test_registration_export_filters_sources_includes_verification_and_has_utf8_bom(self) -> None:
        application = self._export_app_with_synthetic_rows()
        export = route_endpoint(application, "/api/admin/registrations/export")
        request = request_for(application, "/api/admin/registrations/export", method="GET")
        all_response = export(request, x_registration_export_key=EXPORT_CODE)
        self.assertEqual(all_response.status_code, 200)
        self.assertTrue(all_response.body.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.DictReader(io.StringIO(all_response.body.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 3)
        legacy_rows = [row for row in rows if row["registration_id"] == "SUT26-LEGACYTEST"]
        self.assertEqual(len(legacy_rows), 1)
        self.assertEqual(legacy_rows[0]["registration_source"], "legacy_internal_test")
        self.assertEqual(set(rows[0]), {
            "registration_id", "full_name", "email", "mobile", "stream", "registration_date_ist",
            "email_verified", "mobile_verified", "registration_source",
        })
        team = export(request, source="team_prelaunch", x_registration_export_key=EXPORT_CODE)
        team_rows = list(csv.DictReader(io.StringIO(team.body.decode("utf-8-sig"))))
        self.assertEqual(len(team_rows), 1)
        self.assertEqual(team_rows[0]["registration_id"], "SUT26-TEAMTEST")
        self.assertEqual(team_rows[0]["registration_source"], "team_prelaunch")
        self.assertEqual(team_rows[0]["email_verified"], "yes")
        self.assertEqual(team_rows[0]["mobile_verified"], "no")
        public = export(request, source="public_registration", x_registration_export_key=EXPORT_CODE)
        public_rows = list(csv.DictReader(io.StringIO(public.body.decode("utf-8-sig"))))
        self.assertEqual(len(public_rows), 1)
        self.assertEqual(public_rows[0]["registration_source"], "public_registration")

    def test_registration_export_all_labels_legacy_and_official_filters_exclude_it(self) -> None:
        application = self._export_app_with_synthetic_rows()
        export = route_endpoint(application, "/api/admin/registrations/export")
        request = request_for(application, "/api/admin/registrations/export", method="GET")
        all_rows = list(csv.DictReader(io.StringIO(export(
            request, source="all", x_registration_export_key=EXPORT_CODE,
        ).body.decode("utf-8-sig"))))
        self.assertEqual(
            [row["registration_id"] for row in all_rows if row["registration_source"] == "legacy_internal_test"],
            ["SUT26-LEGACYTEST"],
        )
        for source in ("team_prelaunch", "public_registration"):
            rows = list(csv.DictReader(io.StringIO(export(
                request, source=source, x_registration_export_key=EXPORT_CODE,
            ).body.decode("utf-8-sig"))))
            self.assertTrue(all(row["registration_source"] == source for row in rows))
            self.assertNotIn("SUT26-LEGACYTEST", {row["registration_id"] for row in rows})

    def test_registration_export_neutralizes_formula_in_candidate_text(self) -> None:
        application = self._export_app_with_synthetic_rows()
        response = route_endpoint(application, "/api/admin/registrations/export")(
            request_for(application, "/api/admin/registrations/export", method="GET"),
            source="team_prelaunch", x_registration_export_key=EXPORT_CODE,
        )
        rows = list(csv.DictReader(io.StringIO(response.body.decode("utf-8-sig"))))
        self.assertTrue(rows[0]["full_name"].startswith("'=HYPERLINK("))
        self.assertNotIn(EXPORT_CODE, response.body.decode("utf-8-sig"))

    def test_failed_otp_submission_returns_unavailable_and_invalidates_challenge(self) -> None:
        failing_app = create_app(
            self.settings,
            session_factory=self.factory,
            email_sender=lambda **_kwargs: (_ for _ in ()).throw(EmailDeliveryError("private provider detail")),
        )
        start = route_endpoint(failing_app, "/api/registrations/start")
        with self.assertRaises(HTTPException) as failed:
            start(
                RegistrationRequest(
                    full_name="Synthetic Candidate", mobile="9876543210",
                    email="failure@example.invalid", stream="paramedical",
                ),
                request_for(failing_app, "/api/registrations/start"),
            )
        self.assertEqual(failed.exception.status_code, 503)
        with self.factory() as session:
            challenge = session.query(VerificationChallenge).one()
            candidate = session.get(Candidate, challenge.candidate_id)
            self.assertIsNotNone(challenge.invalidated_at)
            self.assertIsNone(candidate.email_verified_at)
            self.assertEqual(session.query(Registration).count(), 0)

    def test_confirmation_failure_keeps_committed_registration_and_resend_does_not_duplicate(self) -> None:
        codes: list[dict] = []
        failing_app = create_app(
            self.settings,
            session_factory=self.factory,
            email_sender=lambda **kwargs: codes.append(kwargs),
            confirmation_sender=lambda **_kwargs: (_ for _ in ()).throw(EmailDeliveryError("private provider detail")),
        )
        start = route_endpoint(failing_app, "/api/registrations/start")
        started = start(
            RegistrationRequest(
                full_name="Synthetic Retry Candidate", mobile="9876543211",
                email="confirm-retry@example.invalid", stream="mbbs_1st_year",
            ),
            request_for(failing_app, "/api/registrations/start"),
        )
        verified = route_endpoint(failing_app, "/api/registrations/verify-email")(
            EmailOtpRequest(challenge_id=started["challenge_id"], otp=codes[-1]["otp"]),
            request_for(failing_app, "/api/registrations/verify-email"),
        )
        self.assertFalse(verified["confirmation_email_sent"])
        with self.factory() as session:
            self.assertEqual(session.query(Registration).count(), 1)

        failing_app.state.confirmation_sender = lambda **_kwargs: None
        resent = route_endpoint(failing_app, "/api/registrations/resend-confirmation")(
            ConfirmationResendRequest(registration_id=verified["registration_id"]),
            request_for(failing_app, "/api/registrations/resend-confirmation"),
        )
        self.assertEqual(resent["message"], "If the registration is eligible, a confirmation email will be sent.")
        with self.factory() as session:
            self.assertEqual(session.query(Registration).count(), 1)

    def test_structured_security_events_never_include_private_values(self) -> None:
        import logging
        record = logging.LogRecord("sutravya.api", logging.WARNING, "test", 1, "email_delivery_failed", (), None)
        record.purpose = REGISTRATION_OTP_PURPOSE
        record.failure_kind = "provider_http_error"
        record.provider_status_code = 401
        record.provider_error_name = "restricted_api_key"
        record.provider_error_kind = "api_key_permission"
        record.otp = "123456"
        record.email = "candidate@example.invalid"
        record.api_key = "synthetic-api-key"
        record.body = "private provider body"
        record.provider_message = "private exception message"
        record.sender = "SUTRAVYA <private-sender@example.invalid>"
        record.recipient = "private-recipient@example.invalid"
        output = SafeJsonFormatter().format(record)
        self.assertIn('"event":"email_delivery_failed"', output)
        self.assertIn('"purpose":"registration_verification"', output)
        self.assertIn('"failure_kind":"provider_http_error"', output)
        self.assertIn('"provider_status_code":401', output)
        self.assertIn('"provider_error_name":"restricted_api_key"', output)
        self.assertIn('"provider_error_kind":"api_key_permission"', output)
        self.assertNotIn("123456", output)
        self.assertNotIn("candidate@example.invalid", output)
        self.assertNotIn("synthetic-api-key", output)
        self.assertNotIn("private provider body", output)
        self.assertNotIn("private exception message", output)
        self.assertNotIn("private-sender@example.invalid", output)
        self.assertNotIn("private-recipient@example.invalid", output)

        record.provider_error_name = "unapproved provider text with PII"
        record.provider_error_kind = "raw provider message"
        output = SafeJsonFormatter().format(record)
        self.assertNotIn("unapproved provider text", output)
        self.assertNotIn("raw provider message", output)

    def test_email_failure_logger_receives_only_allowlisted_diagnostics(self) -> None:
        logger = Mock()
        error = EmailDeliveryError(
            "private exception with OTP 123456 and candidate@example.invalid",
            failure_kind="provider_http_error",
            provider_status_code=403,
            provider_error_name="validation_error",
            provider_error_kind="domain_verification",
        )
        _log_email_delivery_failure(logger, purpose=REGISTRATION_OTP_PURPOSE, error=error)
        logger.warning.assert_called_once_with(
            "email_delivery_failed",
            extra={
                "purpose": REGISTRATION_OTP_PURPOSE,
                "failure_kind": "provider_http_error",
                "provider_status_code": 403,
                "provider_error_name": "validation_error",
                "provider_error_kind": "domain_verification",
            },
        )


if __name__ == "__main__":
    unittest.main()

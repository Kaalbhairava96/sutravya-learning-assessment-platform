"""Direct FastAPI route tests; SQLite only, no dotenv or network access."""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import unittest
from http.cookies import SimpleCookie
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request
from fastapi import HTTPException

from app.config import Settings
from app.email_provider import EmailDeliveryError
from app.models import Base, Candidate, Registration, VerificationChallenge
from app.registration import LOGIN_OTP_PURPOSE, REGISTRATION_OTP_PURPOSE
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
    SESSION_COOKIE,
    ConfirmationResendRequest,
    EmailOtpRequest,
    EmailRequest,
    LoginVerifyRequest,
    RegistrationRequest,
)


TEST_DATABASE_URL = _test_environment["DATABASE_URL"]
PEPPER = "api-test-pepper-value-with-at-least-32-bytes"


def route_endpoint(application, path: str):
    return next(route.endpoint for route in application.routes if getattr(route, "path", None) == path)


def request_for(application, path: str, *, method: str = "POST", cookie: str | None = None) -> Request:
    headers = [(b"host", b"test.local")]
    if cookie:
        headers.append((b"cookie", cookie.encode("ascii")))
    return Request({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": b"", "headers": headers, "client": ("198.51.100.20", 43100),
        "server": ("test.local", 80), "app": application,
    })


class PasswordlessApiTests(unittest.TestCase):
    def setUp(self) -> None:
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

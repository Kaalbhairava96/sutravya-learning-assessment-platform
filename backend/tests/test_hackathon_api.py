"""Free Healthcare Innovation Hackathon registration and portal route tests."""

from __future__ import annotations

import os
import unittest
from http.cookies import SimpleCookie
from unittest.mock import patch

from sqlalchemy import create_engine, event, select
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request
from starlette.responses import Response

from app.config import Settings
from app.models import Base, HackathonRegistration, Registration

TEST_DATABASE_URL = "postgresql+psycopg://synthetic:synthetic@127.0.0.1:55432/sutravya_m3_test"
_TEST_ENVIRONMENT = {
    "APP_ENV": "test",
    "LOG_LEVEL": "CRITICAL",
    "DATABASE_URL": TEST_DATABASE_URL,
}
with patch.dict(os.environ, _TEST_ENVIRONMENT), patch("app.config._read_dotenv", return_value={}):
    from app.main import (
        HACKATHON_SESSION_COOKIE,
        EmailOtpRequest,
        HackathonLoginRequest,
        HackathonRegistrationRequest,
        create_app,
    )

OTP_PEPPER = "hackathon-test-pepper-value-with-at-least-32-bytes"


def request_for(application, path: str, *, method: str = "POST", cookie: str | None = None) -> Request:
    headers = [(b"host", b"test.local")]
    if cookie:
        headers.append((b"cookie", cookie.encode("ascii")))
    return Request({
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers,
        "client": ("198.51.100.21", 43100),
        "server": ("test.local", 80),
        "app": application,
    })


def endpoint(application, path: str):
    return next(route.endpoint for route in application.routes if getattr(route, "path", None) == path)


class HackathonRegistrationFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _record) -> None:
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.settings = Settings(
            app_env="test",
            log_level="CRITICAL",
            database_url=TEST_DATABASE_URL,
            otp_hmac_pepper=OTP_PEPPER,
        )
        self.sent_codes: list[dict] = []
        self.confirmations: list[dict] = []
        self.instructions: list[dict] = []

        def email_sender(**kwargs):
            self.sent_codes.append(kwargs)

        self.application = create_app(
            self.settings,
            session_factory=self.factory,
            email_sender=email_sender,
            hackathon_confirmation_sender=lambda **kwargs: self.confirmations.append(kwargs),
            hackathon_instructions_sender=lambda **kwargs: self.instructions.append(kwargs),
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_free_registration_email_otp_login_and_logout(self) -> None:
        payload = HackathonRegistrationRequest(
            full_name="Aarav Sharma",
            email="aarav.hackathon@example.invalid",
            mobile="+91 98765 43210",
            college_name="Institute of Health Sciences",
            year_of_study=2,
            address="12 Health Avenue, Patna, Bihar",
            pin_code="800001",
        )
        start_result = endpoint(self.application, "/api/hackathon/registrations/start")(
            payload,
            request_for(self.application, "/api/hackathon/registrations/start"),
        )
        self.assertIn("challenge_id", start_result)
        self.assertEqual(self.sent_codes[-1]["purpose"], "hackathon_registration_verification")
        self.assertEqual(self.sent_codes[-1]["recipient_email"], "aarav.hackathon@example.invalid")

        registered = endpoint(self.application, "/api/hackathon/registrations/verify-email")(
            EmailOtpRequest(
                challenge_id=start_result["challenge_id"],
                otp=self.sent_codes[-1]["otp"],
            ),
            request_for(self.application, "/api/hackathon/registrations/verify-email"),
        )
        self.assertRegex(registered["registration_id"], r"^HTSE26-HK-[A-F0-9]{10}$")
        self.assertTrue(registered["confirmation_email_sent"])
        self.assertTrue(registered["submission_instructions_email_sent"])
        self.assertEqual(len(self.confirmations), 1)
        self.assertEqual(len(self.instructions), 1)
        self.assertEqual(self.instructions[0]["recipient_email"], payload.email)

        with self.factory() as session:
            rows = session.scalars(select(HackathonRegistration)).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].status, "registered")
            self.assertEqual(rows[0].year_of_study, 2)
            self.assertEqual(rows[0].pin_code, "800001")
            self.assertEqual(session.scalars(select(Registration)).all(), [])

        login_start = endpoint(self.application, "/api/hackathon/auth/request-otp")(
            HackathonLoginRequest(
                registration_id=registered["registration_id"],
                email=payload.email,
            ),
            request_for(self.application, "/api/hackathon/auth/request-otp"),
        )
        self.assertIsNotNone(login_start["challenge_id"])
        self.assertEqual(self.sent_codes[-1]["purpose"], "hackathon_login")
        login_response = Response()
        login_result = endpoint(self.application, "/api/hackathon/auth/verify-otp")(
            EmailOtpRequest(
                challenge_id=login_start["challenge_id"],
                otp=self.sent_codes[-1]["otp"],
            ),
            request_for(self.application, "/api/hackathon/auth/verify-otp"),
            login_response,
        )
        self.assertEqual(login_result["status"], "authenticated")
        cookie = SimpleCookie()
        cookie.load(login_response.headers["set-cookie"])
        token = cookie[HACKATHON_SESSION_COOKIE].value
        self.assertTrue(cookie[HACKATHON_SESSION_COOKIE]["httponly"])

        profile = endpoint(self.application, "/api/hackathon/auth/session")(
            request_for(
                self.application,
                "/api/hackathon/auth/session",
                method="GET",
                cookie=f"{HACKATHON_SESSION_COOKIE}={token}",
            )
        )
        self.assertEqual(profile["registration_id"], registered["registration_id"])
        self.assertEqual(profile["full_name"], "Aarav Sharma")
        self.assertEqual(profile["college_name"], "Institute of Health Sciences")
        self.assertEqual(profile["year_of_study"], 2)
        self.assertEqual(profile["submission_email"], "sutravya.connect@gmail.com")

        logout_response = Response()
        endpoint(self.application, "/api/hackathon/auth/logout")(
            request_for(
                self.application,
                "/api/hackathon/auth/logout",
                cookie=f"{HACKATHON_SESSION_COOKIE}={token}",
            ),
            logout_response,
        )
        self.assertEqual(logout_response.status_code, 204)
        with self.assertRaises(HTTPException):
            endpoint(self.application, "/api/hackathon/auth/session")(
                request_for(
                    self.application,
                    "/api/hackathon/auth/session",
                    method="GET",
                    cookie=f"{HACKATHON_SESSION_COOKIE}={token}",
                )
            )

    def test_registration_id_and_email_must_match_for_login(self) -> None:
        result = endpoint(self.application, "/api/hackathon/auth/request-otp")(
            HackathonLoginRequest(
                registration_id="HTSE26-HK-0000000000",
                email="wrong@example.invalid",
            ),
            request_for(self.application, "/api/hackathon/auth/request-otp"),
        )
        self.assertIsNone(result["challenge_id"])
        self.assertEqual(self.sent_codes, [])


if __name__ == "__main__":
    unittest.main()

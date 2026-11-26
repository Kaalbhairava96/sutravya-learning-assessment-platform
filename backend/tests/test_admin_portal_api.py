"""Authenticated admin portal tests: setup, sessions, safe database browsing and audited edits."""
from __future__ import annotations

import os
import unittest
from uuid import UUID
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.config import Settings
from app.models import AdminPasswordReset, AdminSession, AdminUser, AuditEvent, Base, Candidate

TEST_DATABASE_URL = "postgresql+psycopg://synthetic:synthetic@127.0.0.1:55432/sutravya_m3_test"
with patch.dict(os.environ, {"APP_ENV": "test", "LOG_LEVEL": "CRITICAL", "DATABASE_URL": TEST_DATABASE_URL}), patch("app.config._read_dotenv", return_value={}):
    from app.main import create_app
    from app.admin_router import (AdminCredentials, AdminPasswordResetConfirm, AdminPasswordResetRequest, RecordPatch, router as secure_admin_router)

BOOTSTRAP = "one-time-bootstrap-token-for-tests-only-32-bytes"
SESSION_SECRET = "admin-session-signing-and-rate-limit-test-secret-32-bytes"
ADMIN_ORIGIN = "https://admin.example.invalid"


def endpoint(app, path):
    for route in app.routes:
        if getattr(route, "path", None) == path:
            return route.endpoint
    # FastAPI keeps included APIRouter routes nested in current releases.
    for route in secure_admin_router.routes:
        if getattr(route, "path", None) == path or getattr(route, "path", None) == path.removeprefix("/api/admin"):
            return route.endpoint
    raise AssertionError("Admin route is not registered: " + path)


def request_for(app, path, method="GET", token=None, *, csrf=False, origin=None):
    headers = [(b"host", b"admin.example.invalid")]
    if token:
        headers.append((b"authorization", ("Bearer " + token).encode("ascii")))
    if csrf:
        headers.append((b"x-admin-request", b"1"))
    if origin:
        headers.append((b"origin", origin.encode("ascii")))
    return Request({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "https", "path": path, "raw_path": path.encode(),
        "query_string": b"", "headers": headers, "client": ("198.51.100.21", 43100),
        "server": ("admin.example.invalid", 443), "app": app,
    })


class AdminPortalTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.addCleanup(self.engine.dispose)
        self.sent_admin_reset_emails = []
        self.app = create_app(
            Settings(
                app_env="test", log_level="CRITICAL", database_url=TEST_DATABASE_URL,
                admin_bootstrap_token=BOOTSTRAP, admin_session_secret=SESSION_SECRET,
                admin_frontend_origin=ADMIN_ORIGIN,
            ),
            session_factory=self.factory,
            email_sender=lambda **kwargs: self.sent_admin_reset_emails.append(kwargs),
        )

    def setup_owner(self):
        result = endpoint(self.app, "/api/admin/auth/setup")(
            AdminCredentials(email="owner@example.invalid", password="a-long-test-only-password-phrase"),
            request_for(self.app, "/api/admin/auth/setup", "POST", csrf=True, origin=ADMIN_ORIGIN),
            x_admin_bootstrap_token=BOOTSTRAP,
        )
        return result["access_token"]

    def test_setup_requires_one_time_token_and_is_one_time(self):
        status = endpoint(self.app, "/api/admin/auth/status")
        self.assertTrue(status(request_for(self.app, "/api/admin/auth/status"))["setup_required"])
        with self.assertRaises(HTTPException) as rejected:
            endpoint(self.app, "/api/admin/auth/setup")(
                AdminCredentials(email="owner@example.invalid", password="a-long-test-only-password-phrase"),
                request_for(self.app, "/api/admin/auth/setup", "POST", csrf=True, origin=ADMIN_ORIGIN),
                x_admin_bootstrap_token="wrong-token",
            )
        self.assertEqual(rejected.exception.status_code, 403)
        self.setup_owner()
        self.assertFalse(status(request_for(self.app, "/api/admin/auth/status"))["setup_required"])
        with self.assertRaises(HTTPException) as second:
            endpoint(self.app, "/api/admin/auth/setup")(
                AdminCredentials(email="another@example.invalid", password="a-long-test-only-password-phrase"),
                request_for(self.app, "/api/admin/auth/setup", "POST", csrf=True, origin=ADMIN_ORIGIN),
                x_admin_bootstrap_token=BOOTSTRAP,
            )
        self.assertEqual(second.exception.status_code, 409)

    def test_login_issues_bearer_token_and_logout_revokes_it(self):
        self.setup_owner()
        result = endpoint(self.app, "/api/admin/auth/login")(
            AdminCredentials(email="owner@example.invalid", password="a-long-test-only-password-phrase"),
            request_for(self.app, "/api/admin/auth/login", "POST", csrf=True, origin=ADMIN_ORIGIN),
        )
        token = result["access_token"]
        me = endpoint(self.app, "/api/admin/auth/me")
        self.assertEqual(me(request_for(self.app, "/api/admin/auth/me", token=token))["administrator"]["email"], "owner@example.invalid")
        endpoint(self.app, "/api/admin/auth/logout")(
            request_for(self.app, "/api/admin/auth/logout", "POST", token, csrf=True, origin=ADMIN_ORIGIN)
        )
        with self.assertRaises(HTTPException) as rejected:
            me(request_for(self.app, "/api/admin/auth/me", token=token))
        self.assertEqual(rejected.exception.status_code, 401)


    def test_password_reset_request_does_not_reveal_unknown_admin_emails(self):
        token = self.setup_owner()
        request_endpoint = endpoint(self.app, "/api/admin/auth/password-reset/request")
        known = request_endpoint(
            AdminPasswordResetRequest(email="owner@example.invalid"),
            request_for(self.app, "/api/admin/auth/password-reset/request", "POST", token, csrf=True, origin=ADMIN_ORIGIN),
        )
        self.assertEqual(known["message"], "If an active administrator account matches this email, a reset code has been sent. Check your inbox and spam folder.")
        self.assertEqual(len(self.sent_admin_reset_emails), 1)
        self.assertEqual(self.sent_admin_reset_emails[0]["purpose"], "admin_password_reset")
        self.assertEqual(self.sent_admin_reset_emails[0]["recipient_email"], "owner@example.invalid")

        unknown = request_endpoint(
            AdminPasswordResetRequest(email="not-an-admin@example.invalid"),
            request_for(self.app, "/api/admin/auth/password-reset/request", "POST", csrf=True, origin=ADMIN_ORIGIN),
        )
        self.assertEqual(unknown, known)
        self.assertEqual(len(self.sent_admin_reset_emails), 1)

        with self.factory() as session:
            challenge = session.query(AdminPasswordReset).one()
            self.assertNotEqual(challenge.otp_digest, self.sent_admin_reset_emails[0]["otp"])
            self.assertEqual(challenge.attempt_count, 0)
            self.assertIsNone(challenge.consumed_at)

    def test_password_reset_changes_password_consumes_code_and_revokes_all_sessions(self):
        old_token = self.setup_owner()
        request_endpoint = endpoint(self.app, "/api/admin/auth/password-reset/request")
        request_endpoint(
            AdminPasswordResetRequest(email="owner@example.invalid"),
            request_for(self.app, "/api/admin/auth/password-reset/request", "POST", csrf=True, origin=ADMIN_ORIGIN),
        )
        otp = self.sent_admin_reset_emails[-1]["otp"]
        old_password_hash = None
        with self.factory() as session:
            user = session.query(AdminUser).filter_by(email="owner@example.invalid").one()
            old_password_hash = user.password_hash
            session.add(AdminSession(
                admin_user_id=user.id,
                token_digest="f" * 64,
                expires_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc) + __import__("datetime").timedelta(hours=1),
            ))
            session.commit()

        confirm_endpoint = endpoint(self.app, "/api/admin/auth/password-reset/confirm")
        response = confirm_endpoint(
            AdminPasswordResetConfirm(
                email="owner@example.invalid", otp=otp,
                new_password="a-new-strong-test-password-phrase",
            ),
            request_for(self.app, "/api/admin/auth/password-reset/confirm", "POST", csrf=True, origin=ADMIN_ORIGIN),
        )
        self.assertEqual(response["status"], "password_reset")
        with self.factory() as session:
            user = session.query(AdminUser).filter_by(email="owner@example.invalid").one()
            self.assertNotEqual(user.password_hash, old_password_hash)
            challenges = session.query(AdminPasswordReset).all()
            self.assertEqual(sum(row.consumed_at is not None for row in challenges), 1)
            sessions = session.query(AdminSession).all()
            self.assertTrue(all(row.revoked_at is not None for row in sessions))
            self.assertTrue(session.query(AuditEvent).filter_by(action="admin_password_reset_completed").one())

        me = endpoint(self.app, "/api/admin/auth/me")
        with self.assertRaises(HTTPException) as old_session_rejected:
            me(request_for(self.app, "/api/admin/auth/me", token=old_token))
        self.assertEqual(old_session_rejected.exception.status_code, 401)

        login = endpoint(self.app, "/api/admin/auth/login")
        with self.assertRaises(HTTPException):
            login(
                AdminCredentials(email="owner@example.invalid", password="a-long-test-only-password-phrase"),
                request_for(self.app, "/api/admin/auth/login", "POST", csrf=True, origin=ADMIN_ORIGIN),
            )
        signed_in = login(
            AdminCredentials(email="owner@example.invalid", password="a-new-strong-test-password-phrase"),
            request_for(self.app, "/api/admin/auth/login", "POST", csrf=True, origin=ADMIN_ORIGIN),
        )
        self.assertTrue(signed_in["access_token"])

    def test_password_reset_rejects_incorrect_code_and_enforces_attempt_limit(self):
        self.setup_owner()
        endpoint(self.app, "/api/admin/auth/password-reset/request")(
            AdminPasswordResetRequest(email="owner@example.invalid"),
            request_for(self.app, "/api/admin/auth/password-reset/request", "POST", csrf=True, origin=ADMIN_ORIGIN),
        )
        confirm = endpoint(self.app, "/api/admin/auth/password-reset/confirm")
        for attempt in range(5):
            with self.assertRaises(HTTPException) as rejected:
                confirm(
                    AdminPasswordResetConfirm(
                        email="owner@example.invalid", otp="000000",
                        new_password="a-new-strong-test-password-phrase",
                    ),
                    request_for(self.app, "/api/admin/auth/password-reset/confirm", "POST", csrf=True, origin=ADMIN_ORIGIN),
                )
            self.assertEqual(rejected.exception.status_code, 400)
        with self.factory() as session:
            challenge = session.query(AdminPasswordReset).one()
            self.assertEqual(challenge.attempt_count, 5)
            self.assertIsNotNone(challenge.invalidated_at)
        self.assertEqual(len(self.sent_admin_reset_emails), 1)


    def test_database_overview_lists_all_tables_and_restricts_authentication_stores(self):
        token = self.setup_owner()
        overview = endpoint(self.app, "/api/admin/database/overview")(
            request_for(self.app, "/api/admin/database/overview", token=token)
        )
        names = {row["name"] for row in overview["tables"]}
        self.assertTrue({"candidates", "registrations", "exam_slots", "admin_users", "admin_sessions"}.issubset(names))
        restricted = endpoint(self.app, "/api/admin/database/tables/{table_name}")(
            "admin_sessions",
            request_for(self.app, "/api/admin/database/tables/admin_sessions", token=token),
        )
        self.assertTrue(restricted["restricted"])
        self.assertEqual(restricted["records"], [])
        self.assertEqual(restricted["columns"], [])

    def test_permitted_record_changes_require_csrf_and_are_audited(self):
        token = self.setup_owner()
        with self.factory() as session:
            candidate = Candidate(full_name="Before Edit", email="person@example.invalid", phone="9876543210")
            session.add(candidate)
            session.commit()
            candidate_id = candidate.id
        endpoint_patch = endpoint(self.app, "/api/admin/database/tables/{table_name}/{record_id}")
        payload = RecordPatch(changes={"full_name": "After Edit"})
        with self.assertRaises(HTTPException) as missing_csrf:
            endpoint_patch(
                "candidates", str(candidate_id), payload,
                request_for(self.app, "/api/admin/database/tables/candidates", "PATCH", token),
            )
        self.assertEqual(missing_csrf.exception.status_code, 403)
        result = endpoint_patch(
            "candidates", str(candidate_id), payload,
            request_for(self.app, "/api/admin/database/tables/candidates", "PATCH", token, csrf=True, origin=ADMIN_ORIGIN),
        )
        self.assertEqual(result["status"], "updated")
        with self.factory() as session:
            self.assertEqual(session.get(Candidate, UUID(str(candidate_id))).full_name, "After Edit")
            self.assertTrue(session.query(AuditEvent).filter_by(action="admin_record_updated").one())

    def test_password_hash_and_answer_key_flags_are_never_exposed(self):
        token = self.setup_owner()
        browse = endpoint(self.app, "/api/admin/database/tables/{table_name}")
        users = browse("admin_users", request_for(self.app, "/api/admin/database/tables/admin_users", token=token), search="", limit=25, offset=0)
        self.assertNotIn("password_hash", [column["name"] for column in users["columns"]])
        options = browse("answer_options", request_for(self.app, "/api/admin/database/tables/answer_options", token=token), search="", limit=25, offset=0)
        self.assertNotIn("is_correct", [column["name"] for column in options["columns"]])

    def test_foreign_origin_is_rejected_for_mutations(self):
        token = self.setup_owner()
        with self.assertRaises(HTTPException) as rejected:
            endpoint(self.app, "/api/admin/auth/logout")(
                request_for(self.app, "/api/admin/auth/logout", "POST", token, csrf=True, origin="https://evil.example.invalid")
            )
        self.assertEqual(rejected.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()

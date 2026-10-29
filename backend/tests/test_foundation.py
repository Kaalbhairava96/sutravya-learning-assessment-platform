from __future__ import annotations

import os
import json
import logging
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import ConfigurationError, Settings
from app.database import create_database_engine
from app.logging_config import SafeJsonFormatter

# Scope import-time configuration even when the optional TestClient dependency
# is missing: failed imports must not leak a dummy DATABASE_URL to other tests.
with patch.dict(
    os.environ,
    {
        "APP_ENV": "test",
        "LOG_LEVEL": "CRITICAL",
        "DATABASE_URL": "postgresql+psycopg://user:pass@127.0.0.1:55432/sutravya_m3_test",
    },
), patch("app.config._read_dotenv", return_value={}):
    from fastapi.testclient import TestClient
    from app.main import create_app


class BackendFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            app_env="test",
            log_level="CRITICAL",
            database_url="postgresql+psycopg://user:pass@127.0.0.1:55432/sutravya_m3_test",
        )
        self.client = TestClient(create_app(self.settings))

    def test_health_is_safe_and_does_not_require_a_live_database(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_missing_database_url_fails_configuration_validation(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "DATABASE_URL is required"):
            Settings.from_env(environ={"APP_ENV": "test"}, dotenv_path=Path("missing-test.env"))

    def test_otp_configuration_defaults_and_pepper_is_optional_at_startup(self) -> None:
        settings = Settings.from_env(
            environ={
                "APP_ENV": "test",
                "DATABASE_URL": "postgresql+psycopg://user:pass@127.0.0.1:55432/sutravya_m3_test",
            },
            dotenv_path=Path("missing-test.env"),
        )
        self.assertEqual(settings.otp_expiry_seconds, 300)
        self.assertEqual(settings.otp_max_attempts, 5)
        self.assertEqual(settings.otp_resend_cooldown_seconds, 60)
        self.assertIsNone(settings.otp_hmac_pepper)
        with self.assertRaisesRegex(ConfigurationError, "required for OTP digest operations"):
            settings.require_otp_hmac_pepper()

    def test_otp_configuration_accepts_valid_overrides_and_hides_pepper(self) -> None:
        pepper = "test-only-pepper-value-with-at-least-32-bytes"
        settings = Settings.from_env(
            environ={
                "APP_ENV": "test",
                "DATABASE_URL": "postgresql+psycopg://user:pass@127.0.0.1:55432/sutravya_m3_test",
                "OTP_EXPIRY_SECONDS": "180",
                "OTP_MAX_ATTEMPTS": "4",
                "OTP_RESEND_COOLDOWN_SECONDS": "90",
                "OTP_HMAC_PEPPER": pepper,
            },
            dotenv_path=Path("missing-test.env"),
        )
        self.assertEqual(settings.otp_expiry_seconds, 180)
        self.assertEqual(settings.otp_max_attempts, 4)
        self.assertEqual(settings.otp_resend_cooldown_seconds, 90)
        self.assertEqual(settings.require_otp_hmac_pepper(), pepper)
        self.assertNotIn(pepper, repr(settings))

    def test_invalid_otp_policy_values_are_rejected(self) -> None:
        for key in ("OTP_EXPIRY_SECONDS", "OTP_MAX_ATTEMPTS", "OTP_RESEND_COOLDOWN_SECONDS"):
            for value in ("0", "-1", "not-an-integer"):
                with self.subTest(key=key, value=value):
                    with self.assertRaisesRegex(ConfigurationError, f"{key} must be a positive integer"):
                        Settings.from_env(
                            environ={
                                "APP_ENV": "test",
                                "DATABASE_URL": "postgresql+psycopg://user:pass@127.0.0.1:55432/sutravya_m3_test",
                                key: value,
                            },
                            dotenv_path=Path("missing-test.env"),
                        )

    def test_short_otp_pepper_is_rejected_without_disclosing_value(self) -> None:
        pepper = "too-short"
        with self.assertRaisesRegex(ConfigurationError, "at least 32 UTF-8 bytes") as caught:
            Settings.from_env(
                environ={
                    "APP_ENV": "test",
                    "DATABASE_URL": "postgresql+psycopg://user:pass@127.0.0.1:55432/sutravya_m3_test",
                    "OTP_HMAC_PEPPER": pepper,
                },
                dotenv_path=Path("missing-test.env"),
            )
        self.assertNotIn(pepper, str(caught.exception))

    def test_non_postgresql_url_fails_configuration_validation(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, r"DATABASE_URL must use postgresql\+psycopg"):
            Settings.from_env(
                environ={"APP_ENV": "test", "DATABASE_URL": "sqlite:///local.db"},
                dotenv_path=Path("missing-test.env"),
            )

    def test_approved_local_disposable_test_database_is_accepted(self) -> None:
        url = "postgresql+psycopg://user:pass@127.0.0.1:55432/sutravya_m3_test"
        settings = Settings.from_env(
            environ={"APP_ENV": "test", "DATABASE_URL": url},
            dotenv_path=Path("missing-test.env"),
        )
        self.assertEqual(settings.database_url, url)
        self.assertNotIn("pass", repr(settings))

    def test_test_mode_rejects_production_or_unapproved_database_names(self) -> None:
        for database_name in ("sutravya_assessment", "sutravya_assessment_prod", "other_test"):
            with self.subTest(database_name=database_name):
                with self.assertRaisesRegex(ConfigurationError, "approved local disposable database"):
                    Settings.from_env(
                        environ={
                            "APP_ENV": "test",
                            "DATABASE_URL": f"postgresql+psycopg://user:pass@127.0.0.1:55432/{database_name}",
                        },
                        dotenv_path=Path("missing-test.env"),
                    )

    def test_test_mode_rejects_remote_or_unapproved_loopback_hosts(self) -> None:
        for authority in ("db.example.invalid:55432", "localhost:55432", "[::1]:55432"):
            host = authority
            with self.subTest(host=host):
                with self.assertRaisesRegex(ConfigurationError, "approved local disposable database"):
                    Settings.from_env(
                        environ={
                            "APP_ENV": "test",
                            "DATABASE_URL": f"postgresql+psycopg://user:pass@{authority}/sutravya_m3_test",
                        },
                        dotenv_path=Path("missing-test.env"),
                    )

    def test_test_mode_requires_the_rehearsal_port_and_rejects_url_options(self) -> None:
        for url in (
            "postgresql+psycopg://user:pass@127.0.0.1:5432/sutravya_m3_test",
            "postgresql+psycopg://user:pass@127.0.0.1:55432/sutravya_m3_test?host=remote.invalid",
        ):
            with self.subTest(url_without_credentials=url.split("@")[-1]):
                with self.assertRaises(ConfigurationError):
                    Settings.from_env(
                        environ={"APP_ENV": "test", "DATABASE_URL": url},
                        dotenv_path=Path("missing-test.env"),
                    )

    def test_invalid_url_fails_configuration_validation(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "valid PostgreSQL connection URL"):
            Settings.from_env(
                environ={
                    "APP_ENV": "test",
                    "DATABASE_URL": "postgresql+psycopg://user:pass@127.0.0.1:not-a-port/sutravya_m3_test",
                },
                dotenv_path=Path("missing-test.env"),
            )

    def test_rejected_test_configuration_fails_before_engine_creation(self) -> None:
        unsafe_environment = {
            "APP_ENV": "test",
            "DATABASE_URL": "postgresql+psycopg://user:pass@db.example.invalid:55432/sutravya_m3_test",
        }
        with patch.dict(os.environ, unsafe_environment), patch("app.database.create_engine") as engine_factory:
            with self.assertRaises(ConfigurationError):
                create_database_engine()
        engine_factory.assert_not_called()

    def test_non_test_modes_keep_documented_postgresql_url_policy(self) -> None:
        production_url = "postgresql+psycopg://user:pass@db.example.invalid:5432/sutravya_assessment"
        settings = Settings.from_env(
            environ={"APP_ENV": "production", "DATABASE_URL": production_url},
            dotenv_path=Path("missing-test.env"),
        )
        self.assertEqual(settings.database_url, production_url)

    def test_production_disables_interactive_api_docs(self) -> None:
        production_settings = Settings(
            app_env="production",
            log_level="CRITICAL",
            database_url="postgresql+psycopg://user:pass@localhost/test_db",
        )
        client = TestClient(create_app(production_settings))
        self.assertEqual(client.get("/docs").status_code, 404)
        self.assertEqual(client.get("/openapi.json").status_code, 404)

    def test_structured_logs_drop_arbitrary_messages_and_sensitive_fields(self) -> None:
        record = logging.LogRecord("sutravya.api", logging.INFO, "test", 1, "personal data", (), None)
        record.candidate_email = "candidate@example.invalid"
        record.access_token = "test-token"
        record.database_url = "postgresql+psycopg://user:password@localhost/private"
        output = SafeJsonFormatter().format(record)
        payload = json.loads(output)
        self.assertEqual(payload["event"], "application_event")
        self.assertNotIn("candidate@example.invalid", output)
        self.assertNotIn("test-token", output)
        self.assertNotIn("password", output)


if __name__ == "__main__":
    unittest.main()

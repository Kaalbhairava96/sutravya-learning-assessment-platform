"""Offline registration and passwordless-session tests using synthetic data."""

from __future__ import annotations

import unittest
from io import BytesIO
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, event, select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.email_provider import EmailDeliveryError, EmailProviderConfigurationError, send_otp_email
from app.models import Base, Candidate, CandidateSession, RateLimitBucket, Registration, VerificationChallenge
from app.registration import (
    LOGIN_OTP_PURPOSE,
    REGISTRATION_OTP_PURPOSE,
    RegistrationError,
    create_login_challenge,
    create_registration_challenge,
    enforce_rate_limit,
    get_candidate_session,
    invalidate_challenge,
    normalize_email,
    normalize_mobile,
    resend_email_challenge,
    revoke_candidate_session,
    validate_registration,
    verify_login_email,
    verify_registration_email,
)
from app.verification import ChallengeVerification, verify_and_consume_challenge


TEST_DATABASE_URL = "postgresql+psycopg://synthetic:synthetic@127.0.0.1:55432/sutravya_m3_test"
PEPPER = "offline-registration-tests-only-pepper-at-least-32-bytes"


def settings() -> Settings:
    return Settings(app_env="test", log_level="CRITICAL", database_url=TEST_DATABASE_URL, otp_hmac_pepper=PEPPER)


class RegistrationAccountTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def enable_sqlite_foreign_keys(connection, _record) -> None:
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.now = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.engine.dispose()

    def register_candidate(self, email: str = "candidate@example.invalid", *, stream: str = "nursing"):
        with self.factory() as session:
            pending = create_registration_challenge(
                session, settings=settings(), name="Synthetic Candidate", email=email,
                mobile="9876543210", stream=stream, now=self.now,
            )
            challenge = session.get(VerificationChallenge, pending.challenge_id)
            self.assertIsNotNone(challenge)
            self.assertNotEqual(challenge.otp_digest, pending.otp)
            self.assertEqual(challenge.purpose, REGISTRATION_OTP_PURPOSE)
            candidate = session.get(Candidate, pending.candidate_id)
            self.assertIsNone(candidate.email_verified_at)
            self.assertIsNone(candidate.phone_verified_at)
            session.rollback()
            outcome, summary = verify_registration_email(
                session, settings=settings(), challenge_id=pending.challenge_id,
                otp=pending.otp, now=self.now + timedelta(seconds=1),
            )
            self.assertEqual(outcome, ChallengeVerification.VERIFIED)
            self.assertIsNotNone(summary)
            return pending.candidate_id, summary

    def test_normalization_and_invalid_registration_inputs(self) -> None:
        self.assertEqual(normalize_email("  Person@Example.com "), "person@example.com")
        self.assertEqual(normalize_mobile("+91 98765-43210"), "+919876543210")
        self.assertEqual(
            validate_registration("  A   Candidate ", "Person@Example.com", "+91 98765-43210", "NURSING"),
            ("A Candidate", "person@example.com", "+919876543210", "nursing"),
        )
        for values in (
            ("Candidate", "invalid", "9876543210", "nursing"),
            ("Candidate", "candidate@example.invalid", "12345", "nursing"),
            ("Candidate", "candidate@example.invalid", "9876543210", "unapproved"),
        ):
            with self.assertRaises(RegistrationError):
                validate_registration(*values)

    def test_registration_is_created_only_after_email_verification(self) -> None:
        with self.factory() as session:
            pending = create_registration_challenge(
                session, settings=settings(), name="Synthetic Nurse", email="nurse@example.invalid",
                mobile="9876543210", stream="paramedical", now=self.now,
            )
            self.assertEqual(session.scalar(select(func.count(Registration.id))), 0)
            session.rollback()
            outcome, result = verify_registration_email(
                session, settings=settings(), challenge_id=pending.challenge_id,
                otp=pending.otp, now=self.now + timedelta(seconds=1),
            )
            self.assertEqual(outcome, ChallengeVerification.VERIFIED)
            self.assertRegex(result.registration_id, r"^SUT26-[A-F0-9]{16}$")
            saved = session.scalar(select(Registration))
            self.assertEqual(saved.registration_id, result.registration_id)
            self.assertEqual(saved.stream, "paramedical")
            self.assertEqual(saved.status, "active")
            candidate = session.get(Candidate, pending.candidate_id)
            self.assertIsNotNone(candidate.email_verified_at)
            self.assertIsNone(candidate.phone_verified_at)
            self.assertIsNone(candidate.pending_stream)
            session.rollback()

    def test_verified_email_is_database_unique_but_unverified_email_is_not(self) -> None:
        self.register_candidate("unique@example.invalid")
        with self.factory() as session, session.begin():
            session.add(Candidate(email="UNIQUE@example.invalid"))
        # The database partial index applies only after email verification.
        with self.factory() as session, session.begin():
            session.add(Candidate(email="unique@example.invalid"))
            session.flush()
            session.scalar(select(Candidate).where(Candidate.email_verified_at.is_not(None)))
            second = Candidate(email="unique@example.invalid", email_verified_at=self.now)
            session.add(second)
            with self.assertRaises(IntegrityError):
                session.flush()

    def test_expired_incorrect_attempt_limit_replay_and_wrong_purpose(self) -> None:
        with self.factory() as session:
            pending = create_registration_challenge(
                session, settings=settings(), name="Synthetic", email="otp@example.invalid",
                mobile="9876543210", stream="nursing", now=self.now,
            )
            for expected in (ChallengeVerification.INVALID_CODE,) * 4 + (ChallengeVerification.ATTEMPTS_EXHAUSTED,):
                outcome, _ = verify_registration_email(
                    session, settings=settings(), challenge_id=pending.challenge_id, otp="000000",
                    now=self.now + timedelta(seconds=1),
                )
                self.assertEqual(outcome, expected)
            challenge = session.get(VerificationChallenge, pending.challenge_id)
            self.assertEqual(challenge.attempt_count, 5)
            session.rollback()
            with session.begin():
                wrong_purpose = verify_and_consume_challenge(
                    session, settings=settings(), candidate_id=pending.candidate_id,
                    challenge_id=pending.challenge_id, channel="email", otp=pending.otp,
                    purpose=LOGIN_OTP_PURPOSE, now=self.now + timedelta(seconds=2),
                )
            self.assertEqual(wrong_purpose, ChallengeVerification.NOT_FOUND)

            expired = create_registration_challenge(
                session, settings=settings(), name="Other Synthetic", email="expired@example.invalid",
                mobile="9876543211", stream="nursing", now=self.now + timedelta(seconds=61),
            )
            outcome, _ = verify_registration_email(
                session, settings=settings(), challenge_id=expired.challenge_id, otp=expired.otp,
                now=self.now + timedelta(seconds=361),
            )
            self.assertEqual(outcome, ChallengeVerification.EXPIRED)

    def test_resend_cooldown_then_single_use(self) -> None:
        with self.factory() as session:
            first = create_registration_challenge(
                session, settings=settings(), name="Synthetic", email="resend@example.invalid",
                mobile="9876543210", stream="nursing", now=self.now,
            )
            with self.assertRaises(RegistrationError):
                resend_email_challenge(
                    session, settings=settings(), challenge_id=first.challenge_id,
                    expected_purpose=REGISTRATION_OTP_PURPOSE, now=self.now + timedelta(seconds=59),
                )
            second = resend_email_challenge(
                session, settings=settings(), challenge_id=first.challenge_id,
                expected_purpose=REGISTRATION_OTP_PURPOSE, now=self.now + timedelta(seconds=60),
            )
            outcome, summary = verify_registration_email(
                session, settings=settings(), challenge_id=second.challenge_id,
                otp=second.otp, now=self.now + timedelta(seconds=61),
            )
            self.assertEqual(outcome, ChallengeVerification.VERIFIED)
            replay, _ = verify_registration_email(
                session, settings=settings(), challenge_id=second.challenge_id,
                otp=second.otp, now=self.now + timedelta(seconds=62),
            )
            self.assertEqual(replay, ChallengeVerification.CONSUMED)
            self.assertIsNotNone(summary)

    def test_stale_candidate_email_is_refreshed_before_challenge_comparison(self) -> None:
        with self.factory() as create_session:
            pending = create_registration_challenge(
                create_session, settings=settings(), name="Synthetic", email="old@example.invalid",
                mobile="9876543210", stream="nursing", now=self.now,
            )
        stale_session = self.factory()
        try:
            stale_candidate = stale_session.get(Candidate, pending.candidate_id)
            self.assertEqual(stale_candidate.email, "old@example.invalid")
            stale_session.commit()
            with self.factory.begin() as change_session:
                changed = change_session.get(Candidate, pending.candidate_id)
                changed.email = "new@example.invalid"
            with stale_session.begin():
                outcome = verify_and_consume_challenge(
                    stale_session, settings=settings(), candidate_id=pending.candidate_id,
                    challenge_id=pending.challenge_id, channel="email", otp=pending.otp,
                    purpose=REGISTRATION_OTP_PURPOSE, now=self.now + timedelta(seconds=1),
                )
            self.assertEqual(outcome, ChallengeVerification.INVALIDATED)
        finally:
            stale_session.close()

    def test_failed_email_submission_can_retry_without_duplicate_candidate(self) -> None:
        with self.factory() as session:
            first = create_registration_challenge(
                session, settings=settings(), name="Synthetic", email="retry@example.invalid",
                mobile="9876543210", stream="nursing", now=self.now,
            )
            # The API invalidates a challenge when mocked provider submission fails.
            invalidate_challenge(session, first.challenge_id, now=self.now + timedelta(seconds=1))
            retry = create_registration_challenge(
                session, settings=settings(), name="Synthetic", email="retry@example.invalid",
                mobile="9876543210", stream="nursing", now=self.now + timedelta(seconds=61),
            )
            self.assertEqual(first.candidate_id, retry.candidate_id)
            self.assertEqual(session.scalar(select(func.count(Candidate.id))), 1)
            self.assertEqual(session.scalar(select(func.count(Registration.id))), 0)

    def test_login_requires_registered_verified_email_and_persists_opaque_session(self) -> None:
        candidate_id, summary = self.register_candidate("login@example.invalid")
        with self.factory() as session:
            self.assertIsNone(create_login_challenge(session, settings=settings(), email="unknown@example.invalid", now=self.now))
            login_challenge = create_login_challenge(
                session, settings=settings(), email="LOGIN@example.invalid", now=self.now + timedelta(seconds=61),
            )
            self.assertIsNotNone(login_challenge)
            self.assertEqual(login_challenge.purpose, LOGIN_OTP_PURPOSE)
            outcome, login = verify_login_email(
                session, settings=settings(), email="login@example.invalid", otp=login_challenge.otp,
                now=self.now + timedelta(seconds=62),
            )
            self.assertEqual(outcome, ChallengeVerification.VERIFIED)
            self.assertEqual(login.registration_id, summary.registration_id)
            saved_session = session.scalar(select(CandidateSession))
            self.assertNotEqual(saved_session.token_digest, login.raw_session_token)
            self.assertEqual(
                get_candidate_session(session, login.raw_session_token, now=self.now + timedelta(seconds=63)).registration_id,
                summary.registration_id,
            )
            session.rollback()
            revoke_candidate_session(session, login.raw_session_token, now=self.now + timedelta(seconds=64))
            self.assertIsNone(get_candidate_session(session, login.raw_session_token, now=self.now + timedelta(seconds=65)))

    def test_legacy_test_only_candidate_cannot_login_but_can_complete_one_real_registration(self) -> None:
        with self.factory() as session:
            candidate = Candidate(
                full_name="Legacy Synthetic Candidate", email="legacy-candidate@example.invalid",
                phone="+919876543210", email_verified_at=self.now,
            )
            session.add(candidate)
            session.flush()
            legacy = Registration(
                candidate_id=candidate.id, event_key="BHC-2026", registration_id="SUT26-LEGACY001",
                stream="nursing", status="active", is_internal_test=True,
                registration_source="legacy_internal_test",
            )
            session.add(legacy)
            session.commit()
            candidate_id, legacy_id = candidate.id, legacy.id

            self.assertIsNone(create_login_challenge(
                session, settings=settings(), email="legacy-candidate@example.invalid", now=self.now,
            ))

            pending = create_registration_challenge(
                session, settings=settings(), name="Legacy Synthetic Candidate",
                email="legacy-candidate@example.invalid", mobile="9876543210", stream="paramedical",
                now=self.now + timedelta(seconds=61),
            )
            outcome, summary = verify_registration_email(
                session, settings=settings(), challenge_id=pending.challenge_id,
                otp=pending.otp, now=self.now + timedelta(seconds=62),
            )
            self.assertEqual(outcome, ChallengeVerification.VERIFIED)
            self.assertEqual(summary.registration_source, "public_registration")
            session.expire_all()
            saved_legacy = session.get(Registration, legacy_id)
            self.assertEqual(saved_legacy.registration_id, "SUT26-LEGACY001")
            self.assertTrue(saved_legacy.is_internal_test)
            self.assertEqual(saved_legacy.registration_source, "legacy_internal_test")
            registrations = session.scalars(
                select(Registration).where(Registration.candidate_id == candidate_id)
            ).all()
            self.assertEqual(len(registrations), 2)
            official = next(row for row in registrations if not row.is_internal_test)
            self.assertEqual(official.registration_source, "public_registration")
            self.assertEqual(official.status, "active")
            session.rollback()

            login_challenge = create_login_challenge(
                session, settings=settings(), email="legacy-candidate@example.invalid",
                now=self.now + timedelta(seconds=123),
            )
            self.assertIsNotNone(login_challenge)
            outcome, login = verify_login_email(
                session, settings=settings(), email="legacy-candidate@example.invalid",
                otp=login_challenge.otp, now=self.now + timedelta(seconds=124),
            )
            self.assertEqual(outcome, ChallengeVerification.VERIFIED)
            self.assertIsNotNone(get_candidate_session(
                session, login.raw_session_token, now=self.now + timedelta(seconds=125),
            ))

    def test_legacy_internal_challenge_cannot_verify_or_be_resent(self) -> None:
        with self.factory() as session:
            candidate = Candidate(
                full_name="Legacy Challenge Candidate", email="legacy-challenge@example.invalid",
                phone="+919876543210",
            )
            session.add(candidate)
            session.flush()
            challenge = VerificationChallenge(
                candidate_id=candidate.id, channel="email", purpose=REGISTRATION_OTP_PURPOSE,
                destination_digest="d" * 64, otp_digest="e" * 64,
                created_at=self.now, expires_at=self.now + timedelta(minutes=5),
                is_internal_test=True, registration_source="legacy_internal_test",
            )
            session.add(challenge)
            session.commit()
            challenge_id = challenge.id

            outcome, summary = verify_registration_email(
                session, settings=settings(), challenge_id=challenge_id, otp="123456",
                now=self.now + timedelta(seconds=1),
            )
            self.assertEqual(outcome, ChallengeVerification.NOT_FOUND)
            self.assertIsNone(summary)
            with self.assertRaises(RegistrationError):
                resend_email_challenge(
                    session, settings=settings(), challenge_id=challenge_id,
                    expected_purpose=REGISTRATION_OTP_PURPOSE, now=self.now + timedelta(seconds=61),
                )

    def test_public_candidate_login_eligibility(self) -> None:
        candidate_id, summary = self.register_candidate("public-login@example.invalid")
        self.assertEqual(summary.registration_source, "public_registration")
        with self.factory() as session:
            challenge = create_login_challenge(
                session, settings=settings(), email="public-login@example.invalid",
                now=self.now + timedelta(seconds=61),
            )
            self.assertIsNotNone(challenge)
            outcome, login = verify_login_email(
                session, settings=settings(), email="public-login@example.invalid", otp=challenge.otp,
                now=self.now + timedelta(seconds=62),
            )
            self.assertEqual(outcome, ChallengeVerification.VERIFIED)
            self.assertEqual(login.registration_id, summary.registration_id)
            self.assertEqual(session.get(Candidate, candidate_id).email, "public-login@example.invalid")

    def test_session_expiry_and_rate_limit_persistence(self) -> None:
        _, summary = self.register_candidate("expiry@example.invalid")
        with self.factory() as session:
            challenge = create_login_challenge(
                session, settings=settings(), email=summary.email, now=self.now + timedelta(seconds=61),
            )
            _, login = verify_login_email(
                session, settings=settings(), email=summary.email, otp=challenge.otp,
                now=self.now + timedelta(seconds=62),
            )
            self.assertIsNone(get_candidate_session(session, login.raw_session_token, now=login.expires_at + timedelta(seconds=1)))
            session.rollback()
            for _ in range(2):
                enforce_rate_limit(
                    session, scope="synthetic-test", subject="203.0.113.10", limit=2,
                    window_seconds=60, settings=settings(), now=self.now,
                )
            with self.assertRaises(RegistrationError):
                enforce_rate_limit(
                    session, scope="synthetic-test", subject="203.0.113.10", limit=2,
                    window_seconds=60, settings=settings(), now=self.now,
                )
            self.assertNotEqual(session.scalar(select(RateLimitBucket.subject_digest)), "203.0.113.10")

    def test_registration_transaction_rolls_back_on_unique_id_conflict(self) -> None:
        with self.factory() as session:
            existing = Candidate(email="existing@example.invalid", email_verified_at=self.now)
            session.add(existing)
            session.flush()
            session.add(Registration(
                candidate_id=existing.id, event_key="BHC-2026", registration_id="SUT26-DUPLICATE",
                stream="nursing", status="active",
            ))
            session.commit()
            pending = create_registration_challenge(
                session, settings=settings(), name="Synthetic", email="rollback@example.invalid",
                mobile="9876543210", stream="nursing", now=self.now,
            )
            with patch("app.registration._new_registration_id", return_value="SUT26-DUPLICATE"):
                with self.assertRaises(IntegrityError):
                    verify_registration_email(
                        session, settings=settings(), challenge_id=pending.challenge_id,
                        otp=pending.otp, now=self.now + timedelta(seconds=1),
                    )
            challenge = session.get(VerificationChallenge, pending.challenge_id)
            candidate = session.get(Candidate, pending.candidate_id)
            self.assertIsNone(challenge.consumed_at)
            self.assertIsNone(candidate.email_verified_at)
            self.assertEqual(session.scalar(select(func.count(Registration.id))), 1)

    def test_mocked_resend_delivery_contract_and_safe_provider_failure(self) -> None:
        configuration = settings()
        configuration = Settings(
            app_env="test", log_level="CRITICAL", database_url=TEST_DATABASE_URL,
            otp_hmac_pepper=PEPPER, resend_api_key="synthetic-key-not-a-secret",
            resend_from_email="SUTRAVYA <test@example.invalid>",
        )
        with patch("app.email_provider.urlopen") as urlopen:
            response = Mock(status=200)
            urlopen.return_value.__enter__.return_value = response
            send_otp_email(
                recipient_email="candidate@example.invalid", recipient_name="Synthetic Candidate",
                otp="123456", purpose=REGISTRATION_OTP_PURPOSE, settings=configuration,
            )
            request = urlopen.call_args.args[0]
            self.assertIn("Bearer synthetic-key-not-a-secret", request.get_header("Authorization"))
            self.assertEqual(request.get_header("User-agent"), "SUTRAVYA-Assessment-API/1.0")
            self.assertIn(b"123456", request.data)
        with patch("app.email_provider.urlopen", side_effect=OSError("provider internal details")):
            with self.assertRaises(EmailDeliveryError) as raised:
                send_otp_email(
                    recipient_email="candidate@example.invalid", recipient_name="Candidate",
                    otp="123456", purpose=REGISTRATION_OTP_PURPOSE, settings=configuration,
                )
            self.assertNotIn("provider internal details", str(raised.exception))

    def test_email_provider_failures_have_safe_diagnostic_categories(self) -> None:
        configuration = Settings(
            app_env="test", log_level="CRITICAL", database_url=TEST_DATABASE_URL,
            otp_hmac_pepper=PEPPER,
        )
        with patch("app.email_provider.urlopen") as urlopen:
            with self.assertRaises(EmailProviderConfigurationError) as raised:
                send_otp_email(
                    recipient_email="candidate@example.invalid", recipient_name="Candidate",
                    otp="123456", purpose=REGISTRATION_OTP_PURPOSE, settings=configuration,
                )
            self.assertEqual(raised.exception.failure_kind, "configuration_missing")
            urlopen.assert_not_called()

        configured = Settings(
            app_env="test", log_level="CRITICAL", database_url=TEST_DATABASE_URL,
            otp_hmac_pepper=PEPPER, resend_api_key="synthetic-test-key",
            resend_from_email="SUTRAVYA <test@example.invalid>",
        )
        provider_errors = (
            (401, b'{"name":"unauthorized","message":"private API key detail"}', "unauthorized", "api_key_permission"),
            (403, b'{"name":"validation_error","message":"mail.sutravya.in domain is not verified"}', "validation_error", "domain_verification"),
            (403, b'{"name":"validation_error","message":"from address must be verified"}', "validation_error", "sender_address"),
            (403, b'{"name":"validation_error","message":"testing mode only permits verified recipients"}', "validation_error", "testing_recipient_restriction"),
            (403, b'{"name":"validation_error","message":"account is restricted from sending"}', "validation_error", "account_sending_restriction"),
            (403, b'{"name":"unexpected_provider_name","message":"private opaque rejection"}', "unknown", "unknown"),
            (403, b"not valid JSON with private response data", "unknown", "unknown"),
            (403, b"", "unknown", "unknown"),
            (422, b'{"name":"validation_error","message":"recipient format is invalid"}', "validation_error", "other_provider_rejection"),
            (429, b'{"name":"rate_limit_exceeded","message":"private throttle detail"}', "rate_limit_exceeded", "other_provider_rejection"),
        )
        for status_code, provider_body, expected_name, expected_kind in provider_errors:
            with self.subTest(status_code=status_code, expected_kind=expected_kind, body=bool(provider_body)):
                error = HTTPError(
                    "https://api.resend.com/emails", status_code, "private exception message", {}, BytesIO(provider_body)
                )
                with patch("app.email_provider.urlopen", side_effect=error):
                    with self.assertRaises(EmailDeliveryError) as raised:
                        send_otp_email(
                            recipient_email="candidate@example.invalid", recipient_name="Candidate",
                            otp="123456", purpose=REGISTRATION_OTP_PURPOSE, settings=configured,
                        )
                self.assertEqual(raised.exception.failure_kind, "provider_http_error")
                self.assertEqual(raised.exception.provider_status_code, status_code)
                self.assertEqual(raised.exception.provider_error_name, expected_name)
                self.assertEqual(raised.exception.provider_error_kind, expected_kind)
                self.assertNotIn("private", str(raised.exception))
                self.assertNotIn("private exception message", str(raised.exception))
                self.assertNotIn("private API key detail", str(raised.exception))

        with patch("app.email_provider.urlopen", side_effect=TimeoutError("private timeout details")):
            with self.assertRaises(EmailDeliveryError) as raised:
                send_otp_email(
                    recipient_email="candidate@example.invalid", recipient_name="Candidate",
                    otp="123456", purpose=REGISTRATION_OTP_PURPOSE, settings=configured,
                )
        self.assertEqual(raised.exception.failure_kind, "network_or_timeout")
        self.assertIsNone(raised.exception.provider_status_code)
        self.assertNotIn("private timeout details", str(raised.exception))


if __name__ == "__main__":
    unittest.main()

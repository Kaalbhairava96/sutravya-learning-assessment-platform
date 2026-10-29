from __future__ import annotations

import re
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.config import ConfigurationError, Settings
from app.models import VerificationChallenge
from app.verification import (
    ChallengeState,
    challenge_state,
    digest_destination,
    digest_otp,
    generate_otp,
    otp_matches,
)


TEST_DATABASE_URL = "postgresql+psycopg://user:pass@127.0.0.1:55432/sutravya_m3_test"
TEST_PEPPER = "unit-test-only-pepper-material-with-32-bytes-minimum"


class VerificationSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            app_env="test",
            log_level="CRITICAL",
            database_url=TEST_DATABASE_URL,
            otp_hmac_pepper=TEST_PEPPER,
        )
        self.candidate_id = uuid4()
        self.challenge_id = uuid4()

    def test_generator_returns_six_ascii_digits(self) -> None:
        for _ in range(100):
            self.assertRegex(generate_otp(), re.compile(r"^[0-9]{6}$"))

    def test_hmac_digest_is_challenge_bound_and_compared(self) -> None:
        otp = "004271"
        digest = digest_otp(
            otp,
            settings=self.settings,
            challenge_id=self.challenge_id,
            candidate_id=self.candidate_id,
            channel="mobile",
        )
        self.assertEqual(len(digest), 64)
        self.assertNotEqual(digest, otp)
        self.assertTrue(
            otp_matches(
                otp,
                digest,
                settings=self.settings,
                challenge_id=self.challenge_id,
                candidate_id=self.candidate_id,
                channel="mobile",
            )
        )
        self.assertFalse(
            otp_matches(
                otp,
                digest,
                settings=self.settings,
                challenge_id=uuid4(),
                candidate_id=self.candidate_id,
                channel="mobile",
            )
        )

    def test_destination_digest_is_keyed_and_email_case_insensitive(self) -> None:
        digest = digest_destination(
            "  Nurse@Example.invalid ",
            settings=self.settings,
            candidate_id=self.candidate_id,
            channel="email",
        )
        self.assertEqual(
            digest,
            digest_destination(
                "nurse@example.invalid",
                settings=self.settings,
                candidate_id=self.candidate_id,
                channel="email",
            ),
        )
        self.assertNotEqual(
            digest,
            digest_destination(
                "other@example.invalid",
                settings=self.settings,
                candidate_id=self.candidate_id,
                channel="email",
            ),
        )
        self.assertFalse(
            otp_matches(
                "not-a-code",
                digest,
                settings=self.settings,
                challenge_id=self.challenge_id,
                candidate_id=self.candidate_id,
                channel="mobile",
            )
        )

    def test_digest_operation_fails_closed_without_pepper(self) -> None:
        settings = Settings(
            app_env="test",
            log_level="CRITICAL",
            database_url=TEST_DATABASE_URL,
        )
        with self.assertRaisesRegex(ConfigurationError, "required for OTP digest operations"):
            digest_otp(
                "004271",
                settings=settings,
                challenge_id=self.challenge_id,
                candidate_id=self.candidate_id,
                channel="email",
            )

    def test_challenge_expiry_attempt_and_terminal_state_rules(self) -> None:
        now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
        base = {
            "id": self.challenge_id,
            "candidate_id": self.candidate_id,
            "channel": "mobile",
            "purpose": "contact_verification",
            "otp_digest": "a" * 64,
            "created_at": now - timedelta(minutes=1),
            "expires_at": now + timedelta(minutes=4),
        }
        challenge = VerificationChallenge(**base, attempt_count=0)
        self.assertEqual(challenge_state(challenge, now=now, max_attempts=5), ChallengeState.USABLE)
        self.assertEqual(
            challenge_state(challenge, now=challenge.expires_at, max_attempts=5),
            ChallengeState.EXPIRED,
        )
        challenge.attempt_count = 5
        self.assertEqual(
            challenge_state(challenge, now=now, max_attempts=5),
            ChallengeState.ATTEMPTS_EXHAUSTED,
        )
        challenge.consumed_at = now
        self.assertEqual(
            challenge_state(challenge, now=now, max_attempts=5),
            ChallengeState.CONSUMED,
        )
        challenge.consumed_at = None
        challenge.invalidated_at = now
        self.assertEqual(
            challenge_state(challenge, now=now, max_attempts=5),
            ChallengeState.INVALIDATED,
        )


if __name__ == "__main__":
    unittest.main()

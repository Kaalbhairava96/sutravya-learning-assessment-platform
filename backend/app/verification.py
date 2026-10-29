"""Small OTP security helpers; delivery, routes, and candidate sessions are deferred."""

from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
from re import fullmatch
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Candidate, VerificationChallenge


OTP_DIGITS = 6
OTP_PURPOSE = "contact_verification"


class ChallengeState(StrEnum):
    USABLE = "usable"
    CONSUMED = "consumed"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"
    ATTEMPTS_EXHAUSTED = "attempts_exhausted"


class ChallengeVerification(StrEnum):
    VERIFIED = "verified"
    INVALID_CODE = "invalid_code"
    NOT_FOUND = "not_found"
    CONSUMED = "consumed"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"
    ATTEMPTS_EXHAUSTED = "attempts_exhausted"


def generate_otp() -> str:
    """Generate a zero-padded six-digit code with a cryptographically secure RNG."""
    return f"{secrets.randbelow(10**OTP_DIGITS):0{OTP_DIGITS}d}"


def digest_otp(
    otp: str,
    *,
    settings: Settings,
    challenge_id: UUID,
    candidate_id: UUID,
    channel: str,
    purpose: str = OTP_PURPOSE,
) -> str:
    """Create a challenge-bound HMAC digest; never persist or log the supplied code."""
    if fullmatch(r"[0-9]{6}", otp) is None:
        raise ValueError("OTP must contain exactly six ASCII digits.")
    message = "\x1f".join(
        ("sutravya-otp-v1", str(challenge_id), str(candidate_id), channel, purpose, otp)
    ).encode("utf-8")
    key = settings.require_otp_hmac_pepper().encode("utf-8")
    return hmac.new(key, message, sha256).hexdigest()


def digest_destination(
    destination: str,
    *,
    settings: Settings,
    candidate_id: UUID,
    channel: str,
    purpose: str = OTP_PURPOSE,
) -> str:
    """Bind a challenge to its recipient without copying contact data into the row."""
    canonical = destination.strip().lower() if channel == "email" else destination.strip()
    message = "\x1f".join(
        ("sutravya-destination-v1", str(candidate_id), channel, purpose, canonical)
    ).encode("utf-8")
    key = settings.require_otp_hmac_pepper().encode("utf-8")
    return hmac.new(key, message, sha256).hexdigest()


def otp_matches(
    otp: str,
    stored_digest: str,
    *,
    settings: Settings,
    challenge_id: UUID,
    candidate_id: UUID,
    channel: str,
    purpose: str = OTP_PURPOSE,
) -> bool:
    """Compare digests in constant time. Malformed input is an ordinary mismatch."""
    if fullmatch(r"[0-9]{6}", otp) is None:
        return False
    expected = digest_otp(
        otp,
        settings=settings,
        challenge_id=challenge_id,
        candidate_id=candidate_id,
        channel=channel,
        purpose=purpose,
    )
    return hmac.compare_digest(expected, stored_digest)


def challenge_state(
    challenge: VerificationChallenge,
    *,
    now: datetime,
    max_attempts: int,
) -> ChallengeState:
    """Return the persisted challenge's usable/terminal state without changing it."""
    if now.tzinfo is None:
        raise ValueError("The current verification time must be timezone-aware.")
    # SQLite strips timezone metadata from DateTime(timezone=True) columns. All
    # challenge timestamps are written as UTC, so restore that meaning when an
    # offline SQLite test reads them back. PostgreSQL values remain aware.
    expiry = challenge.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if challenge.consumed_at is not None:
        return ChallengeState.CONSUMED
    if challenge.invalidated_at is not None:
        return ChallengeState.INVALIDATED
    if now.astimezone(timezone.utc) >= expiry.astimezone(timezone.utc):
        return ChallengeState.EXPIRED
    if challenge.attempt_count >= max_attempts:
        return ChallengeState.ATTEMPTS_EXHAUSTED
    return ChallengeState.USABLE


def verify_and_consume_challenge(
    session: Session,
    *,
    settings: Settings,
    candidate_id: UUID,
    challenge_id: UUID,
    channel: str,
    otp: str,
    purpose: str = OTP_PURPOSE,
    now: datetime | None = None,
) -> ChallengeVerification:
    """Verify and consume a challenge inside the caller's active transaction.

    The candidate row is locked first so future issuance/resend operations can use
    the same lock order. The challenge row is then locked and refreshed. PostgreSQL
    serializes competing consumers; after the first commits, later consumers see
    the consumed timestamp. The caller must commit normal rejection outcomes too,
    so incorrect-attempt increments persist.
    """
    if not session.in_transaction():
        raise RuntimeError("Challenge verification requires an active database transaction.")
    verification_time = now or datetime.now(timezone.utc)
    if verification_time.tzinfo is None:
        raise ValueError("Verification time must be timezone-aware.")

    candidate = session.scalar(
        select(Candidate)
        .where(Candidate.id == candidate_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if candidate is None:
        return ChallengeVerification.NOT_FOUND

    challenge = session.scalar(
        select(VerificationChallenge)
        .where(
            VerificationChallenge.id == challenge_id,
            VerificationChallenge.candidate_id == candidate_id,
            VerificationChallenge.channel == channel,
            VerificationChallenge.purpose == purpose,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if challenge is None:
        return ChallengeVerification.NOT_FOUND
    if channel == "mobile" and not candidate.phone:
        return ChallengeVerification.NOT_FOUND
    if channel == "email" and not candidate.email:
        return ChallengeVerification.NOT_FOUND

    state = challenge_state(challenge, now=verification_time, max_attempts=settings.otp_max_attempts)
    if state != ChallengeState.USABLE:
        return ChallengeVerification(state.value)

    destination = candidate.phone if channel == "mobile" else candidate.email
    expected_destination_digest = digest_destination(
        destination or "",
        settings=settings,
        candidate_id=candidate.id,
        channel=channel,
        purpose=challenge.purpose,
    )
    if not hmac.compare_digest(expected_destination_digest, challenge.destination_digest):
        challenge.invalidated_at = verification_time
        return ChallengeVerification.INVALIDATED

    if not otp_matches(
        otp,
        challenge.otp_digest,
        settings=settings,
        challenge_id=challenge.id,
        candidate_id=candidate.id,
        channel=challenge.channel,
        purpose=challenge.purpose,
    ):
        challenge.attempt_count += 1
        if challenge.attempt_count >= settings.otp_max_attempts:
            return ChallengeVerification.ATTEMPTS_EXHAUSTED
        return ChallengeVerification.INVALID_CODE

    challenge.consumed_at = verification_time
    if channel == "mobile":
        candidate.phone_verified_at = verification_time
    elif channel == "email":
        candidate.email_verified_at = verification_time
    else:
        return ChallengeVerification.NOT_FOUND
    return ChallengeVerification.VERIFIED

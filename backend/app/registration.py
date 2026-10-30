"""Email OTP registration and passwordless candidate sessions."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Candidate, CandidateSession, RateLimitBucket, Registration, VerificationChallenge
from app.verification import (
    ChallengeVerification,
    digest_destination,
    digest_otp,
    generate_otp,
    verify_and_consume_challenge,
)


EVENT_KEY = "BHC-2026"
REGISTRATION_OTP_PURPOSE = "registration_verification"
LOGIN_OTP_PURPOSE = "login"
ALLOWED_STREAMS = frozenset({"paramedical", "nursing", "mbbs_1st_year"})
SESSION_SECONDS = 24 * 60 * 60
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class RegistrationError(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class PendingEmailChallenge:
    challenge_id: UUID
    candidate_id: UUID
    email: str
    otp: str
    purpose: str


@dataclass(frozen=True)
class RegistrationSummary:
    registration_id: str
    email: str
    full_name: str
    stream: str
    is_internal_test: bool = False


@dataclass(frozen=True)
class CandidateLogin:
    raw_session_token: str
    expires_at: datetime
    registration_id: str
    stream: str


def normalize_email(value: str) -> str:
    normalized = value.strip().casefold()
    if len(normalized) > 320 or not _EMAIL.fullmatch(normalized):
        raise RegistrationError("invalid_email", 422)
    return normalized


def normalize_mobile(value: str) -> str:
    """Store a normalized Indian mobile, but do not verify or uniquely claim it."""
    digits = re.sub(r"[\s().-]", "", value)
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if not re.fullmatch(r"[6-9][0-9]{9}", digits):
        raise RegistrationError("invalid_mobile", 422)
    return f"+91{digits}"


def validate_registration(name: str, email: str, mobile: str, stream: str) -> tuple[str, str, str, str]:
    full_name = " ".join(name.split())
    normalized_email = normalize_email(email)
    normalized_mobile = normalize_mobile(mobile)
    normalized_stream = stream.strip().casefold()
    if not full_name or len(full_name) > 200:
        raise RegistrationError("invalid_name", 422)
    if normalized_stream not in ALLOWED_STREAMS:
        raise RegistrationError("invalid_stream", 422)
    return full_name, normalized_email, normalized_mobile, normalized_stream


def _keyed_digest(value: str, *, settings: Settings, namespace: str) -> str:
    key = settings.require_otp_hmac_pepper().encode("utf-8")
    message = f"sutravya-{namespace}-v1\x1f{value}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _consume_bucket(
    session: Session,
    *,
    scope: str,
    subject: str,
    limit: int,
    window_seconds: int,
    settings: Settings,
    now: datetime,
) -> bool:
    digest = _keyed_digest(subject, settings=settings, namespace="rate-limit")
    dialect = session.get_bind().dialect.name
    insert = pg_insert if dialect == "postgresql" else sqlite_insert if dialect == "sqlite" else None
    if insert is None:
        raise RuntimeError("Rate limiting requires PostgreSQL or SQLite.")
    cutoff = now - timedelta(seconds=window_seconds)
    statement = insert(RateLimitBucket).values(
        scope=scope,
        subject_digest=digest,
        window_started_at=now,
        request_count=1,
    )
    reset = RateLimitBucket.window_started_at <= cutoff
    statement = statement.on_conflict_do_update(
        index_elements=["scope", "subject_digest"],
        set_={
            "window_started_at": case((reset, now), else_=RateLimitBucket.window_started_at),
            "request_count": case((reset, 1), else_=RateLimitBucket.request_count + 1),
        },
    )
    session.execute(statement)
    count = session.scalar(
        select(RateLimitBucket.request_count).where(
            RateLimitBucket.scope == scope,
            RateLimitBucket.subject_digest == digest,
        )
    )
    return bool(count is not None and count <= limit)


def enforce_rate_limit(
    session: Session,
    *,
    scope: str,
    subject: str,
    limit: int,
    window_seconds: int,
    settings: Settings,
    now: datetime | None = None,
) -> None:
    current = now or datetime.now(timezone.utc)
    with session.begin():
        allowed = _consume_bucket(
            session,
            scope=scope,
            subject=subject,
            limit=limit,
            window_seconds=window_seconds,
            settings=settings,
            now=current,
        )
    if not allowed:
        raise RegistrationError("too_many_requests", 429)


def _add_email_challenge(
    session: Session,
    *,
    candidate: Candidate,
    settings: Settings,
    purpose: str,
    now: datetime,
    is_internal_test: bool = False,
) -> PendingEmailChallenge:
    if purpose not in {REGISTRATION_OTP_PURPOSE, LOGIN_OTP_PURPOSE}:
        raise ValueError("Unsupported email OTP purpose.")
    latest = session.scalar(
        select(VerificationChallenge)
        .where(
            VerificationChallenge.candidate_id == candidate.id,
            VerificationChallenge.channel == "email",
            VerificationChallenge.purpose == purpose,
        )
        .order_by(VerificationChallenge.created_at.desc())
        .limit(1)
    )
    if latest is not None and now < _utc(latest.created_at) + timedelta(seconds=settings.otp_resend_cooldown_seconds):
        raise RegistrationError("resend_cooldown", 429)
    session.query(VerificationChallenge).filter(
        VerificationChallenge.candidate_id == candidate.id,
        VerificationChallenge.channel == "email",
        VerificationChallenge.purpose == purpose,
        VerificationChallenge.consumed_at.is_(None),
        VerificationChallenge.invalidated_at.is_(None),
    ).update({VerificationChallenge.invalidated_at: now}, synchronize_session=False)
    otp = generate_otp()
    challenge = VerificationChallenge(
        candidate_id=candidate.id,
        channel="email",
        purpose=purpose,
        destination_digest=digest_destination(
            candidate.email or "", settings=settings, candidate_id=candidate.id,
            channel="email", purpose=purpose,
        ),
        otp_digest="0" * 64,
        created_at=now,
        expires_at=now + timedelta(seconds=settings.otp_expiry_seconds),
        is_internal_test=is_internal_test,
    )
    session.add(challenge)
    session.flush()
    challenge.otp_digest = digest_otp(
        otp, settings=settings, challenge_id=challenge.id, candidate_id=candidate.id,
        channel="email", purpose=purpose,
    )
    return PendingEmailChallenge(challenge.id, candidate.id, candidate.email or "", otp, purpose)


def create_registration_challenge(
    session: Session,
    *,
    settings: Settings,
    name: str,
    email: str,
    mobile: str,
    stream: str,
    is_internal_test: bool = False,
    now: datetime | None = None,
) -> PendingEmailChallenge:
    current = now or datetime.now(timezone.utc)
    full_name, normalized_email, normalized_mobile, normalized_stream = validate_registration(name, email, mobile, stream)
    with session.begin():
        candidate = session.scalar(
            select(Candidate)
            .where(func.lower(Candidate.email) == normalized_email)
            .order_by(Candidate.email_verified_at.is_not(None).desc(), Candidate.created_at)
            .limit(1)
            .with_for_update()
        )
        if candidate is not None and candidate.email_verified_at is not None:
            existing_official = session.scalar(
                select(Registration.id).where(
                    Registration.candidate_id == candidate.id,
                    Registration.event_key == EVENT_KEY,
                    Registration.is_internal_test.is_(False),
                ).limit(1)
            )
            # A rehearsal record must not prevent the same verified person from
            # completing their one official event registration after launch.
            if is_internal_test or existing_official is not None:
                raise RegistrationError("registration_unavailable", 409)
        if candidate is None:
            candidate = Candidate(full_name=full_name, email=normalized_email, phone=normalized_mobile)
            session.add(candidate)
            session.flush()
        else:
            candidate.full_name = full_name
            candidate.email = normalized_email
            candidate.phone = normalized_mobile
        candidate.pending_stream = normalized_stream
        return _add_email_challenge(
            session, candidate=candidate, settings=settings,
            purpose=REGISTRATION_OTP_PURPOSE, now=current,
            is_internal_test=is_internal_test,
        )


def create_login_challenge(
    session: Session,
    *,
    settings: Settings,
    email: str,
    now: datetime | None = None,
) -> PendingEmailChallenge | None:
    current = now or datetime.now(timezone.utc)
    normalized_email = normalize_email(email)
    with session.begin():
        candidate = session.scalar(
            select(Candidate)
            .where(
                func.lower(Candidate.email) == normalized_email,
                Candidate.email_verified_at.is_not(None),
            )
            .with_for_update()
        )
        if candidate is None:
            return None
        registration = session.scalar(
            select(Registration).where(
                Registration.candidate_id == candidate.id,
                Registration.event_key == EVENT_KEY,
                Registration.is_internal_test.is_(False),
            )
        )
        if registration is None:
            return None
        return _add_email_challenge(
            session, candidate=candidate, settings=settings,
            purpose=LOGIN_OTP_PURPOSE, now=current,
        )


def resend_email_challenge(
    session: Session,
    *,
    settings: Settings,
    challenge_id: UUID,
    expected_purpose: str,
    is_internal_test: bool | None = None,
    now: datetime | None = None,
) -> PendingEmailChallenge:
    current = now or datetime.now(timezone.utc)
    with session.begin():
        prior = session.scalar(
            select(VerificationChallenge)
            .where(
                VerificationChallenge.id == challenge_id,
                VerificationChallenge.channel == "email",
                VerificationChallenge.purpose == expected_purpose,
                VerificationChallenge.consumed_at.is_(None),
            )
            .with_for_update()
        )
        if prior is None:
            raise RegistrationError("challenge_unavailable", 400)
        if is_internal_test is not None and prior.is_internal_test != is_internal_test:
            raise RegistrationError("challenge_unavailable", 400)
        candidate = session.scalar(select(Candidate).where(Candidate.id == prior.candidate_id).with_for_update())
        if candidate is None or not candidate.email:
            raise RegistrationError("challenge_unavailable", 400)
        if expected_purpose == LOGIN_OTP_PURPOSE and candidate.email_verified_at is None:
            raise RegistrationError("challenge_unavailable", 400)
        return _add_email_challenge(
            session, candidate=candidate, settings=settings, purpose=expected_purpose, now=current,
            is_internal_test=prior.is_internal_test,
        )


def _new_registration_id() -> str:
    return f"SUT26-{secrets.token_hex(8).upper()}"


def verify_registration_email(
    session: Session,
    *,
    settings: Settings,
    challenge_id: UUID,
    otp: str,
    now: datetime | None = None,
) -> tuple[ChallengeVerification, RegistrationSummary | None]:
    current = now or datetime.now(timezone.utc)
    with session.begin():
        challenge = session.get(VerificationChallenge, challenge_id)
        if challenge is None:
            return ChallengeVerification.NOT_FOUND, None
        outcome = verify_and_consume_challenge(
            session, settings=settings, candidate_id=challenge.candidate_id,
            challenge_id=challenge_id, channel="email", otp=otp,
            purpose=REGISTRATION_OTP_PURPOSE, now=current,
        )
        if outcome != ChallengeVerification.VERIFIED:
            return outcome, None
        candidate = session.scalar(
            select(Candidate).where(Candidate.id == challenge.candidate_id).with_for_update()
        )
        if candidate is None or candidate.email_verified_at is None or not candidate.pending_stream:
            raise RegistrationError("registration_unavailable", 409)
        registration = session.scalar(
            select(Registration).where(
                Registration.candidate_id == candidate.id,
                Registration.event_key == EVENT_KEY,
                Registration.is_internal_test.is_(False),
            ).with_for_update()
        )
        if registration is None:
            registration = Registration(
                candidate_id=candidate.id,
                event_key=EVENT_KEY,
                registration_id=_new_registration_id(),
                stream=candidate.pending_stream,
                status="active",
                is_internal_test=challenge.is_internal_test,
            )
            session.add(registration)
            session.flush()
        else:
            # Complete any legacy/incomplete registration row without creating a duplicate.
            if not registration.registration_id:
                registration.registration_id = _new_registration_id()
            if not registration.stream:
                registration.stream = candidate.pending_stream
            if not registration.status:
                registration.status = "active"
        candidate.pending_stream = None
        summary = RegistrationSummary(
            registration_id=registration.registration_id or "",
            email=candidate.email or "",
            full_name=candidate.full_name or "Candidate",
            stream=registration.stream or "",
            is_internal_test=registration.is_internal_test,
        )
    return outcome, summary


def verify_login_email(
    session: Session,
    *,
    settings: Settings,
    email: str,
    otp: str,
    now: datetime | None = None,
) -> tuple[ChallengeVerification, CandidateLogin | None]:
    current = now or datetime.now(timezone.utc)
    normalized_email = normalize_email(email)
    with session.begin():
        candidate = session.scalar(
            select(Candidate)
            .where(
                func.lower(Candidate.email) == normalized_email,
                Candidate.email_verified_at.is_not(None),
            )
            .with_for_update()
        )
        if candidate is None:
            return ChallengeVerification.NOT_FOUND, None
        registration = session.scalar(
            select(Registration).where(
                Registration.candidate_id == candidate.id,
                Registration.event_key == EVENT_KEY,
                Registration.is_internal_test.is_(False),
            )
        )
        challenge = session.scalar(
            select(VerificationChallenge)
            .where(
                VerificationChallenge.candidate_id == candidate.id,
                VerificationChallenge.channel == "email",
                VerificationChallenge.purpose == LOGIN_OTP_PURPOSE,
                VerificationChallenge.consumed_at.is_(None),
                VerificationChallenge.invalidated_at.is_(None),
            )
            .order_by(VerificationChallenge.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        if registration is None or challenge is None:
            return ChallengeVerification.NOT_FOUND, None
        outcome = verify_and_consume_challenge(
            session, settings=settings, candidate_id=candidate.id,
            challenge_id=challenge.id, channel="email", otp=otp,
            purpose=LOGIN_OTP_PURPOSE, now=current,
        )
        if outcome != ChallengeVerification.VERIFIED:
            return outcome, None
        raw_token = secrets.token_urlsafe(32)
        expiry = current + timedelta(seconds=SESSION_SECONDS)
        session.add(
            CandidateSession(
                candidate_id=candidate.id,
                token_digest=hashlib.sha256(raw_token.encode("ascii")).hexdigest(),
                created_at=current,
                expires_at=expiry,
            )
        )
        login = CandidateLogin(raw_token, expiry, registration.registration_id or "", registration.stream or "")
    return outcome, login


def get_candidate_session(
    session: Session,
    raw_token: str | None,
    *,
    now: datetime | None = None,
) -> RegistrationSummary | None:
    if not raw_token:
        return None
    current = now or datetime.now(timezone.utc)
    token_digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    row = session.execute(
        select(CandidateSession, Candidate, Registration)
        .join(Candidate, Candidate.id == CandidateSession.candidate_id)
        .join(Registration, Registration.candidate_id == Candidate.id)
        .where(
            CandidateSession.token_digest == token_digest,
            CandidateSession.revoked_at.is_(None),
            CandidateSession.expires_at > current,
            Candidate.email_verified_at.is_not(None),
            Registration.event_key == EVENT_KEY,
            Registration.is_internal_test.is_(False),
        )
    ).first()
    if row is None:
        return None
    _session_record, candidate, registration = row
    return RegistrationSummary(
        registration_id=registration.registration_id or "",
        email=candidate.email or "",
        full_name=candidate.full_name or "Candidate",
        stream=registration.stream or "",
        is_internal_test=registration.is_internal_test,
    )


def revoke_candidate_session(session: Session, raw_token: str | None, *, now: datetime | None = None) -> None:
    if not raw_token:
        return
    current = now or datetime.now(timezone.utc)
    digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    with session.begin():
        token_session = session.scalar(
            select(CandidateSession).where(CandidateSession.token_digest == digest).with_for_update()
        )
        if token_session is not None and token_session.revoked_at is None:
            token_session.revoked_at = current


def invalidate_challenge(session: Session, challenge_id: UUID, *, now: datetime | None = None) -> None:
    """Invalidate a challenge after delivery failure without retaining its OTP."""
    current = now or datetime.now(timezone.utc)
    with session.begin():
        challenge = session.scalar(
            select(VerificationChallenge).where(VerificationChallenge.id == challenge_id).with_for_update()
        )
        if challenge is not None and challenge.consumed_at is None and challenge.invalidated_at is None:
            challenge.invalidated_at = current

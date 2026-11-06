"""FastAPI registration and passwordless email OTP API."""

from __future__ import annotations

import time
import uuid
import logging
import hashlib
import hmac
import csv
import io
from decimal import Decimal
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from typing import Callable, Iterator, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.database import create_database_engine
from app.email_provider import (
    EmailDeliveryError,
    EmailProviderConfigurationError,
    send_otp_email,
    send_registration_confirmation,
)
from app.logging_config import configure_logging
from app.models import (
    AnswerOption, AuditEvent, Candidate, ExamAttempt, ExamSlot, Question,
    QuestionBank, Registration, Result, ScoringRule, VerificationChallenge,
)
from app.exam_service import (
    ExamError,
    exam_availability,
    get_attempt,
    get_current_attempt,
    get_question,
    save_answer,
    start_exam,
    submit_exam,
)
from app.registration import (
    EVENT_KEY,
    LOGIN_OTP_PURPOSE,
    REGISTRATION_OTP_PURPOSE,
    PUBLIC_REGISTRATION_SOURCE,
    TEAM_PRELAUNCH_SOURCE,
    RegistrationError,
    create_login_challenge,
    create_registration_challenge,
    enforce_rate_limit,
    get_candidate_session,
    invalidate_challenge,
    normalize_email,
    resend_email_challenge,
    revoke_candidate_session,
    verify_login_email,
    verify_registration_email,
)
from app.verification import ChallengeVerification


SESSION_COOKIE = "sutravya_candidate_session"
REGISTRATION_TIMEZONE = ZoneInfo("Asia/Kolkata")
REGISTRATION_OPENS_AT = datetime(2026, 11, 1, 0, 0, 0, tzinfo=REGISTRATION_TIMEZONE)
REGISTRATION_CLOSES_AT = datetime(2026, 11, 26, 0, 0, 0, tzinfo=REGISTRATION_TIMEZONE)


def _registration_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_registration_window(now: datetime) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    current = now.astimezone(REGISTRATION_TIMEZONE)
    if current < REGISTRATION_OPENS_AT:
        raise RegistrationError("registration_not_open", 403)
    if current >= REGISTRATION_CLOSES_AT:
        raise RegistrationError("registration_closed", 410)
    return current.astimezone(timezone.utc)


def _authorize_registration_request(request: Request, settings: Settings, now: datetime) -> str:
    """Authorize registration before launch and return its reporting source."""
    supplied_code = request.headers.get("x-internal-test-code", "")
    current = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now
    current = current.astimezone(REGISTRATION_TIMEZONE)
    if current >= REGISTRATION_CLOSES_AT:
        raise RegistrationError("registration_closed", 410)
    if current >= REGISTRATION_OPENS_AT:
        return PUBLIC_REGISTRATION_SOURCE
    configured_code = settings.internal_test_access_code
    if (
        not settings.internal_test_mode
        or not configured_code
        or not supplied_code
        or len(supplied_code) > 256
        or not hmac.compare_digest(supplied_code.encode("utf-8"), configured_code.encode("utf-8"))
    ):
        raise RegistrationError("internal_test_unauthorized", 403)
    return TEAM_PRELAUNCH_SOURCE


def _require_registration_deadline(now: datetime) -> None:
    current = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now
    current = current.astimezone(REGISTRATION_TIMEZONE)
    if current >= REGISTRATION_CLOSES_AT:
        raise RegistrationError("registration_closed", 410)


def _csv_safe_cell(value: object) -> str:
    """Prefix spreadsheet formula initiators so candidate text opens as text."""
    cell = "" if value is None else str(value)
    if cell.startswith(("\t", "\r", "\n")) or cell.lstrip("\ufeff").lstrip().startswith(("=", "+", "-", "@")):
        return "'" + cell
    return cell


class RegistrationRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    mobile: str = Field(min_length=10, max_length=20)
    email: str = Field(min_length=3, max_length=320)
    stream: str = Field(min_length=1, max_length=32)


class EmailOtpRequest(BaseModel):
    challenge_id: UUID
    otp: str = Field(min_length=1, max_length=32)


class ResendOtpRequest(BaseModel):
    challenge_id: UUID


class EmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class LoginVerifyRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    otp: str = Field(min_length=1, max_length=32)


class ConfirmationResendRequest(BaseModel):
    registration_id: str = Field(min_length=1, max_length=32)


class ExamAnswerRequest(BaseModel):
    question_id: UUID
    option_id: UUID


class AdminSlotRequest(BaseModel):
    stream: Literal["paramedical", "nursing", "mbbs_1st_year"]
    starts_at: datetime
    ends_at: datetime
    capacity: int = Field(gt=0, le=1500)


class AdminOptionRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=8)
    option_text: str = Field(min_length=1, max_length=2000)


class AdminQuestionRequest(BaseModel):
    question_text: str = Field(min_length=1, max_length=10000)
    section: Literal["anatomy", "physiology", "biology", "quantitative_reasoning", "english_communication"]
    difficulty: Literal["easy", "moderate"]
    time_limit_seconds: int = Field(ge=15, le=60)
    category: str | None = Field(default=None, max_length=120)
    explanation: str | None = Field(default=None, max_length=10000)
    source_reference: str | None = Field(default=None, max_length=200)
    options: list[AdminOptionRequest] = Field(min_length=4, max_length=4)
    correct_identifier: str = Field(min_length=1, max_length=8)


class AdminQuestionBankRequest(BaseModel):
    stream: Literal["paramedical", "nursing", "mbbs_1st_year"]
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    correct_points: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    questions: list[AdminQuestionRequest] = Field(min_length=100, max_length=100)


class AdminSlotAssignmentRequest(BaseModel):
    registration_ids: list[str] = Field(min_length=1, max_length=1500)


def _require_admin(settings: Settings, supplied_key: str | None) -> None:
    configured_key = settings.admin_api_key
    if not configured_key:
        raise HTTPException(status_code=503, detail="Assessment administration is not configured.")
    if (
        not supplied_key
        or len(supplied_key) > 512
        or not hmac.compare_digest(supplied_key.encode("utf-8"), configured_key.encode("utf-8"))
    ):
        raise HTTPException(status_code=403, detail="Administrator authorization failed.")


def _exam_error(error: ExamError) -> HTTPException:
    messages = {
        "authentication_required": "Sign in to access your assessment.",
        "eligible_registration_required": "An eligible verified registration is required.",
        "exam_not_configured": "Your assessment is not configured yet. Please contact the organiser.",
        "exam_slot_not_assigned": "Your exam slot has not been assigned yet.",
        "exam_slot_stream_mismatch": "Your assigned slot does not match your registered assessment stream. Contact the organiser.",
        "exam_slot_not_open": "Your assigned exam slot is not currently open.",
        "exam_slot_capacity_reached": "Your exam slot has reached its configured capacity. Please contact the organiser.",
        "question_bank_incomplete": "Your assessment paper is being prepared. Please contact the organiser.",
        "question_bank_invalid": "Your assessment paper is not ready. Please contact the organiser.",
        "question_time_expired": "This question time has expired. Move to the next question.",
        "question_not_presented": "Open this question before submitting an answer.",
        "question_not_found": "This question is not available.",
        "scoring_rule_not_configured": "Your assessment scoring is not configured yet.",
        "attempt_already_submitted": "Your assessment attempt has already been submitted.",
        "attempt_not_found": "Assessment attempt not found.",
        "attempt_not_in_progress": "This assessment attempt is no longer active.",
        "exam_time_expired": "The assessment time has expired. Submit your attempt to view the result.",
        "invalid_question_or_option": "The selected answer is not valid for this question.",
        "result_not_available": "Your result is not available yet. Please contact the organiser.",
    }
    return HTTPException(status_code=error.status_code, detail=messages.get(error.code, "Assessment request could not be completed."))


@contextmanager
def _session(request: Request) -> Iterator[Session]:
    factory: sessionmaker[Session] = request.app.state.session_factory
    with factory() as session:
        yield session


def _client_ip(request: Request) -> str:
    # Do not trust forwarded headers unless trusted-proxy middleware is explicitly configured.
    return request.client.host if request.client else "unknown"


def _registration_error(error: RegistrationError) -> HTTPException:
    messages = {
        "invalid_name": "Enter a valid full name.",
        "invalid_email": "Enter a valid email address.",
        "invalid_mobile": "Enter a valid Indian mobile number.",
        "invalid_stream": "Select one of the available exam streams.",
        "too_many_requests": "Too many requests. Please try again later.",
        "resend_cooldown": "Please wait before requesting another code.",
        "challenge_unavailable": "This code request is unavailable. Request a new code.",
        "registration_unavailable": "Registration could not be completed. Check the details or contact support.",
        "registration_not_open": "Registration opens 1 November 2026 at 12:00 AM IST.",
        "registration_closed": "Registration closed after 25 November 2026 at 11:59:59 PM IST.",
        "internal_test_unauthorized": "Internal testing access could not be authorized.",
        "internal_test_unavailable": "Internal testing access is no longer available.",
    }
    return HTTPException(status_code=error.status_code, detail=messages.get(error.code, "Request could not be completed."))


def _limit(session: Session, settings: Settings, *, scope: str, subject: str, maximum: int) -> None:
    try:
        enforce_rate_limit(
            session,
            settings=settings,
            scope=scope,
            subject=subject,
            limit=maximum,
            window_seconds=3600,
        )
    except RegistrationError as error:
        if error.code == "too_many_requests":
            logging.getLogger("sutravya.api").warning("rate_limit_rejected", extra={"scope": scope})
        raise


def _delivery_error() -> HTTPException:
    return HTTPException(status_code=503, detail="Email delivery is temporarily unavailable. Please try again later.")


def _challenge_message(outcome: ChallengeVerification) -> tuple[int, str]:
    return {
        ChallengeVerification.INVALID_CODE: (400, "The code is incorrect."),
        ChallengeVerification.ATTEMPTS_EXHAUSTED: (429, "The code request is locked. Request a new code later."),
        ChallengeVerification.EXPIRED: (400, "The code has expired. Request a new code."),
        ChallengeVerification.CONSUMED: (400, "The code has already been used."),
        ChallengeVerification.INVALIDATED: (400, "The code is no longer valid. Request a new code."),
        ChallengeVerification.NOT_FOUND: (400, "The code request is unavailable."),
    }.get(outcome, (400, "The code request is unavailable."))


_EMAIL_FAILURE_KINDS = {
    "configuration_missing", "provider_http_error", "network_or_timeout", "unexpected_error"
}
_PROVIDER_ERROR_NAMES = {
    "validation_error", "restricted_api_key", "invalid_api_key", "missing_api_key",
    "unauthorized", "domain_not_verified", "sender_not_verified", "testing_mode",
    "recipient_not_allowed", "account_suspended", "account_restricted", "sending_disabled",
    "rate_limit_exceeded", "not_found", "unknown",
}
_PROVIDER_ERROR_KINDS = {
    "domain_verification", "api_key_permission", "sender_address",
    "testing_recipient_restriction", "account_sending_restriction",
    "other_provider_rejection", "unknown",
}


def _log_email_delivery_failure(logger, *, purpose: str, error: Exception) -> None:
    failure_kind = getattr(error, "failure_kind", "unexpected_error")
    if not isinstance(failure_kind, str) or failure_kind not in _EMAIL_FAILURE_KINDS:
        failure_kind = "unexpected_error"
    provider_status_code = getattr(error, "provider_status_code", None)
    if type(provider_status_code) is not int or not 100 <= provider_status_code <= 599:
        provider_status_code = None
    provider_error_name = getattr(error, "provider_error_name", "unknown")
    if not isinstance(provider_error_name, str) or provider_error_name not in _PROVIDER_ERROR_NAMES:
        provider_error_name = "unknown"
    provider_error_kind = getattr(error, "provider_error_kind", "unknown")
    if not isinstance(provider_error_kind, str) or provider_error_kind not in _PROVIDER_ERROR_KINDS:
        provider_error_kind = "unknown"
    details = {"purpose": purpose, "failure_kind": failure_kind}
    if provider_status_code is not None:
        details["provider_status_code"] = provider_status_code
    if failure_kind == "provider_http_error":
        details["provider_error_name"] = provider_error_name
        details["provider_error_kind"] = provider_error_kind
    logger.warning("email_delivery_failed", extra=details)


def _send_otp(request: Request, pending) -> None:
    try:
        request.app.state.email_sender(
            recipient_email=pending.email,
            recipient_name="Candidate",
            otp=pending.otp,
            purpose=pending.purpose,
            settings=request.app.state.settings,
        )
    except Exception as error:
        _log_email_delivery_failure(logging.getLogger("sutravya.api"), purpose=pending.purpose, error=error)
        raise EmailDeliveryError("Email submission failed.") from None


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: sessionmaker[Session] | None = None,
    email_sender: Callable[..., None] = send_otp_email,
    confirmation_sender: Callable[..., None] = send_registration_confirmation,
) -> FastAPI:
    """Build the API after configuration validation; engine creation is lazy."""
    active_settings = settings or Settings.from_env()
    logger = configure_logging(active_settings.log_level)
    docs_enabled = active_settings.app_env != "production"
    application = FastAPI(
        title="SUTRAVYA Learning & Assessment API",
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    if session_factory is None:
        engine = create_database_engine(active_settings, pool_pre_ping=True)
        session_factory = sessionmaker(bind=engine, autoflush=True, expire_on_commit=False)
        application.state.database_engine = engine
    application.state.session_factory = session_factory
    application.state.settings = active_settings
    application.state.email_sender = email_sender
    application.state.confirmation_sender = confirmation_sender

    def log_email_runtime_config_check() -> None:
        api_key = active_settings.resend_api_key
        sender = active_settings.resend_from_email or ""
        _display_name, sender_address = parseaddr(sender)
        sender_domain = sender_address.rsplit("@", 1)[1].lower() if "@" in sender_address else ""
        logger.info(
            "email_runtime_config_check",
            extra={
                "resend_key_present": bool(api_key),
                "resend_key_fingerprint": hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]
                if api_key else "missing",
                "resend_sender_expected_match": sender == "SUTRAVYA <noreply@mail.sutravya.in>",
                "resend_sender_domain_match": sender_domain == "mail.sutravya.in",
            },
        )

    application.router.on_startup.append(log_email_runtime_config_check)

    if active_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(active_settings.cors_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT"],
            allow_headers=["Content-Type", "X-Internal-Test-Code", "X-Admin-Key"],
        )

    @application.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = str(uuid.uuid4())
        started = time.perf_counter()
        status_code = 500
        try:
            origin = request.headers.get("origin")
            if (
                origin
                and request.url.path.startswith("/api/")
                and origin.rstrip("/") not in active_settings.cors_origins
            ):
                status_code = 403
                return JSONResponse(status_code=403, content={"detail": "Origin is not allowed."})
            response = await call_next(request)
            status_code = response.status_code
            if request.url.path.startswith("/api/exam/") or request.url.path.startswith("/api/admin/assessment/"):
                response.headers["Cache-Control"] = "no-store, private"
                response.headers["Pragma"] = "no-cache"
            return response
        except Exception:
            logger.error("request_failed", extra={"request_id": request_id, "method": request.method, "status_code": status_code})
            raise
        finally:
            logger.info(
                "request_complete",
                extra={"request_id": request_id, "method": request.method, "status_code": status_code,
                       "duration_ms": round((time.perf_counter() - started) * 1000, 2)},
            )

    @application.get("/health", tags=["operations"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/api/registrations/start", status_code=202, tags=["registration"])
    def start_registration(payload: RegistrationRequest, request: Request):
        with _session(request) as session:
            settings = request.app.state.settings
            try:
                request_now = _registration_now()
                if request_now.astimezone(REGISTRATION_TIMEZONE) < REGISTRATION_OPENS_AT:
                    _limit(session, settings, scope="internal_test_ip", subject=_client_ip(request), maximum=10)
                registration_source = _authorize_registration_request(request, settings, request_now)
                if registration_source == PUBLIC_REGISTRATION_SOURCE:
                    _require_registration_window(request_now)
                email = normalize_email(payload.email)
                _limit(session, settings, scope="registration_ip", subject=_client_ip(request), maximum=30)
                _limit(session, settings, scope="registration_email", subject=email, maximum=5)
                _limit(session, settings, scope="email_global", subject="all", maximum=1000)
                registration_now = _registration_now()
                if registration_source == PUBLIC_REGISTRATION_SOURCE:
                    registration_now = _require_registration_window(registration_now)
                else:
                    _require_registration_deadline(registration_now)
                pending = create_registration_challenge(
                    session, settings=settings, name=payload.full_name, email=email,
                    mobile=payload.mobile, stream=payload.stream, now=registration_now,
                    registration_source=registration_source,
                )
            except RegistrationError as error:
                # Do not reveal whether an email already owns a completed registration.
                if error.code == "registration_unavailable":
                    return {"message": "If this email can be registered, a verification code will be sent."}
                raise _registration_error(error)
            try:
                _send_otp(request, pending)
            except (EmailProviderConfigurationError, EmailDeliveryError):
                invalidate_challenge(session, pending.challenge_id)
                raise _delivery_error()
            return {"challenge_id": str(pending.challenge_id), "expires_in": settings.otp_expiry_seconds}

    @application.post("/api/registrations/resend-otp", status_code=202, tags=["registration"])
    def resend_registration_otp(payload: ResendOtpRequest, request: Request):
        with _session(request) as session:
            settings = request.app.state.settings
            try:
                request_now = _registration_now()
                if request_now.astimezone(REGISTRATION_TIMEZONE) < REGISTRATION_OPENS_AT:
                    _limit(session, settings, scope="internal_test_ip", subject=_client_ip(request), maximum=10)
                request_source = _authorize_registration_request(request, settings, request_now)
                _limit(session, settings, scope="otp_resend_ip", subject=_client_ip(request), maximum=20)
                with session.begin():
                    prior = session.get(VerificationChallenge, payload.challenge_id)
                    if (
                        prior is None
                        or prior.purpose != REGISTRATION_OTP_PURPOSE
                        or prior.is_internal_test
                        or prior.registration_source == "legacy_internal_test"
                    ):
                        raise RegistrationError("challenge_unavailable", 400)
                    if request_source == TEAM_PRELAUNCH_SOURCE and prior.registration_source != TEAM_PRELAUNCH_SOURCE:
                        raise RegistrationError("challenge_unavailable", 400)
                    candidate = session.get(Candidate, prior.candidate_id)
                    email = normalize_email(candidate.email or "") if candidate else ""
                if not email:
                    raise RegistrationError("challenge_unavailable", 400)
                _limit(session, settings, scope="registration_email", subject=email, maximum=5)
                _limit(session, settings, scope="email_global", subject="all", maximum=1000)
                registration_now = _registration_now()
                if prior.registration_source == PUBLIC_REGISTRATION_SOURCE:
                    registration_now = _require_registration_window(registration_now)
                else:
                    _require_registration_deadline(registration_now)
                pending = resend_email_challenge(
                    session, settings=settings, challenge_id=payload.challenge_id,
                    expected_purpose=REGISTRATION_OTP_PURPOSE, now=registration_now,
                )
            except RegistrationError as error:
                raise _registration_error(error)
            try:
                _send_otp(request, pending)
            except (EmailProviderConfigurationError, EmailDeliveryError):
                invalidate_challenge(session, pending.challenge_id)
                raise _delivery_error()
            return {"challenge_id": str(pending.challenge_id), "expires_in": settings.otp_expiry_seconds}

    @application.post("/api/registrations/verify-email", tags=["registration"])
    def verify_registration(payload: EmailOtpRequest, request: Request):
        with _session(request) as session:
            settings = request.app.state.settings
            try:
                request_now = _registration_now()
                if request_now.astimezone(REGISTRATION_TIMEZONE) < REGISTRATION_OPENS_AT:
                    _limit(session, settings, scope="internal_test_ip", subject=_client_ip(request), maximum=10)
                request_source = _authorize_registration_request(request, settings, request_now)
                _limit(session, settings, scope="otp_verify_ip", subject=_client_ip(request), maximum=60)
                with session.begin():
                    candidate_email = session.scalar(
                        select(Candidate.email)
                        .join(VerificationChallenge, VerificationChallenge.candidate_id == Candidate.id)
                        .where(VerificationChallenge.id == payload.challenge_id)
                    )
                verification_subject = (
                    normalize_email(candidate_email) if candidate_email else f"challenge:{payload.challenge_id}"
                )
                _limit(session, settings, scope="registration_verify_email", subject=verification_subject, maximum=20)
                registration_now = _registration_now()
                with session.begin():
                    challenge = session.get(VerificationChallenge, payload.challenge_id)
                    if (
                        challenge is not None
                        and challenge.purpose == REGISTRATION_OTP_PURPOSE
                        and (
                            challenge.is_internal_test
                            or challenge.registration_source == "legacy_internal_test"
                            or (
                                request_source == TEAM_PRELAUNCH_SOURCE
                                and challenge.registration_source != TEAM_PRELAUNCH_SOURCE
                            )
                        )
                    ):
                        raise RegistrationError("challenge_unavailable", 400)
                if request_source == PUBLIC_REGISTRATION_SOURCE:
                    registration_now = _require_registration_window(registration_now)
                else:
                    _require_registration_deadline(registration_now)
                outcome, registration = verify_registration_email(
                    session, settings=settings, challenge_id=payload.challenge_id, otp=payload.otp,
                    now=registration_now,
                )
            except RegistrationError as error:
                raise _registration_error(error)
            except IntegrityError:
                # Includes a concurrent verified-email winner or Registration ID collision.
                raise HTTPException(status_code=409, detail="Registration could not be completed. Please request a new code or contact support.")
            if outcome != ChallengeVerification.VERIFIED or registration is None:
                status, message = _challenge_message(outcome)
                raise HTTPException(status_code=status, detail=message)
            try:
                request.app.state.confirmation_sender(
                    recipient_email=registration.email,
                    recipient_name=registration.full_name,
                    registration_id=registration.registration_id,
                    stream=registration.stream,
                    settings=settings,
                )
                sent = True
            except Exception as error:
                _log_email_delivery_failure(logger, purpose="registration_confirmation", error=error)
                sent = False
            return {
                "registration_id": registration.registration_id,
                "registration_source": registration.registration_source,
                "confirmation_email_sent": sent,
                "message": "Registration complete. Save your Registration ID.",
            }

    @application.post("/api/registrations/resend-confirmation", status_code=202, tags=["registration"])
    def resend_confirmation(payload: ConfirmationResendRequest, request: Request):
        with _session(request) as session:
            settings = request.app.state.settings
            try:
                _limit(session, settings, scope="confirmation_ip", subject=_client_ip(request), maximum=20)
                _limit(session, settings, scope="confirmation_registration", subject=payload.registration_id, maximum=3)
                with session.begin():
                    registration = session.scalar(
                        select(Registration).where(
                            Registration.registration_id == payload.registration_id,
                            Registration.event_key == EVENT_KEY,
                        )
                    )
                    candidate = session.get(Candidate, registration.candidate_id) if registration else None
                    recipient = (candidate.email, candidate.full_name, registration.registration_id, registration.stream) if (
                        candidate and candidate.email_verified_at and candidate.email
                    ) else None
            except RegistrationError as error:
                raise _registration_error(error)
            if recipient:
                recipient_email, recipient_name, registration_id, stream = recipient
                try:
                    request.app.state.confirmation_sender(
                        recipient_email=recipient_email, recipient_name=recipient_name or "Candidate",
                        registration_id=registration_id or "", stream=stream or "",
                        settings=settings,
                    )
                except Exception as error:
                    _log_email_delivery_failure(logger, purpose="registration_confirmation", error=error)
            return {"message": "If the registration is eligible, a confirmation email will be sent."}

    @application.get("/api/exam/availability", tags=["candidate assessment"])
    def candidate_exam_availability(request: Request):
        try:
            with _session(request) as session:
                return exam_availability(session, request.cookies.get(SESSION_COOKIE))
        except ExamError as error:
            raise _exam_error(error)

    @application.post("/api/exam/attempts/start", status_code=201, tags=["candidate assessment"])
    def candidate_exam_start(request: Request):
        try:
            with _session(request) as session:
                return start_exam(session, request.cookies.get(SESSION_COOKIE))
        except ExamError as error:
            raise _exam_error(error)

    @application.get("/api/exam/attempts/current", tags=["candidate assessment"])
    def candidate_exam_current_attempt(request: Request):
        try:
            with _session(request) as session:
                return get_current_attempt(session, request.cookies.get(SESSION_COOKIE))
        except ExamError as error:
            raise _exam_error(error)

    @application.get("/api/exam/attempts/{attempt_id}/questions/{position}", tags=["candidate assessment"])
    def candidate_exam_question(attempt_id: UUID, position: int, request: Request):
        if position < 0 or position >= 100:
            raise HTTPException(status_code=404, detail="Question not found.")
        try:
            with _session(request) as session:
                return get_question(
                    session, request.cookies.get(SESSION_COOKIE),
                    attempt_id=attempt_id, position=position,
                )
        except ExamError as error:
            raise _exam_error(error)

    @application.get("/api/exam/attempts/{attempt_id}", tags=["candidate assessment"])
    def candidate_exam_attempt(attempt_id: UUID, request: Request):
        try:
            with _session(request) as session:
                return get_attempt(session, request.cookies.get(SESSION_COOKIE), attempt_id=attempt_id)
        except ExamError as error:
            raise _exam_error(error)

    @application.put("/api/exam/attempts/{attempt_id}/answer", tags=["candidate assessment"])
    def candidate_exam_save_answer(attempt_id: UUID, payload: ExamAnswerRequest, request: Request):
        try:
            with _session(request) as session:
                return save_answer(
                    session, request.cookies.get(SESSION_COOKIE), attempt_id=attempt_id,
                    question_id=payload.question_id, option_id=payload.option_id,
                )
        except ExamError as error:
            raise _exam_error(error)

    @application.post("/api/exam/attempts/{attempt_id}/submit", tags=["candidate assessment"])
    def candidate_exam_submit(attempt_id: UUID, request: Request):
        try:
            with _session(request) as session:
                return submit_exam(session, request.cookies.get(SESSION_COOKIE), attempt_id=attempt_id)
        except ExamError as error:
            raise _exam_error(error)

    @application.get("/api/admin/assessment/overview", tags=["assessment administration"])
    def assessment_admin_overview(
        request: Request,
        x_admin_key: str | None = Header(default=None),
    ):
        _require_admin(request.app.state.settings, x_admin_key)
        with _session(request) as session:
            streams = ("paramedical", "nursing", "mbbs_1st_year")
            stream_summary = {}
            for stream in streams:
                stream_summary[stream] = {
                    "registrations": int(session.scalar(
                        select(func.count(Registration.id)).where(
                            Registration.event_key == EVENT_KEY,
                            Registration.stream == stream,
                            Registration.is_internal_test.is_(False),
                            Registration.registration_source.in_((PUBLIC_REGISTRATION_SOURCE, TEAM_PRELAUNCH_SOURCE)),
                        )
                    ) or 0),
                    "question_count": int(session.scalar(
                        select(func.count(Question.id))
                        .join(QuestionBank, QuestionBank.id == Question.question_bank_id)
                        .where(QuestionBank.bank_code == stream, Question.is_active.is_(True))
                    ) or 0),
                }
            slots = session.scalars(
                select(ExamSlot).where(ExamSlot.event_key == EVENT_KEY).order_by(ExamSlot.starts_at)
            ).all()
            attempts = int(session.scalar(select(func.count(ExamAttempt.id))) or 0)
            results = int(session.scalar(select(func.count(Result.id))) or 0)
            return {
                "streams": stream_summary,
                "slots": [{
                    "id": str(slot.id), "stream": slot.stream,
                    "starts_at": slot.starts_at.isoformat(), "ends_at": slot.ends_at.isoformat(),
                    "capacity": slot.capacity,
                } for slot in slots],
                "attempts": attempts,
                "results": results,
            }

    @application.post("/api/admin/assessment/slots", status_code=201, tags=["assessment administration"])
    def create_assessment_slot(
        payload: AdminSlotRequest,
        request: Request,
        x_admin_key: str | None = Header(default=None),
    ):
        _require_admin(request.app.state.settings, x_admin_key)
        if payload.starts_at.tzinfo is None or payload.ends_at.tzinfo is None:
            raise HTTPException(status_code=422, detail="Slot timestamps must include a timezone.")
        starts_at = payload.starts_at.astimezone(timezone.utc)
        ends_at = payload.ends_at.astimezone(timezone.utc)
        if starts_at <= datetime.now(timezone.utc) or ends_at - starts_at < timedelta(minutes=30):
            raise HTTPException(status_code=422, detail="Choose a future slot of at least 30 minutes.")
        with _session(request) as session:
            overlap = session.scalar(select(ExamSlot.id).where(
                ExamSlot.event_key == EVENT_KEY,
                ExamSlot.stream == payload.stream,
                ExamSlot.starts_at < ends_at,
                ExamSlot.ends_at > starts_at,
            ))
            if overlap is not None:
                raise HTTPException(status_code=409, detail="This stream already has an overlapping exam slot.")
            slot = ExamSlot(
                event_key=EVENT_KEY, stream=payload.stream,
                starts_at=starts_at, ends_at=ends_at, capacity=payload.capacity,
            )
            session.add(slot)
            session.flush()
            session.add(AuditEvent(
                action="exam_slot_created", target_type="exam_slot", target_id=slot.id,
            ))
            session.commit()
            return {"slot_id": str(slot.id), "stream": slot.stream, "starts_at": slot.starts_at.isoformat(),
                    "ends_at": slot.ends_at.isoformat(), "capacity": slot.capacity}

    @application.post("/api/admin/assessment/slots/{slot_id}/assign", tags=["assessment administration"])
    def assign_registrations_to_slot(
        slot_id: UUID,
        payload: AdminSlotAssignmentRequest,
        request: Request,
        x_admin_key: str | None = Header(default=None),
    ):
        _require_admin(request.app.state.settings, x_admin_key)
        ids = [value.strip() for value in payload.registration_ids]
        if len(set(ids)) != len(ids) or any(not value or len(value) > 32 for value in ids):
            raise HTTPException(status_code=422, detail="Registration IDs must be unique and valid.")
        with _session(request) as session:
            slot = session.get(ExamSlot, slot_id)
            if slot is None or slot.event_key != EVENT_KEY or slot.stream not in {"paramedical", "nursing", "mbbs_1st_year"}:
                raise HTTPException(status_code=404, detail="Assessment slot not found.")
            registrations = session.scalars(select(Registration).where(
                Registration.event_key == EVENT_KEY,
                Registration.registration_id.in_(ids),
                Registration.stream == slot.stream,
                Registration.status == "active",
                Registration.is_internal_test.is_(False),
                Registration.registration_source.in_((PUBLIC_REGISTRATION_SOURCE, TEAM_PRELAUNCH_SOURCE)),
            ).with_for_update()).all()
            if len(registrations) != len(ids):
                raise HTTPException(status_code=422, detail="One or more registrations are invalid or belong to another stream.")
            registration_pk = [row.id for row in registrations]
            existing_attempt = session.scalar(select(ExamAttempt.id).where(
                ExamAttempt.registration_id.in_(registration_pk)
            ).limit(1))
            if existing_attempt is not None:
                raise HTTPException(status_code=409, detail="A registration with an existing exam attempt cannot be reassigned.")
            for row in registrations:
                row.exam_slot_id = slot.id
            session.add(AuditEvent(
                action="exam_slot_registrations_assigned", target_type="exam_slot", target_id=slot.id,
            ))
            session.commit()
            return {"assigned_count": len(registrations), "slot_id": str(slot.id), "stream": slot.stream}

    @application.post("/api/admin/assessment/question-banks/import", status_code=201, tags=["assessment administration"])
    def import_assessment_question_bank(
        payload: AdminQuestionBankRequest,
        request: Request,
        x_admin_key: str | None = Header(default=None),
    ):
        _require_admin(request.app.state.settings, x_admin_key)
        expected = {"A", "B", "C", "D"}
        section_order = ("anatomy", "physiology", "biology", "quantitative_reasoning", "english_communication")
        section_counts = {section: 0 for section in section_order}
        for question in payload.questions:
            section_counts[question.section] += 1
        if any(section_counts[section] != 20 for section in section_order):
            raise HTTPException(status_code=422, detail="Question bank must contain exactly 20 questions in each of the five approved sections.")
        for index, question in enumerate(payload.questions, start=1):
            identifiers = [option.identifier.strip().upper() for option in question.options]
            if set(identifiers) != expected or len(set(identifiers)) != 4:
                raise HTTPException(status_code=422, detail=f"Question {index} must have exactly A, B, C and D options.")
            if question.correct_identifier.strip().upper() not in expected:
                raise HTTPException(status_code=422, detail=f"Question {index} has an invalid correct option.")
        with _session(request) as session:
            bank = session.scalar(select(QuestionBank).where(QuestionBank.bank_code == payload.stream).with_for_update())
            if bank is None:
                bank = QuestionBank(bank_code=payload.stream, title=payload.title, description=payload.description)
                session.add(bank)
                session.flush()
            else:
                existing_questions = int(session.scalar(
                    select(func.count(Question.id)).where(Question.question_bank_id == bank.id)
                ) or 0)
                existing_attempts = session.scalar(
                    select(ExamAttempt.id).where(ExamAttempt.question_bank_id == bank.id).limit(1)
                )
                if existing_questions or existing_attempts:
                    raise HTTPException(status_code=409, detail="This question bank already contains questions or exam attempts.")
                bank.title = payload.title
                bank.description = payload.description
            rule = session.scalar(select(ScoringRule).where(
                ScoringRule.question_bank_id == bank.id, ScoringRule.rule_code == "htse_2026"
            ).with_for_update())
            if rule is None:
                rule = ScoringRule(
                    question_bank_id=bank.id, rule_code="htse_2026",
                    correct_points=payload.correct_points, incorrect_points=Decimal("-0.25"),
                    unanswered_points=Decimal("0"),
                )
                session.add(rule)
            else:
                rule.correct_points = payload.correct_points
                rule.incorrect_points = Decimal("-0.25")
                rule.unanswered_points = Decimal("0")
            for item in payload.questions:
                question = Question(
                    question_bank_id=bank.id, question_text=item.question_text.strip(),
                    category=item.category, section=item.section,
                    difficulty=item.difficulty, time_limit_seconds=item.time_limit_seconds,
                    explanation=item.explanation, source_reference=item.source_reference, is_active=True,
                )
                session.add(question)
                session.flush()
                for option in item.options:
                    identifier = option.identifier.strip().upper()
                    session.add(AnswerOption(
                        question_id=question.id, identifier=identifier,
                        option_text=option.option_text.strip(),
                        is_correct=identifier == item.correct_identifier.strip().upper(),
                    ))
            session.add(AuditEvent(
                action="exam_question_bank_imported", target_type="question_bank", target_id=bank.id,
            ))
            session.commit()
            return {"question_bank_id": str(bank.id), "stream": payload.stream,
                    "question_count": len(payload.questions), "correct_points": str(payload.correct_points),
                    "negative_marking": True, "incorrect_points": "-0.25"}

    @application.get("/api/admin/registrations/export", tags=["organiser export"])
    def export_registrations(
        request: Request,
        source: Literal["all", "team_prelaunch", "public_registration"] = "all",
        x_registration_export_key: str | None = Header(default=None),
    ) -> Response:
        settings = request.app.state.settings
        configured_key = settings.registration_export_key
        if not configured_key:
            raise HTTPException(status_code=503, detail="Registration export is not configured.")
        if (
            not x_registration_export_key
            or len(x_registration_export_key) > 512
            or not hmac.compare_digest(x_registration_export_key, configured_key)
        ):
            raise HTTPException(status_code=403, detail="Export authorization failed.")

        statement = (
            select(Registration, Candidate)
            .join(Candidate, Candidate.id == Registration.candidate_id)
            .where(Registration.event_key == EVENT_KEY)
            .order_by(Registration.created_at, Registration.registration_id)
        )
        if source != "all":
            statement = statement.where(
                Registration.registration_source == source,
                Registration.is_internal_test.is_(False),
            )

        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\r\n")
        writer.writerow((
            "registration_id", "full_name", "email", "mobile", "stream", "registration_date_ist",
            "email_verified", "mobile_verified", "registration_source",
        ))
        with _session(request) as session:
            for registration, candidate in session.execute(statement):
                created_at = registration.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                date_value = created_at.astimezone(REGISTRATION_TIMEZONE).isoformat(timespec="seconds")
                writer.writerow(tuple(_csv_safe_cell(value) for value in (
                    registration.registration_id,
                    candidate.full_name,
                    candidate.email,
                    candidate.phone,
                    registration.stream,
                    date_value,
                    "yes" if candidate.email_verified_at is not None else "no",
                    "yes" if candidate.phone_verified_at is not None else "no",
                    (
                        "legacy_internal_test"
                        if registration.is_internal_test
                        or registration.registration_source == "legacy_internal_test"
                        else registration.registration_source
                    ),
                )))
        csv_bytes = ("\ufeff" + output.getvalue()).encode("utf-8")
        return Response(
            content=csv_bytes,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="sutravya-registrations.csv"'},
        )

    @application.post("/api/auth/request-otp", status_code=202, tags=["candidate account"])
    def request_login_otp(payload: EmailRequest, request: Request):
        with _session(request) as session:
            settings = request.app.state.settings
            try:
                email = normalize_email(payload.email)
                _limit(session, settings, scope="login_ip", subject=_client_ip(request), maximum=30)
                _limit(session, settings, scope="login_email", subject=email, maximum=10)
                pending = create_login_challenge(session, settings=settings, email=email)
                if pending is not None:
                    _limit(session, settings, scope="email_global", subject="all", maximum=1000)
            except RegistrationError as error:
                if error.code == "resend_cooldown":
                    return {"message": "If an eligible account exists, a sign-in code will be sent."}
                raise _registration_error(error)
            if pending is not None:
                try:
                    _send_otp(request, pending)
                except (EmailProviderConfigurationError, EmailDeliveryError):
                    invalidate_challenge(session, pending.challenge_id)
                    raise _delivery_error()
            return {"message": "If an eligible account exists, a sign-in code will be sent."}

    @application.post("/api/auth/verify-otp", tags=["candidate account"])
    def verify_login(payload: LoginVerifyRequest, request: Request, response: Response):
        with _session(request) as session:
            settings = request.app.state.settings
            try:
                email = normalize_email(payload.email)
                _limit(session, settings, scope="login_verify_ip", subject=_client_ip(request), maximum=60)
                _limit(session, settings, scope="login_verify_email", subject=email, maximum=10)
                outcome, login = verify_login_email(session, settings=settings, email=email, otp=payload.otp)
            except RegistrationError as error:
                raise _registration_error(error)
            if outcome != ChallengeVerification.VERIFIED or login is None:
                raise HTTPException(status_code=400, detail="The code is invalid or expired. Request a new code.")
            response.set_cookie(
                SESSION_COOKIE,
                login.raw_session_token,
                max_age=max(0, int((login.expires_at - datetime.now(timezone.utc)).total_seconds())),
                httponly=True,
                secure=settings.app_env == "production",
                samesite="lax",
                path="/api",
            )
            return {"status": "authenticated"}

    @application.get("/api/auth/session", tags=["candidate account"])
    def current_session(request: Request):
        with _session(request) as session:
            summary = get_candidate_session(session, request.cookies.get(SESSION_COOKIE))
            if summary is None:
                raise HTTPException(status_code=401, detail="Authentication required.")
            return {
                "registration_id": summary.registration_id,
                "stream": summary.stream,
                "full_name": summary.full_name,
                "email": summary.email,
            }

    @application.post("/api/auth/logout", status_code=204, tags=["candidate account"])
    def logout(request: Request, response: Response):
        with _session(request) as session:
            revoke_candidate_session(session, request.cookies.get(SESSION_COOKIE))
        response.delete_cookie(
            SESSION_COOKIE, path="/api", secure=request.app.state.settings.app_env == "production",
            httponly=True, samesite="lax",
        )
        response.status_code = 204
        return response

    return application


# Configuration validation occurs before serving traffic. No connection is opened here.
app = create_app()

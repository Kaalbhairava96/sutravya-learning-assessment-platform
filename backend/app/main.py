"""FastAPI registration and passwordless email OTP API."""

from __future__ import annotations

import time
import uuid
import logging
import hashlib
import hmac
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Callable, Iterator
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
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
from app.models import Candidate, Registration, VerificationChallenge
from app.registration import (
    EVENT_KEY,
    LOGIN_OTP_PURPOSE,
    REGISTRATION_OTP_PURPOSE,
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
REGISTRATION_CLOSES_AT = datetime(2026, 11, 16, 0, 0, 0, tzinfo=REGISTRATION_TIMEZONE)


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


def _authorize_registration_request(request: Request, settings: Settings, now: datetime) -> bool:
    """Authorize pre-launch testing and return whether this request is internal."""
    supplied_code = request.headers.get("x-internal-test-code", "")
    current = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now
    current = current.astimezone(REGISTRATION_TIMEZONE)
    if current >= REGISTRATION_CLOSES_AT:
        raise RegistrationError("registration_closed", 410)
    if current >= REGISTRATION_OPENS_AT:
        if supplied_code:
            raise RegistrationError("internal_test_unavailable", 403)
        return False
    configured_code = settings.internal_test_access_code
    if (
        not settings.internal_test_mode
        or not configured_code
        or not supplied_code
        or len(supplied_code) > 256
        or not hmac.compare_digest(supplied_code.encode("utf-8"), configured_code.encode("utf-8"))
    ):
        raise RegistrationError("internal_test_unauthorized", 403)
    return True


def _require_internal_test_window(now: datetime) -> None:
    current = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now
    current = current.astimezone(REGISTRATION_TIMEZONE)
    if current >= REGISTRATION_CLOSES_AT:
        raise RegistrationError("registration_closed", 410)
    if current >= REGISTRATION_OPENS_AT:
        raise RegistrationError("internal_test_unavailable", 403)


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
        "registration_closed": "Registration closed on 15 November 2026 at 11:59:59 PM IST.",
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
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-Internal-Test-Code"],
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
                internal_test = _authorize_registration_request(request, settings, request_now)
                if not internal_test:
                    _require_registration_window(request_now)
                email = normalize_email(payload.email)
                _limit(session, settings, scope="registration_ip", subject=_client_ip(request), maximum=30)
                _limit(session, settings, scope="registration_email", subject=email, maximum=5)
                _limit(session, settings, scope="email_global", subject="all", maximum=1000)
                registration_now = _registration_now()
                if not internal_test:
                    registration_now = _require_registration_window(registration_now)
                else:
                    _require_internal_test_window(registration_now)
                pending = create_registration_challenge(
                    session, settings=settings, name=payload.full_name, email=email,
                    mobile=payload.mobile, stream=payload.stream, now=registration_now,
                    is_internal_test=internal_test,
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
                _authorize_registration_request(request, settings, request_now)
                _limit(session, settings, scope="otp_resend_ip", subject=_client_ip(request), maximum=20)
                with session.begin():
                    prior = session.get(VerificationChallenge, payload.challenge_id)
                    if prior is None or prior.purpose != REGISTRATION_OTP_PURPOSE:
                        raise RegistrationError("challenge_unavailable", 400)
                    if prior.is_internal_test:
                        _require_internal_test_window(request_now)
                    candidate = session.get(Candidate, prior.candidate_id)
                    email = normalize_email(candidate.email or "") if candidate else ""
                if not email:
                    raise RegistrationError("challenge_unavailable", 400)
                _limit(session, settings, scope="registration_email", subject=email, maximum=5)
                _limit(session, settings, scope="email_global", subject="all", maximum=1000)
                registration_now = _registration_now()
                if prior.is_internal_test:
                    _require_internal_test_window(registration_now)
                if not prior.is_internal_test:
                    registration_now = _require_registration_window(registration_now)
                pending = resend_email_challenge(
                    session, settings=settings, challenge_id=payload.challenge_id,
                    expected_purpose=REGISTRATION_OTP_PURPOSE, now=registration_now,
                    is_internal_test=prior.is_internal_test,
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
                _authorize_registration_request(request, settings, request_now)
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
                    if challenge is not None and challenge.purpose == REGISTRATION_OTP_PURPOSE and challenge.is_internal_test:
                        _require_internal_test_window(registration_now)
                if not (challenge and challenge.is_internal_test):
                    registration_now = _require_registration_window(registration_now)
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
                "is_internal_test": registration.is_internal_test,
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
                        Registration.is_internal_test.is_(False),
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

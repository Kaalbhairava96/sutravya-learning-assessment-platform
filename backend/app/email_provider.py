"""Minimal Resend HTTP adapter; sensitive values never enter log messages."""

from __future__ import annotations

import json
import re
from html import escape
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings


_PROVIDER_ERROR_NAMES = {
    "validation_error", "restricted_api_key", "invalid_api_key", "missing_api_key",
    "unauthorized", "domain_not_verified", "sender_not_verified", "testing_mode",
    "recipient_not_allowed", "account_suspended", "account_restricted", "sending_disabled",
    "rate_limit_exceeded", "not_found",
}
_PROVIDER_ERROR_KINDS = {
    "domain_verification", "api_key_permission", "sender_address",
    "testing_recipient_restriction", "account_sending_restriction",
    "other_provider_rejection", "unknown",
}


def _provider_error_diagnostics(body: bytes) -> tuple[str, str]:
    """Return only allowlisted provider identifiers and a normalized category."""
    if not isinstance(body, bytes):
        return "unknown", "unknown"
    try:
        payload = json.loads(body[:8192].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return "unknown", "unknown"
    if not isinstance(payload, dict):
        return "unknown", "unknown"

    raw_name = payload.get("name")
    normalized_name = ""
    if isinstance(raw_name, str) and len(raw_name) <= 48 and re.fullmatch(r"[A-Za-z0-9_-]+", raw_name):
        normalized_name = raw_name.lower().replace("-", "_")
    safe_name = normalized_name if normalized_name in _PROVIDER_ERROR_NAMES else "unknown"

    name_categories = {
        "restricted_api_key": "api_key_permission",
        "invalid_api_key": "api_key_permission",
        "missing_api_key": "api_key_permission",
        "unauthorized": "api_key_permission",
        "domain_not_verified": "domain_verification",
        "sender_not_verified": "sender_address",
        "testing_mode": "testing_recipient_restriction",
        "recipient_not_allowed": "testing_recipient_restriction",
        "account_suspended": "account_sending_restriction",
        "account_restricted": "account_sending_restriction",
        "sending_disabled": "account_sending_restriction",
        "rate_limit_exceeded": "other_provider_rejection",
        "not_found": "other_provider_rejection",
    }
    if normalized_name in name_categories:
        return safe_name, name_categories[normalized_name]

    raw_message = payload.get("message")
    if not isinstance(raw_message, str):
        return safe_name, "unknown"
    message = raw_message[:1024].lower()
    if "test mode" in message or "testing mode" in message or (
        "recipient" in message and any(word in message for word in ("verified", "allowed", "test"))
    ):
        kind = "testing_recipient_restriction"
    elif "domain" in message and any(word in message for word in ("verify", "verified", "verification")):
        kind = "domain_verification"
    elif any(term in message for term in ("api key", "api_key", "permission", "unauthorized", "forbidden")):
        kind = "api_key_permission"
    elif any(term in message for term in ("sender", "from address", "from email", "sender address")):
        kind = "sender_address"
    elif "account" in message and any(term in message for term in ("suspend", "restrict", "disable", "block")):
        kind = "account_sending_restriction"
    else:
        kind = "other_provider_rejection" if normalized_name == "validation_error" else "unknown"
    return safe_name, kind if kind in _PROVIDER_ERROR_KINDS else "unknown"


class EmailProviderConfigurationError(RuntimeError):
    """Raised when private Resend or sender configuration is missing."""

    failure_kind = "configuration_missing"
    provider_status_code = None


class EmailDeliveryError(RuntimeError):
    """Raised when Resend does not accept an email request."""

    def __init__(
        self,
        message: str,
        *,
        failure_kind: str = "unexpected_error",
        provider_status_code: int | None = None,
        provider_error_name: str = "unknown",
        provider_error_kind: str = "unknown",
    ) -> None:
        super().__init__(message)
        self.failure_kind = failure_kind
        self.provider_status_code = provider_status_code
        self.provider_error_name = provider_error_name
        self.provider_error_kind = provider_error_kind


def _send(payload: dict[str, Any], *, settings: Settings) -> None:
    if not settings.resend_api_key or not settings.resend_from_email:
        raise EmailProviderConfigurationError("Transactional email configuration is incomplete.")
    request = Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SUTRAVYA-Assessment-API/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=8) as response:
            response_body = response.read(16_384)
            if not 200 <= response.status < 300:
                error_name, error_kind = _provider_error_diagnostics(response_body)
                raise EmailDeliveryError(
                    "Email provider rejected the message.",
                    failure_kind="provider_http_error",
                    provider_status_code=response.status if isinstance(response.status, int) else None,
                    provider_error_name=error_name,
                    provider_error_kind=error_kind,
                )
    except HTTPError as error:
        # Parse only bounded, allowlisted metadata; never retain the body or exception text.
        try:
            response_body = error.read(8192)
        except (OSError, ValueError):
            response_body = b""
        error_name, error_kind = _provider_error_diagnostics(response_body)
        raise EmailDeliveryError(
            "Email provider rejected the message.",
            failure_kind="provider_http_error",
            provider_status_code=error.code if isinstance(error.code, int) else None,
            provider_error_name=error_name,
            provider_error_kind=error_kind,
        ) from None
    except (URLError, TimeoutError, OSError):
        raise EmailDeliveryError(
            "Email provider is temporarily unavailable.", failure_kind="network_or_timeout"
        ) from None


def send_otp_email(
    *, recipient_email: str, recipient_name: str, otp: str, purpose: str, settings: Settings
) -> None:
    if purpose == "registration_verification":
        subject = "Verify your SUTRAVYA assessment registration"
        lead = "Use this one-time code to verify your email and complete your registration."
    elif purpose == "login":
        subject = "Your SUTRAVYA sign-in code"
        lead = "Use this one-time code to sign in to your candidate account."
    else:
        raise ValueError("Unsupported email OTP purpose.")
    safe_name = escape(recipient_name)
    html = (
        f"<p>Hello {safe_name},</p><p>{lead}</p>"
        f"<p style=\"font-size:28px;font-weight:700;letter-spacing:6px\">{otp}</p>"
        "<p>This code expires in five minutes and can be used once. If you did not request it, ignore this email.</p>"
    )
    _send(
        {"from": settings.resend_from_email, "to": [recipient_email], "subject": subject, "html": html},
        settings=settings,
    )


def send_registration_confirmation(
    *, recipient_email: str, recipient_name: str, registration_id: str,
    stream: str, settings: Settings,
) -> None:
    safe_name, safe_id, safe_stream = escape(recipient_name), escape(registration_id), escape(stream)
    _send(
        {
            "from": settings.resend_from_email,
            "to": [recipient_email],
            "subject": "SUTRAVYA registration confirmed",
            "html": (
                f"<p>Hello {safe_name},</p><p>Your email is verified and your registration is complete.</p>"
                f"<p>Registration ID: <strong>{safe_id}</strong></p><p>Exam stream: {safe_stream}</p>"
                "<p>Keep your Registration ID. You will use email OTP to sign in.</p>"
            ),
        },
        settings=settings,
    )

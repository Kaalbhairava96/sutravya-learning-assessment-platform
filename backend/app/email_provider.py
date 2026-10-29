"""Minimal Resend HTTP adapter; sensitive values never enter log messages."""

from __future__ import annotations

import json
from html import escape
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings


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
    ) -> None:
        super().__init__(message)
        self.failure_kind = failure_kind
        self.provider_status_code = provider_status_code


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
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=8) as response:
            response.read(16_384)
            if not 200 <= response.status < 300:
                raise EmailDeliveryError(
                    "Email provider rejected the message.",
                    failure_kind="provider_http_error",
                    provider_status_code=response.status if isinstance(response.status, int) else None,
                )
    except HTTPError as error:
        # Never include provider bodies, request headers, recipient addresses, or tokens in errors.
        raise EmailDeliveryError(
            "Email provider rejected the message.",
            failure_kind="provider_http_error",
            provider_status_code=error.code if isinstance(error.code, int) else None,
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

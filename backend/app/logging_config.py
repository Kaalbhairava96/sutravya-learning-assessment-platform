"""Small structured JSON logger that emits only explicitly selected fields."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


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


class SafeJsonFormatter(logging.Formatter):
    """Exclude arbitrary messages, exception details, and request payloads."""

    def format(self, record: logging.LogRecord) -> str:
        safe_events = {
            "request_complete", "request_failed", "email_delivery_failed", "rate_limit_rejected",
            "email_runtime_config_check",
        }
        event = record.msg if type(record.msg) is str and record.msg in safe_events else "application_event"
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": event,
        }
        for key in (
            "request_id", "method", "status_code", "duration_ms", "scope", "purpose",
            "failure_kind", "provider_status_code", "provider_error_name", "provider_error_kind",
            "resend_key_present", "resend_key_fingerprint", "resend_sender_expected_match",
            "resend_sender_domain_match",
        ):
            value = getattr(record, key, None)
            if value is not None:
                if key == "failure_kind" and (not isinstance(value, str) or value not in {
                    "configuration_missing", "provider_http_error", "network_or_timeout", "unexpected_error"
                }):
                    continue
                if key == "provider_status_code" and (
                    type(value) is not int or not 100 <= value <= 599
                ):
                    continue
                if key == "provider_error_name" and (
                    not isinstance(value, str) or value not in _PROVIDER_ERROR_NAMES
                ):
                    continue
                if key == "provider_error_kind" and (
                    not isinstance(value, str) or value not in _PROVIDER_ERROR_KINDS
                ):
                    continue
                if key in {
                    "resend_key_present", "resend_sender_expected_match", "resend_sender_domain_match"
                } and type(value) is not bool:
                    continue
                if key == "resend_key_fingerprint" and not (
                    value == "missing"
                    or (isinstance(value, str) and len(value) == 12 and all(ch in "0123456789abcdef" for ch in value))
                ):
                    continue
                payload[key] = value
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def configure_logging(level: str) -> logging.Logger:
    logger = logging.getLogger("sutravya.api")
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(SafeJsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger

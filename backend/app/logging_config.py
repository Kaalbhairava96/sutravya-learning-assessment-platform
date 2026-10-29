"""Small structured JSON logger that emits only explicitly selected fields."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


class SafeJsonFormatter(logging.Formatter):
    """Exclude arbitrary messages, exception details, and request payloads."""

    def format(self, record: logging.LogRecord) -> str:
        safe_events = {
            "request_complete", "request_failed", "email_delivery_failed", "rate_limit_rejected"
        }
        event = record.msg if type(record.msg) is str and record.msg in safe_events else "application_event"
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": event,
        }
        for key in ("request_id", "method", "status_code", "duration_ms", "scope", "purpose"):
            value = getattr(record, key, None)
            if value is not None:
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

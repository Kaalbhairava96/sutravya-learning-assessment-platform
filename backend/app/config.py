"""Environment-based configuration with safe validation and no secret logging."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    """Raised when required application configuration is absent or invalid."""


# Milestone 3A permits test-mode connections only to the named, disposable
# PostgreSQL database exposed by the local rehearsal container.
TEST_DATABASE_NAME = "sutravya_m3_test"
TEST_DATABASE_HOST = "127.0.0.1"
TEST_DATABASE_PORT = 55432


def _validate_database_url(app_env: str, database_url: str) -> None:
    if not database_url:
        raise ConfigurationError("DATABASE_URL is required. Set it in the environment or local .env file.")
    try:
        parsed = urlsplit(database_url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ConfigurationError("DATABASE_URL must be a valid PostgreSQL connection URL.") from exc

    if parsed.scheme != "postgresql+psycopg" or not hostname or not parsed.path.strip("/"):
        raise ConfigurationError("DATABASE_URL must use postgresql+psycopg and include a host and database name.")

    if app_env == "test":
        if (
            hostname != TEST_DATABASE_HOST
            or port != TEST_DATABASE_PORT
            or parsed.path != f"/{TEST_DATABASE_NAME}"
            or "?" in database_url
            or "#" in database_url
        ):
            raise ConfigurationError(
                "Test mode requires the approved local disposable database "
                f"{TEST_DATABASE_NAME} on {TEST_DATABASE_HOST}:{TEST_DATABASE_PORT}, without URL options."
            )


def _read_dotenv(path: Path) -> dict[str, str]:
    """Read a small KEY=VALUE .env file without adding a dotenv dependency."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigurationError(f"Invalid .env syntax on line {line_number}.")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not key.replace("_", "").isalnum():
            raise ConfigurationError(f"Invalid .env key on line {line_number}.")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


@dataclass(frozen=True)
class Settings:
    app_env: str
    log_level: str
    database_url: str = field(repr=False)
    otp_expiry_seconds: int = 300
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 60
    otp_hmac_pepper: str | None = field(default=None, repr=False)
    resend_api_key: str | None = field(default=None, repr=False)
    resend_from_email: str | None = None
    cors_origins: tuple[str, ...] = ()
    internal_test_mode: bool = False
    internal_test_access_code: str | None = field(default=None, repr=False)
    registration_export_key: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.app_env not in {"development", "test", "production"}:
            raise ConfigurationError("APP_ENV must be development, test, or production.")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError("LOG_LEVEL must be a standard logging level.")
        _validate_database_url(self.app_env, self.database_url)
        if type(self.internal_test_mode) is not bool:
            raise ConfigurationError("INTERNAL_TEST_MODE must be true or false.")
        if self.internal_test_mode and not self.internal_test_access_code:
            raise ConfigurationError("INTERNAL_TEST_ACCESS_CODE is required when internal test mode is enabled.")
        if self.internal_test_access_code is not None and len(self.internal_test_access_code) < 16:
            raise ConfigurationError("INTERNAL_TEST_ACCESS_CODE must contain at least 16 characters when configured.")
        if self.registration_export_key is not None and len(self.registration_export_key) < 32:
            raise ConfigurationError("REGISTRATION_EXPORT_KEY must contain at least 32 characters when configured.")
        for name, value in (
            ("OTP_EXPIRY_SECONDS", self.otp_expiry_seconds),
            ("OTP_MAX_ATTEMPTS", self.otp_max_attempts),
            ("OTP_RESEND_COOLDOWN_SECONDS", self.otp_resend_cooldown_seconds),
        ):
            if type(value) is not int or value <= 0:
                raise ConfigurationError(f"{name} must be a positive integer.")
        if self.otp_hmac_pepper is not None and len(self.otp_hmac_pepper.encode("utf-8")) < 32:
            raise ConfigurationError("OTP_HMAC_PEPPER must contain at least 32 UTF-8 bytes when configured.")
        for origin in self.cors_origins:
            parsed_origin = urlsplit(origin)
            if parsed_origin.scheme not in {"http", "https"} or not parsed_origin.netloc or parsed_origin.path:
                raise ConfigurationError("CORS_ORIGINS must contain exact origins without paths.")

    def require_otp_hmac_pepper(self) -> str:
        """Return the configured pepper or fail closed for digest operations."""
        if self.otp_hmac_pepper is None:
            raise ConfigurationError("OTP_HMAC_PEPPER is required for OTP digest operations.")
        return self.otp_hmac_pepper

    @staticmethod
    def _positive_int(values: dict[str, str], name: str, default: int) -> int:
        raw_value = values.get(name, str(default)).strip()
        try:
            parsed = int(raw_value)
        except ValueError as exc:
            raise ConfigurationError(f"{name} must be a positive integer.") from exc
        if parsed <= 0:
            raise ConfigurationError(f"{name} must be a positive integer.")
        return parsed

    @classmethod
    def from_env(
        cls,
        environ: dict[str, str] | None = None,
        dotenv_path: Path | None = None,
    ) -> "Settings":
        """Load settings, preferring process environment over the local .env file."""
        values = _read_dotenv(dotenv_path or Path.cwd() / ".env")
        values.update(dict(os.environ if environ is None else environ))

        app_env = values.get("APP_ENV", "development").strip().lower()
        if app_env not in {"development", "test", "production"}:
            raise ConfigurationError("APP_ENV must be development, test, or production.")

        log_level = values.get("LOG_LEVEL", "INFO").strip().upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError("LOG_LEVEL must be a standard logging level.")

        database_url = values.get("DATABASE_URL", "").strip()
        pepper_value = values.get("OTP_HMAC_PEPPER", "")
        pepper = pepper_value if pepper_value else None
        internal_mode_raw = values.get("INTERNAL_TEST_MODE", "false").strip().lower()
        if internal_mode_raw not in {"true", "false"}:
            raise ConfigurationError("INTERNAL_TEST_MODE must be true or false.")
        return cls(
            app_env=app_env,
            log_level=log_level,
            database_url=database_url,
            otp_expiry_seconds=cls._positive_int(values, "OTP_EXPIRY_SECONDS", 300),
            otp_max_attempts=cls._positive_int(values, "OTP_MAX_ATTEMPTS", 5),
            otp_resend_cooldown_seconds=cls._positive_int(values, "OTP_RESEND_COOLDOWN_SECONDS", 60),
            otp_hmac_pepper=pepper,
            resend_api_key=values.get("RESEND_API_KEY") or None,
            resend_from_email=values.get("RESEND_FROM_EMAIL") or None,
            cors_origins=tuple(
                origin.strip().rstrip("/")
                for origin in values.get("CORS_ORIGINS", "").split(",")
                if origin.strip()
            ),
            internal_test_mode=internal_mode_raw == "true",
            internal_test_access_code=values.get("INTERNAL_TEST_ACCESS_CODE") or None,
            registration_export_key=values.get("REGISTRATION_EXPORT_KEY") or None,
        )

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

    def __post_init__(self) -> None:
        if self.app_env not in {"development", "test", "production"}:
            raise ConfigurationError("APP_ENV must be development, test, or production.")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError("LOG_LEVEL must be a standard logging level.")
        _validate_database_url(self.app_env, self.database_url)

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
        return cls(app_env=app_env, log_level=log_level, database_url=database_url)

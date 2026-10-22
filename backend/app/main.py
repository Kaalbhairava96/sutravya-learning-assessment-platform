"""FastAPI entry point for the SUTRAVYA assessment backend foundation."""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request

from app.config import Settings
from app.logging_config import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the API after validating required configuration; never connects on startup."""
    active_settings = settings or Settings.from_env()
    logger = configure_logging(active_settings.log_level)
    docs_enabled = active_settings.app_env != "production"
    application = FastAPI(
        title="SUTRAVYA Learning & Assessment API",
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    @application.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = str(uuid.uuid4())
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            logger.error(
                "request_failed",
                extra={"request_id": request_id, "method": request.method, "status_code": status_code},
            )
            raise
        finally:
            logger.info(
                "request_complete",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )

    @application.get("/health", tags=["operations"])
    async def health() -> dict[str, str]:
        """Liveness only: deliberately does not connect to or reveal database state."""
        return {"status": "ok"}

    return application


# Missing or invalid configuration fails the server process before it accepts traffic.
# DATABASE_URL is validated here but no database connection is opened by this milestone.
app = create_app()

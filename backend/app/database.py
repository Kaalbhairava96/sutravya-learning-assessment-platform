"""Validated SQLAlchemy engine construction for application and migrations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.config import Settings


def create_database_engine(
    settings: Settings | None = None,
    **engine_options: Any,
) -> Engine:
    """Construct an engine only after validated settings are available.

    In test mode Settings enforces the single approved local disposable database
    before SQLAlchemy receives the URL. Creating an engine does not connect;
    callers explicitly open a connection afterward.
    """
    active_settings = settings or Settings.from_env()
    return create_engine(active_settings.database_url, **engine_options)

"""
Location: 24fps/backend/app/storage/db.py

SQLAlchemy engine, session factory, and declarative base for the
forensic case/evidence metadata database.

Per Master Specification Section 17, this targets SQLite for the local
forensic workstation and is designed to swap to PostgreSQL at scale via
`DATABASE_URL` alone — no application code outside this module should
depend on which backend is active. Note per Section 17: evidence media
itself must NEVER be stored as a database blob; only paths/URIs/asset
metadata belong here.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base class for all forensic ORM models.

    Every SQLAlchemy model in `app/models/` must inherit from this base
    so that Alembic autogeneration and metadata creation operate against
    a single, unified schema.
    """


def _build_engine() -> Engine:
    """Construct the SQLAlchemy engine from application settings.

    SQLite requires `check_same_thread=False` when accessed from
    FastAPI's threaded request handling; this flag is a no-op for other
    backends such as PostgreSQL and is therefore only applied when the
    configured URL targets SQLite.

    Returns:
        A configured SQLAlchemy `Engine` instance.
    """
    settings = get_settings()
    connect_args: dict[str, Any] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(
        settings.database_url,
        connect_args=connect_args,
        future=True,
    )


engine: Engine = _build_engine()

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a scoped database session.

    The session is always closed after the request completes, including
    on unhandled exceptions, to avoid leaking connections under sustained
    forensic job load.

    Yields:
        An active SQLAlchemy `Session` bound to the configured engine.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db_schema() -> None:
    """Create all tables known to `Base.metadata` if they do not exist.

    This is a convenience path for local development and test
    environments only. In staging/production, schema changes must flow
    exclusively through Alembic migrations so that schema history
    remains auditable, per Master Specification Section 51, rule 12
    ("Schema versions must be tracked.").
    """
    Base.metadata.create_all(bind=engine)

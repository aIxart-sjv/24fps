"""
Application bootstrap helpers for packaged/frozen execution (Phase 20,
"Windows Packaging + End-to-End Validation").

Two problems a packaged `.exe` has that a `uvicorn app.main:app` CLI
invocation from the repository root never does:

1. The current working directory is not guaranteed to be the backend
   project root (task Phase 20 scope section 8: "Do not assume working
   directory is repository root") -- a Windows shortcut, a scheduled
   task, or a double-click from a different folder can all set CWD to
   something else. `resolve_application_root`/`resolve_migrations_
   directory` locate bundled files (`migrations/`) relative to the
   running process itself, not CWD.
2. Nothing today runs Alembic migrations except a developer manually
   invoking the `alembic` CLI. A clean installation must be able to
   initialize/update its database without the investigator running any
   Python/Alembic commands (Master Specification Section 65: "the
   investigator does not manually run Python/npm commands"; task Phase
   20 scope section 7). `run_database_migrations` does this
   programmatically via Alembic's own Python API
   (`alembic.command.upgrade`), never `Base.metadata.create_all()` (task
   Phase 20 scope section 7 explicitly forbids that shortcut) and never
   touches a historical migration file.

Both functions are plain, side-effect-free (except the migration run
itself) and safe to call from `app.main.lifespan` or from the packaged
entry point (`run.py`) -- they do not import FastAPI/uvicorn themselves,
keeping this module usable in isolation (e.g. from a future standalone
"run migrations only" CLI invocation).
"""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import get_settings
from app.logging.forensic_logger import get_logger

logger = get_logger(__name__, log_filename="application.log")

__all__ = [
    "is_frozen",
    "resolve_application_root",
    "resolve_migrations_directory",
    "run_database_migrations",
]


def is_frozen() -> bool:
    """Whether this process is running from a PyInstaller-frozen bundle.

    PyInstaller sets `sys.frozen = True` on the bootstrapped
    interpreter; this is the documented, standard way to detect it
    (there is no other reliable cross-platform signal).
    """
    return bool(getattr(sys, "frozen", False))


def resolve_application_root() -> Path:
    """Resolve the directory this application's own bundled files
    (`migrations/`, model weights, etc.) live under.

    Returns:
        - When frozen (PyInstaller): `sys._MEIPASS` if set (PyInstaller
          onefile mode extracts bundled data there at every launch), else
          the running executable's own directory (onedir mode, where
          `--add-data` targets land next to the `.exe`).
        - Otherwise (normal `python`/development execution): the backend
          project root (this file lives at `<root>/app/bootstrap.py`).
    """
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resolve_migrations_directory() -> Path:
    """Resolve the bundled/on-disk `migrations/` directory."""
    return resolve_application_root() / "migrations"


def run_database_migrations() -> None:
    """Upgrade the configured database to the latest Alembic revision.

    Builds an `alembic.config.Config` entirely in Python (no dependency
    on parsing `alembic.ini` from a particular working directory) and
    calls `alembic.command.upgrade(config, "head")` -- the same
    operation `alembic upgrade head` performs on the CLI, against the
    exact same `migrations/` scripts, never a schema shortcut.
    `migrations/env.py` itself already reads the database URL from
    `app.config.get_settings()` (not from this `Config` object), so the
    two stay a single source of truth.

    Raises:
        RuntimeError: If the bundled/on-disk `migrations/` directory
            cannot be found -- a packaging defect (a distribution
            missing this directory), reported clearly rather than
            surfacing as an obscure Alembic internal error.
        Exception: Any exception Alembic itself raises for a genuine
            migration failure (e.g. an unreadable database file, a
            corrupt revision history) propagates unchanged -- this
            function never swallows a migration error, since silently
            continuing with a stale/partial schema would be worse than
            failing startup.
    """
    settings = get_settings()
    migrations_dir = resolve_migrations_directory()
    if not migrations_dir.is_dir():
        raise RuntimeError(
            f"migrations directory not found at {migrations_dir!s} -- this "
            "distribution is missing its migrations/ folder"
        )

    config = Config()
    config.set_main_option("script_location", str(migrations_dir))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    logger.info(
        "Running database migrations",
        extra={
            "forensic_context": {
                "migrations_dir": str(migrations_dir),
                "database_url_scheme": settings.database_url.split(":", maxsplit=1)[0],
            }
        },
    )
    command.upgrade(config, "head")
    logger.info("Database migrations complete")

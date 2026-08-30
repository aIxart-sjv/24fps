"""
Location: 24fps/backend/run.py

Standalone entry point for the packaged/frozen 24FPS backend
(Phase 20, "Windows Packaging + End-to-End Validation").

Development workflows keep using `uvicorn app.main:app --reload` (or any
equivalent `uvicorn` CLI invocation) exactly as before -- this script
does not replace that. It exists because PyInstaller needs a single,
real, importable Python script with top-level executable code to build
into a standalone executable; an ASGI application object alone
(`app.main:app`) is not something PyInstaller can turn into a process by
itself.

Deliberately minimal: no business logic lives here. It only resolves the
importable package root, builds the FastAPI app, and calls
`uvicorn.run(...)` with the configured host/port. Every actual startup
behavior (filesystem-root creation, database migrations, DB connectivity
check, route registration) lives in `app.main.lifespan`/`app.main.
create_app`, completely unchanged regardless of whether the app is
launched via this script, via the `uvicorn` CLI, or under a test client.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_importable() -> None:
    """Make sure this file's own directory (the backend project root, or
    the PyInstaller bundle root when frozen) is on `sys.path`,
    independent of the process's current working directory (task Phase
    20 scope section 8: "Do not assume working directory is repository
    root"). PyInstaller already does this for a frozen build, but the
    check is cheap and keeps this script correct when run directly with
    plain `python run.py` from an arbitrary CWD too.
    """
    root = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def main() -> None:
    _ensure_importable()

    import uvicorn

    from app.config import get_settings
    from app.main import create_app

    settings = get_settings()
    application = create_app()

    # `log_config=None`: uvicorn's own default logging setup is skipped
    # so the single forensic logger (`app.logging.forensic_logger`,
    # already wired into `app.main`'s lifespan and every route) remains
    # the one place log formatting/encoding/destination is decided --
    # never a second, competing logging configuration.
    uvicorn.run(application, host=settings.host, port=settings.port, log_config=None)


if __name__ == "__main__":
    main()

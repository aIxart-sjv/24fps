"""
Location: 24fps/backend/app/main.py

FastAPI application entrypoint for the 24FPS Multi-Vendor DVR/NVR
Forensic Analysis Platform backend.

Wires together configuration, database connectivity, structured logging,
and the API router tree into a single ASGI application. This module
intentionally contains no forensic business logic — that responsibility
belongs to `app/core`, `app/adapters`, and the individual route modules
under `app/api/routes`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import acquisition as acquisition_routes
from app.api.routes import ai as ai_routes
from app.api.routes import artifacts as artifacts_routes
from app.api.routes import audit as audit_routes
from app.api.routes import auth as auth_routes
from app.api.routes import blockchain as blockchain_routes
from app.api.routes import cases as cases_routes
from app.api.routes import correlation as correlation_routes
from app.api.routes import custody as custody_routes
from app.api.routes import devices as devices_routes
from app.api.routes import evidence as evidence_routes
from app.api.routes import findings as findings_routes
from app.api.routes import integrity as integrity_routes
from app.api.routes import jobs as jobs_routes
from app.api.routes import notifications as notifications_routes
from app.api.routes import processing as processing_routes
from app.api.routes import recordings as recordings_routes
from app.api.routes import recovery as recovery_routes
from app.api.routes import reports as reports_routes
from app.api.routes import search as search_routes
from app.api.routes import system as system_routes
from app.api.routes import timeline as timeline_routes
from app.api.routes import timestamps as timestamps_routes
from app.api.routes import admin_access as admin_access_routes
from app.api.routes import users as users_routes
from app.api.routes import validation as validation_routes
from app.bootstrap import run_database_migrations
from app.config import get_settings
from app.logging.forensic_logger import get_logger
from app.storage.db import engine

logger = get_logger(__name__, log_filename="application.log")

API_V1_PREFIX: str = "/api/v1"

# Local development origins for the React/Vite frontend and the Tauri
# desktop shell, per Master Specification Section 64 ("Localhost API").
# Phase 23: the supplied frontend's `vite --port=3000` replaced the
# previous frontend's default 5173 -- both are kept so either dev server
# configuration works without editing this file again.
_LOCAL_DEV_ORIGINS: list[str] = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "tauri://localhost",
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle events.

    On startup this ensures all configured filesystem roots exist, brings
    the database schema to the latest Alembic revision (Phase 20: a clean
    installation -- including a packaged `.exe` an investigator never
    runs `alembic` commands against directly -- must be able to
    initialize/update its own database; `app.bootstrap.
    run_database_migrations` never uses `Base.metadata.create_all()` as a
    shortcut and never touches a historical migration file), and verifies
    the database engine can open a connection, failing fast rather than
    allowing a partially functional backend to accept forensic work. On
    shutdown, the database connection pool is disposed.

    Args:
        app: The FastAPI application instance being started.

    Yields:
        Control back to FastAPI for the duration it serves requests.

    Raises:
        RuntimeError: If migrations fail or the database connection
            cannot be established during the startup verification step.
    """
    settings = get_settings()
    settings.ensure_directories()
    logger.info(
        "Backend starting up",
        extra={
            "forensic_context": {
                "app_env": settings.app_env.value,
                "app_version": settings.app_version,
            }
        },
    )

    try:
        run_database_migrations()
    except Exception as exc:
        logger.error(
            "Database migration failed during startup",
            extra={"forensic_context": {"error": str(exc)}},
        )
        raise RuntimeError("Backend failed to apply database migrations at startup.") from exc

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error(
            "Database connectivity check failed during startup",
            extra={"forensic_context": {"error": str(exc)}},
        )
        raise RuntimeError("Backend failed to establish a database connection at startup.") from exc

    logger.info("Backend startup checks passed")
    yield

    engine.dispose()
    logger.info("Backend shutdown complete")


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application instance.

    Uses an explicit factory function (rather than a bare module-level
    `app = FastAPI()`) so the application remains importable and
    constructible from test suites without triggering side effects at
    import time.

    Returns:
        A fully configured `FastAPI` application instance.
    """
    settings = get_settings()

    application = FastAPI(
        title="24FPS Multi-Vendor DVR/NVR Forensic Analysis Platform",
        description=(
            "Backend forensic processing engine for SIH26150: standardized "
            "acquisition, recovery, and analysis of multi-vendor "
            "surveillance evidence."
        ),
        version=settings.app_version,
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=_LOCAL_DEV_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(system_routes.router, prefix=API_V1_PREFIX, tags=["system"])
    application.include_router(
        cases_routes.router, prefix=API_V1_PREFIX, tags=["cases", "evidence"]
    )
    application.include_router(integrity_routes.router, prefix=API_V1_PREFIX, tags=["integrity"])
    application.include_router(devices_routes.router, prefix=API_V1_PREFIX, tags=["identification"])
    application.include_router(recordings_routes.router, prefix=API_V1_PREFIX, tags=["recordings"])
    application.include_router(recovery_routes.router, prefix=API_V1_PREFIX, tags=["recovery"])
    application.include_router(timestamps_routes.router, prefix=API_V1_PREFIX, tags=["timestamps"])
    application.include_router(
        correlation_routes.router, prefix=API_V1_PREFIX, tags=["correlation"]
    )
    application.include_router(jobs_routes.router, prefix=API_V1_PREFIX, tags=["jobs"])
    application.include_router(ai_routes.router, prefix=API_V1_PREFIX, tags=["ai"])
    application.include_router(validation_routes.router, prefix=API_V1_PREFIX, tags=["validation"])
    application.include_router(audit_routes.router, prefix=API_V1_PREFIX, tags=["audit"])
    application.include_router(blockchain_routes.router, prefix=API_V1_PREFIX, tags=["blockchain"])
    application.include_router(reports_routes.router, prefix=API_V1_PREFIX, tags=["reports"])
    application.include_router(auth_routes.router, prefix=API_V1_PREFIX, tags=["auth"])
    application.include_router(custody_routes.router, prefix=API_V1_PREFIX, tags=["custody"])
    application.include_router(processing_routes.router, prefix=API_V1_PREFIX, tags=["processing"])
    application.include_router(findings_routes.router, prefix=API_V1_PREFIX, tags=["findings"])
    application.include_router(
        notifications_routes.router, prefix=API_V1_PREFIX, tags=["notifications"]
    )
    application.include_router(timeline_routes.router, prefix=API_V1_PREFIX, tags=["timeline"])
    application.include_router(artifacts_routes.router, prefix=API_V1_PREFIX, tags=["artifacts"])
    application.include_router(users_routes.router, prefix=API_V1_PREFIX, tags=["users"])
    application.include_router(
        admin_access_routes.router, prefix=API_V1_PREFIX, tags=["admin-access"]
    )
    application.include_router(
        acquisition_routes.router, prefix=API_V1_PREFIX, tags=["acquisition"]
    )
    application.include_router(evidence_routes.router, prefix=API_V1_PREFIX, tags=["evidence"])
    application.include_router(search_routes.router, prefix=API_V1_PREFIX, tags=["search"])

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Return a structured error envelope for any unhandled exception.

        Prevents raw stack traces or framework default error pages from
        leaking implementation details to API clients, while still
        logging the full exception server-side, per Master Specification
        Section 54 ("Error Handling").

        Args:
            request: The incoming request that triggered the exception.
            exc: The unhandled exception instance.

        Returns:
            A JSON response with HTTP 500 status and the stable error
            envelope shape defined in Master Specification Section 85.
        """
        logger.error(
            "Unhandled exception during request processing",
            extra={
                "forensic_context": {
                    "path": str(request.url.path),
                    "method": request.method,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected server error occurred.",
                }
            },
        )

    return application


app: FastAPI = create_app()

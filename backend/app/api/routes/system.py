"""
Location: 24fps/backend/app/api/routes/system.py

System-level, vendor-agnostic endpoints: process health, backend
build/version information, and high-level subsystem scaffolding status.
These deliberately avoid touching case, evidence, or vendor-adapter
logic, per Master Specification Section 46 ("HEALTH" / "SYSTEM INFO").
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config import get_settings
from app.storage.db import engine

router = APIRouter()


class HealthResponse(BaseModel):
    """Response schema for the liveness/health endpoint."""

    status: str = Field(description="Overall backend health status.")
    timestamp: str = Field(description="UTC timestamp of the health check.")
    database_connected: bool = Field(
        description="Whether the metadata database is currently reachable."
    )


class SystemInfoResponse(BaseModel):
    """Response schema describing static backend build information."""

    app_version: str = Field(description="Semantic version of the backend.")
    app_env: str = Field(description="Active deployment environment.")
    database_url_scheme: str = Field(
        description=(
            "Database driver scheme in use (e.g. 'sqlite', 'postgresql'), "
            "exposed without credentials or full connection details."
        )
    )


class SubsystemCapability(BaseModel):
    """Describes the implementation status of a single backend subsystem."""

    name: str = Field(description="Human-readable subsystem name.")
    implemented: bool = Field(description="Whether this subsystem currently has working logic.")
    notes: str = Field(description="Short note on current implementation status.")


class SystemCapabilitiesResponse(BaseModel):
    """Response schema listing high-level backend subsystem status.

    Distinct from the future vendor `capability_registry` (Master
    Specification Section 56), which will report per-adapter
    parsing/recovery capability at vendor/model/firmware granularity
    once adapters are implemented. This endpoint only reports
    backend-wide scaffolding status.
    """

    subsystems: list[SubsystemCapability]


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Report basic liveness and database connectivity status.

    Returns:
        A `HealthResponse` indicating whether the backend process is
        running and whether the configured metadata database is
        currently reachable.
    """
    database_connected = True
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - health check must never raise
        database_connected = False

    return HealthResponse(
        status="ok" if database_connected else "degraded",
        timestamp=datetime.now(UTC).isoformat(),
        database_connected=database_connected,
    )


@router.get("/system/info", response_model=SystemInfoResponse)
def get_system_info() -> SystemInfoResponse:
    """Report static backend build and environment information.

    Returns:
        A `SystemInfoResponse` describing the running backend version,
        deployment environment, and database driver family.
    """
    settings = get_settings()
    scheme = settings.database_url.split(":", maxsplit=1)[0]
    return SystemInfoResponse(
        app_version=settings.app_version,
        app_env=settings.app_env.value,
        database_url_scheme=scheme,
    )


@router.get("/system/capabilities", response_model=SystemCapabilitiesResponse)
def get_system_capabilities() -> SystemCapabilitiesResponse:
    """Report which high-level backend subsystems are currently wired up.

    Reflects development-order progress (Master Specification Section
    89) rather than forensic capability, so the frontend/desktop shell
    can detect which API surfaces are safe to call during incremental
    development.

    Returns:
        A `SystemCapabilitiesResponse` enumerating known backend
        subsystems and their current implementation status.
    """
    subsystems = [
        SubsystemCapability(
            name="configuration",
            implemented=True,
            notes="Environment-driven settings via pydantic-settings.",
        ),
        SubsystemCapability(
            name="database",
            implemented=True,
            notes="SQLAlchemy engine/session foundation with Alembic migrations.",
        ),
        SubsystemCapability(
            name="case_management",
            implemented=False,
            notes="Domain models and routes not yet implemented.",
        ),
        SubsystemCapability(
            name="evidence_management",
            implemented=False,
            notes="Domain models and routes not yet implemented.",
        ),
        SubsystemCapability(
            name="vendor_adapters",
            implemented=False,
            notes="Adapter directory scaffolding only; no parsers implemented.",
        ),
        SubsystemCapability(
            name="acquisition",
            implemented=False,
            notes="StorageAccess interface defined; no acquisition logic yet.",
        ),
        SubsystemCapability(
            name="integrity_hashing",
            implemented=True,
            notes="SHA-256 + MD5 evidence hashing, storage, and verification.",
        ),
        SubsystemCapability(
            name="recovery",
            implemented=False,
            notes="Not yet implemented.",
        ),
        SubsystemCapability(
            name="ai_analytics",
            implemented=False,
            notes="Not yet implemented.",
        ),
        SubsystemCapability(
            name="reporting",
            implemented=False,
            notes="Not yet implemented.",
        ),
    ]
    return SystemCapabilitiesResponse(subsystems=subsystems)

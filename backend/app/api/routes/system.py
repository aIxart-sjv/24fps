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
    89) rather than per-vendor forensic capability, so the frontend/
    desktop shell can detect which API surfaces are safe to call.
    Distinct from `AdapterRegistry.support_matrix()` (Phase 19), which
    reports per-vendor/model/firmware support level -- this endpoint only
    reports whether a backend subsystem exists at all.

    Kept in sync by hand at each phase boundary (Phase 20: corrected
    against actual Phase 1-19 status -- this list had silently drifted
    stale, still reporting every subsystem through "reporting" as
    `implemented=False` despite Phases 4-18 having implemented them; an
    inaccurate status/capability endpoint is exactly the kind of
    "unsupported capability falsely advertised" (task Phase 20 scope
    section 35) this phase must not leave in place, even though nothing
    about the underlying subsystems themselves changed).

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
            implemented=True,
            notes="Case CRUD (Phase 2/4).",
        ),
        SubsystemCapability(
            name="evidence_management",
            implemented=True,
            notes="Evidence registration, artifacts, native export (Phase 4).",
        ),
        SubsystemCapability(
            name="vendor_adapters",
            implemented=True,
            notes=(
                "DVRAdapter/AdapterRegistry framework (Phase 7); CP Plus validated "
                "against real evidence (Phase 8, LEVEL_4); Dahua/Hikvision detection-only "
                "(Phase 19, LEVEL_1); Honeywell/Uniview/TP-Link/Godrej/Matrix research-only "
                "(Phase 19, LEVEL_0) -- see GET /api/v1/cases/{case_id}/audit for per-case "
                "history; no dedicated adapter-listing route exists."
            ),
        ),
        SubsystemCapability(
            name="acquisition",
            implemented=True,
            notes=(
                "RAW/DD + native export + E01 (pyewf, optional) on Linux; "
                "WindowsStorageAccess remains an interface stub -- native Windows physical-"
                "drive acquisition is NOT implemented (see Phase 20 final report)."
            ),
        ),
        SubsystemCapability(
            name="integrity_hashing",
            implemented=True,
            notes="SHA-256 + MD5 evidence hashing, storage, and verification.",
        ),
        SubsystemCapability(
            name="recording_extraction",
            implemented=True,
            notes="CP Plus recording enumeration + FFmpeg-based extraction (Phase 9).",
        ),
        SubsystemCapability(
            name="recovery",
            implemented=True,
            notes="Layered recovery engine (Phase 10); validated only for CP Plus.",
        ),
        SubsystemCapability(
            name="timeline_correlation",
            implemented=True,
            notes="Timestamp normalization, canonical timeline, cross-camera correlation "
            "(Phase 11/12).",
        ),
        SubsystemCapability(
            name="ai_analytics",
            implemented=True,
            notes="Object/face/motion detection + tracking (Phase 13); model weights "
            "download on first use into AI_MODEL_ROOT.",
        ),
        SubsystemCapability(
            name="validation",
            implemented=True,
            notes="Ground-truth metric engine (Phase 14).",
        ),
        SubsystemCapability(
            name="provenance_audit",
            implemented=True,
            notes="Processing history + hash-linked audit chain (Phase 15/16).",
        ),
        SubsystemCapability(
            name="blockchain_anchoring",
            implemented=True,
            notes="Local/test provider only by default (BLOCKCHAIN_PROVIDER=none "
            "disables it); no real network integration exists (Phase 17).",
        ),
        SubsystemCapability(
            name="reporting",
            implemented=True,
            notes="Standardized JSON + PDF report generation (Phase 18).",
        ),
        SubsystemCapability(
            name="physical_custody_auth",
            implemented=True,
            notes="User accounts/sessions + QR-based physical evidence custody (Phase 21).",
        ),
        SubsystemCapability(
            name="automatic_processing_findings",
            implemented=True,
            notes=(
                "Controlled automatic case-processing orchestration, structured findings, "
                "and officer notifications (Phase 22); reuses the Phase 13 job system and "
                "Phase 15/16 provenance/audit chain rather than a second mechanism."
            ),
        ),
    ]
    return SystemCapabilitiesResponse(subsystems=subsystems)

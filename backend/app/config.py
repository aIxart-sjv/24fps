"""
Location: 24fps/backend/app/config.py

Central configuration module for the 24FPS Multi-Vendor DVR/NVR Forensic
Analysis Platform backend.

This module defines the canonical runtime configuration object used
throughout the application. All configuration is environment-aware and
loaded via pydantic-settings, which reads from process environment
variables and an optional `.env` file. No evidence location, credential,
or deployment-specific value is ever hardcoded here (Master
Specification Section 67).
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(str, Enum):
    """Enumerates the supported deployment environments for the backend."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Enumerates the supported application log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """Canonical application settings for the forensic backend.

    Every field maps directly onto an environment variable of the same
    name (case-insensitive). Values are validated at process startup so
    misconfiguration fails fast rather than surfacing mid-acquisition.

    Attributes:
        app_env: Deployment environment identifier.
        app_version: Semantic version string of the running backend build.
        database_url: SQLAlchemy connection URL for the case/evidence
            metadata database. Defaults to a local SQLite file suitable
            for a single-investigator forensic workstation, per Master
            Specification Section 17 ("Database").
        evidence_root: Filesystem root under which preserved, read-only
            source evidence (acquired images, manifests) is stored.
        artifact_root: Filesystem root for derived artifacts (recovered
            recordings, normalized metadata, AI outputs).
        report_root: Filesystem root for generated JSON/PDF reports.
        temp_root: Filesystem root for transient working files that may
            be safely deleted between runs.
        log_root: Filesystem root for technical and forensic log files.
        ffmpeg_path: Absolute or PATH-resolvable location of the FFmpeg
            executable used for media demuxing/decoding.
        ffprobe_path: Absolute or PATH-resolvable location of the FFprobe
            executable used for media inspection (codec/resolution/fps/
            duration), normally installed alongside FFmpeg.
        libewf_path: Optional path override for libewf tooling used to
            read/write EWF/E01 forensic images.
        ai_model_root: Filesystem root where AI model weights are cached.
        blockchain_provider: Identifier of the blockchain anchoring
            provider implementation to use (e.g. "none", "local_testnet").
        blockchain_network: Network identifier for the configured
            blockchain provider (e.g. "sepolia", "local").
        max_workers: Maximum number of worker processes/threads the
            backend may spawn for CPU-heavy forensic operations.
        log_level: Minimum severity level emitted by the application
            logger.
        host: Interface the packaged/standalone entry point binds
            uvicorn to. Loopback-only by default.
        port: TCP port the packaged/standalone entry point binds
            uvicorn to.
        auth_session_ttl_minutes: Minutes an authenticated login session
            remains valid before re-authentication is required.
        custody_token_ttl_minutes: Minutes a QR physical-custody handoff
            token remains valid before it expires unaccepted.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: AppEnvironment = Field(default=AppEnvironment.DEVELOPMENT)
    app_version: str = Field(default="0.1.0")

    database_url: str = Field(
        default="sqlite:///./data/case_metadata.db",
        description="SQLAlchemy connection URL for case/evidence metadata.",
    )

    evidence_root: Path = Field(default=Path("./data/evidence"))
    artifact_root: Path = Field(default=Path("./data/artifacts"))
    report_root: Path = Field(default=Path("./data/reports"))
    temp_root: Path = Field(default=Path("./data/temp"))
    log_root: Path = Field(default=Path("./data/logs"))

    ffmpeg_path: str = Field(default="ffmpeg")
    ffprobe_path: str = Field(default="ffprobe")
    libewf_path: str | None = Field(default=None)
    ai_model_root: Path = Field(default=Path("./data/models"))

    blockchain_provider: str = Field(default="none")
    blockchain_network: str = Field(default="none")

    max_workers: int = Field(default=4, ge=1, le=64)
    log_level: LogLevel = Field(default=LogLevel.INFO)

    #: Phase 20: the packaged entry point (`run.py`) needs an explicit
    #: bind host/port -- previously only ever set ad hoc on the `uvicorn`
    #: CLI in development. Defaults match uvicorn's own defaults and
    #: Master Specification Section 64's localhost-only API design; never
    #: `0.0.0.0` by default (a single-investigator local forensic
    #: workstation tool has no reason to bind beyond loopback unless an
    #: operator explicitly opts in).
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000, ge=1, le=65535)

    #: Phase 21: how long an authenticated login session (`UserSession`)
    #: remains valid before it must be re-issued. Deliberately short --
    #: "short-lived authenticated session" is an explicit task
    #: requirement, not a general-purpose long-lived API key.
    auth_session_ttl_minutes: int = Field(default=60, ge=1, le=1440)

    #: Phase 21: how long a QR custody-handoff token remains valid before
    #: it expires unaccepted. Deliberately short -- a token left valid
    #: for days would widen the window for a lost/stolen printout to be
    #: scanned by the wrong person.
    custody_token_ttl_minutes: int = Field(default=30, ge=1, le=1440)

    @field_validator(
        "evidence_root",
        "artifact_root",
        "report_root",
        "temp_root",
        "log_root",
        "ai_model_root",
        mode="before",
    )
    @classmethod
    def _expand_path(cls, value: str | Path) -> Path:
        """Expand user (~) and resolve configured filesystem roots.

        Args:
            value: Raw path-like value supplied via environment variable
                or default.

        Returns:
            A resolved, absolute `Path` object.
        """
        return Path(value).expanduser().resolve()

    def ensure_directories(self) -> None:
        """Create all configured filesystem roots if they do not exist.

        Must be called explicitly during application startup rather than
        as a side effect of settings construction, so that `Settings`
        objects remain safe to instantiate in unit tests without
        touching disk.

        Raises:
            OSError: If a directory cannot be created due to permissions
                or an underlying filesystem error.
        """
        for directory in (
            self.evidence_root,
            self.artifact_root,
            self.report_root,
            self.temp_root,
            self.log_root,
            self.ai_model_root,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide cached `Settings` instance.

    Using `lru_cache` guarantees a single `Settings` object is constructed
    per process, so environment parsing/validation happens exactly once
    and every module observes an identical configuration snapshot.

    Returns:
        The cached `Settings` instance for this process.
    """
    return Settings()

"""
Pydantic schemas for derived artifact registration and API responses.
Master Specification Section 20 (Media Artifact Model).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class ArtifactCreateRequest(BaseModel):
    """Request to register a derived artifact against a parent evidence item.

    Optional fields use the `Annotated[X, Field(...)] = default` form rather
    than `X = Field(default, ...)`: mypy (without the pydantic plugin, which
    is currently incompatible with the installed mypy version) cannot infer
    optionality through a bare `Field(default, ...)` call and reports every
    such field as a required constructor argument. `Annotated` keeps the
    same runtime behavior and OpenAPI metadata while type-checking
    correctly under `mypy --strict`.
    """

    relative_path: str = Field(
        ...,
        description="Artifact location, relative to the configured ARTIFACT_ROOT",
        min_length=1,
    )
    artifact_type: str = Field(
        ...,
        description="Kind of derived artifact (e.g. forensic_image, recovered_recording)",
        min_length=1,
        max_length=64,
    )
    parent_artifact_id: Annotated[
        int | None,
        Field(description="Primary key of the artifact this one was derived from, if any"),
    ] = None
    size_bytes: Annotated[
        int | None, Field(description="Artifact size in bytes, if known", ge=0)
    ] = None
    sha256: Annotated[
        str | None, Field(description="SHA-256 digest of the artifact, if computed")
    ] = None
    md5: Annotated[str | None, Field(description="MD5 digest of the artifact, if computed")] = None
    created_by: Annotated[
        str | None, Field(description="Examiner or tool identity that produced it")
    ] = None
    tool_version: Annotated[
        str | None, Field(description="Version of the tool that produced it")
    ] = None
    status: Annotated[str, Field(description="Lifecycle status of the artifact")] = "registered"


class ArtifactResponse(BaseModel):
    """Response containing derived artifact information."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    evidence_id: int
    parent_artifact_id: int | None
    artifact_type: str
    path: str
    size_bytes: int | None
    sha256: str | None
    md5: str | None
    created_at: datetime
    created_by: str | None
    tool_version: str | None
    status: str

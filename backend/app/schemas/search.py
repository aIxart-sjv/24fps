"""
Pydantic schemas for deterministic visual-attribute video search (Phase 23).
See `app.ai.attribute_search` and `app.core.video_search_manager` for the
full rationale and traceability chain.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class VideoSearchRequest(BaseModel):
    """A free-text visual-attribute query (e.g. `"red shirt guy"`)."""

    query: str = Field(..., min_length=1, max_length=256)
    recording_ids: list[int] | None = Field(
        default=None, description="Optional recording scope; omit to search the whole case."
    )


class VideoSearchSightingResponse(BaseModel):
    """One grouped visual-attribute match, traceable back to its exact
    underlying `AIResult` rows, recording, and frame range."""

    recording_id: int
    camera_id: str | None
    start_frame: int
    end_frame: int
    start_timestamp: str | None
    end_timestamp: str | None
    matched_color: str
    match_confidence: float
    ai_result_ids: list[int]
    track_id: int | None
    class_name: str
    source_artifact: int


class VideoSearchResponse(BaseModel):
    """The full, traceable outcome of one search request.

    `recognized=False` means the query named no color this deterministic
    classifier supports -- not that nothing was found. A finding of "no
    sightings" (`recognized=True`, `sightings=[]`) is distinct and
    reported via `warnings`. Every result is an ANALYTICAL VISUAL
    ATTRIBUTE MATCH, never an identity claim (task Phase 23 scope,
    "Do not claim natural-language search proves identity").
    """

    case_id: int
    query: str
    method: str
    method_version: str
    recognized_color: str | None
    recognized_object_class: str | None
    supported_colors: list[str]
    supported_classes: list[str]
    recognized: bool
    detections_examined: int
    sightings: list[VideoSearchSightingResponse]
    warnings: list[str]
    disclaimer: str = (
        "This is a deterministic clothing-color attribute match over existing AI object "
        "detections, not identity recognition. Appearance similarity is evidence, not proof -- "
        "multiple people may share the same detected color."
    )

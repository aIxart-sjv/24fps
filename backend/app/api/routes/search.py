"""
API route for deterministic visual-attribute video search (Phase 23,
"Required Feature -- Natural-Language Video Search"). See
`app.ai.attribute_search` and `app.core.video_search_manager` for the
full rationale.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_case_access
from app.core.video_search_manager import VideoSearchManager
from app.models import Case
from app.schemas.search import VideoSearchRequest, VideoSearchResponse, VideoSearchSightingResponse
from app.storage.db import get_db

router = APIRouter()


@router.post("/cases/{case_id}/video-search", response_model=VideoSearchResponse)
def search_video(
    case_id: int,
    request: VideoSearchRequest,
    db: Session = Depends(get_db),
    case: Case = Depends(require_case_access),
) -> VideoSearchResponse:
    """Search a case's already-computed AI detections for a visual attribute.

    Never runs new object detection -- searches only detections an
    examiner already produced via `POST /ai/jobs`. Returns an honest
    "no recognized attribute" or "no matches" result rather than
    fabricating a hit (task Phase 23 scope, "Do not claim 'red shirt'
    matching is reliable unless actually tested").
    """
    del case
    result = VideoSearchManager.search(
        db, case_id=case_id, query=request.query, recording_ids=request.recording_ids
    )
    return VideoSearchResponse(
        case_id=result.case_id,
        query=result.query,
        method=result.method,
        method_version=result.method_version,
        recognized_color=result.attributes.color,
        recognized_object_class=result.attributes.object_class,
        supported_colors=result.supported_colors,
        supported_classes=result.supported_classes,
        recognized=result.recognized,
        detections_examined=result.detections_examined,
        sightings=[
            VideoSearchSightingResponse(
                recording_id=s.recording_id,
                camera_id=s.camera_id,
                start_frame=s.start_frame,
                end_frame=s.end_frame,
                start_timestamp=s.start_timestamp,
                end_timestamp=s.end_timestamp,
                matched_color=s.matched_color,
                match_confidence=s.match_confidence,
                ai_result_ids=s.ai_result_ids,
                track_id=s.track_id,
                class_name=s.class_name,
                source_artifact=s.source_artifact,
            )
            for s in result.sightings
        ],
        warnings=result.warnings,
    )

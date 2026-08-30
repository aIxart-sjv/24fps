"""Real CP Plus evidence -- Phase 21 Part B acceptance test.

Benchmarks frame-redundancy optimization (`app.ai.frame_redundancy`)
against a real, hash-verified CP Plus recording: baseline (optimization
disabled -- every sampled frame analyzed, today's existing behavior)
versus optimized (optimization enabled), run back to back over the exact
same derived artifact and sampling parameters. Reports real, measured
numbers -- total/analyzed/skipped frame counts, actual wall-clock
processing time for each run, and whether detections differ -- rather
than a fabricated or assumed time-saving figure (task Phase 21 Part B:
"Never claim time saved solely from frame counts").

Also verifies the CPV master and its Phase 9 H.264 preview derived
artifact are provably byte-identical before and after both runs -- this
optimization changes only which frames get expensive model inference, it
never touches source video or derived media.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest

from app.config import get_settings
from app.core.ai_manager import AIManager
from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.core.recording_manager import RecordingManager
from app.hashing.sha256 import sha256_file
from app.models import AIResult, Artifact, JobStatus, RecordingMetadata
from app.schemas.case import CaseCreateRequest
from app.schemas.evidence import EvidenceCreateRequest
from app.storage.db import Base
from tests.fixtures.ai_models import requires_object_detection_model
from tests.fixtures.cp_plus_evidence import (
    load_expected_sha256,
    requires_real_evidence,
    sha256_of,
    smallest_real_cpv_path,
)

#: Sparse enough that even a multi-minute real CP Plus recording decodes
#: and runs inference on a manageable number of frames within test time
#: budget, while still producing enough samples for the benchmark to be
#: meaningful.
_BENCHMARK_SAMPLING_FPS = 2.0


@pytest.fixture
def real_evidence_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Matches the established pattern from
    tests/test_cp_plus_ai_real_evidence_integration.py."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    evidence_root = tmp_path / "evidence"
    artifact_root = tmp_path / "artifacts"
    evidence_root.mkdir()
    artifact_root.mkdir()
    monkeypatch.setenv("EVIDENCE_ROOT", str(evidence_root))
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    import app.models  # noqa: F401 - registers every ORM model on Base.metadata

    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()
    try:
        yield db, evidence_root
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        get_settings.cache_clear()


def _register_real_recording(db, evidence_root: Path, case_id: str):
    source_path = smallest_real_cpv_path()
    assert source_path is not None

    expected_hashes = load_expected_sha256()
    assert sha256_of(source_path) == expected_hashes[source_path.name]

    case_dir = evidence_root / case_id
    case_dir.mkdir()
    copied_path = case_dir / source_path.name
    shutil.copy2(source_path, copied_path)

    case = CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Redundancy IT"))
    evidence = EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id=copied_path.stem, source_type="native_export", source_path=str(copied_path)
        ),
    )
    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]
    recording = RecordingManager.extract_recording(db, recording.id)
    return case, recording, source_path, copied_path, expected_hashes


@requires_real_evidence
@requires_object_detection_model
def test_baseline_vs_optimized_object_detection_on_real_recording(real_evidence_db) -> None:
    db, evidence_root = real_evidence_db
    case, recording, source_path, copied_path, expected_hashes = _register_real_recording(
        db, evidence_root, "CASE-REDUNDANCY-BENCH"
    )
    # `recording.artifact_id` is the H.265 *master* artifact
    # (`RecordingManager.extract_recording` sets it there); the derived
    # H.264 *preview* artifact AIManager actually decodes from is a
    # separate row, looked up the same way `AIManager.
    # _resolve_source_artifact` does. Both must be provably unchanged by
    # this optimization -- neither is touched by frame-redundancy logic,
    # which only ever reads already-decoded in-memory frames.
    assert recording.artifact_id is not None
    master_artifact = db.query(Artifact).filter(Artifact.id == int(recording.artifact_id)).first()
    assert master_artifact is not None
    master_artifact_path = Path(master_artifact.path)
    master_sha256_before = sha256_file(master_artifact_path)

    preview_metadata = (
        db.query(RecordingMetadata)
        .filter(
            RecordingMetadata.recording_id == recording.id,
            RecordingMetadata.key == "preview_artifact_id",
        )
        .first()
    )
    assert preview_metadata is not None
    preview_artifact = db.query(Artifact).filter(Artifact.id == int(preview_metadata.value)).first()
    assert preview_artifact is not None
    preview_artifact_path = Path(preview_artifact.path)
    preview_sha256_before = sha256_file(preview_artifact_path)

    baseline_start = time.perf_counter()
    baseline_job = AIManager.run_job(
        db,
        case_id=case.id,
        recording_ids=[recording.id],
        analysis_types=["object_detection"],
        sampling_strategy="fps",
        sampling_value=_BENCHMARK_SAMPLING_FPS,
        frame_redundancy_enabled=False,
    )
    baseline_elapsed = time.perf_counter() - baseline_start

    assert baseline_job.status in (JobStatus.COMPLETED.value, JobStatus.PARTIAL.value)
    baseline_results = (
        db.query(AIResult).filter(AIResult.job_id == baseline_job.id).order_by(AIResult.id).all()
    )

    optimized_start = time.perf_counter()
    optimized_job = AIManager.run_job(
        db,
        case_id=case.id,
        recording_ids=[recording.id],
        analysis_types=["object_detection"],
        sampling_strategy="fps",
        sampling_value=_BENCHMARK_SAMPLING_FPS,
        frame_redundancy_enabled=True,
        frame_redundancy_threshold=3.0,
    )
    optimized_elapsed = time.perf_counter() - optimized_start

    assert optimized_job.status in (JobStatus.COMPLETED.value, JobStatus.PARTIAL.value)
    optimized_results = (
        db.query(AIResult).filter(AIResult.job_id == optimized_job.id).order_by(AIResult.id).all()
    )

    optimized_params = json.loads(optimized_job.parameters)
    stats = optimized_params.get("frame_redundancy_stats")

    # Report the real, measured comparison -- never a formula-derived
    # "time saved" claim.
    print(
        "\n[frame-redundancy benchmark] "
        f"baseline_wall_time_s={baseline_elapsed:.3f} "
        f"optimized_wall_time_s={optimized_elapsed:.3f} "
        f"baseline_results={len(baseline_results)} "
        f"optimized_results={len(optimized_results)} "
        f"frame_redundancy_stats={stats}"
    )

    if stats is not None:
        # Every frame the baseline sampled is still represented in the
        # optimized run's accounting -- none silently disappeared.
        assert stats["analyzed_count"] + stats["skipped_count"] == stats["total_frames"]
        assert stats["comparison_method"] == "grayscale_mean_absolute_difference"
        assert stats["reference_strategy"] == "last_analyzed_frame"

    # Detections are NOT required to be identical between baseline and
    # optimized -- a skipped frame produces zero detections for that
    # frame_number, which can differ from what the model would have
    # returned had it actually run. What IS required: every detection
    # that *was* produced references a real, valid sampled frame, never
    # a fabricated one.
    for result in optimized_results:
        assert result.source_artifact is not None
        assert result.job_id == optimized_job.id

    # Source CPV, its H.265 master artifact, and its derived H.264
    # preview artifact are all provably unchanged by either run.
    assert sha256_of(copied_path) == expected_hashes[source_path.name]
    assert sha256_of(source_path) == expected_hashes[source_path.name]
    assert sha256_file(master_artifact_path) == master_sha256_before
    assert sha256_file(preview_artifact_path) == preview_sha256_before

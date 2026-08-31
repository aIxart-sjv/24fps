#!/usr/bin/env python3
"""
Generate machine-readable Processing Performance / Accuracy-Validation /
Output-Parameter benchmark files from a REAL run of
`ProcessingOrchestrator.process_case` against the real CP Plus evidence
package (task: "For the real CP Plus evidence run, produce a
machine-readable processing benchmark showing the actual runtime of each
applicable module. Also produce a separate machine-readable analysis/
validation summary.").

Every number in the output files is read straight off the same response
builders `app.api.routes.processing` uses for the live API
(`_run_response`/`_accuracy_metrics_for_stage`/
`_output_parameters_for_stage`) -- this script does not compute or
format anything itself, so the files are guaranteed to match exactly
what the real `/processing/{id}`, `/processing/{id}/accuracy`, and
`/processing/{id}/outputs` endpoints would return for this run. Nothing
is estimated, mocked, or manually entered.

Uses an isolated temp EVIDENCE_ROOT/ARTIFACT_ROOT and an isolated SQLite
DB file -- the real, out-of-repo evidence package
(`~/Documents/24fps-evidence/cp-plus-2026-08-28/`) is only ever read
from, each file copied once into the isolated root before processing.

Usage:
    python scripts/generate_cp_plus_benchmark.py [--out-dir DIR]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.routes.processing import (  # noqa: E402
    _accuracy_metrics_for_stage,
    _case_level_output_parameters,
    _output_parameters_for_stage,
    _run_response,
)
from app.config import get_settings  # noqa: E402
from app.core.auth_manager import AuthManager  # noqa: E402
from app.core.case_manager import CaseManager  # noqa: E402
from app.core.evidence_manager import EvidenceManager  # noqa: E402
from app.core.processing_orchestrator import ProcessingOrchestrator  # noqa: E402
from app.core.processing_policy import ProcessingPolicy  # noqa: E402
from app.schemas.case import CaseCreateRequest  # noqa: E402
from app.schemas.evidence import EvidenceCreateRequest  # noqa: E402
from app.schemas.processing import (
    AccuracyValidationResponse,
    OutputParametersResponse,
)  # noqa: E402
from app.storage.db import Base  # noqa: E402

REAL_EVIDENCE_DIR = Path.home() / "Documents" / "24fps-evidence" / "cp-plus-2026-08-28"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "benchmarks",
        help="Directory to write the benchmark JSON files into.",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=REAL_EVIDENCE_DIR,
        help="Real CP Plus evidence package directory (read-only).",
    )
    args = parser.parse_args()

    if not args.evidence_dir.is_dir():
        print(f"Real evidence package not found at {args.evidence_dir}", file=sys.stderr)
        return 1
    cpv_files = sorted(args.evidence_dir.glob("*.cpv"))
    if not cpv_files:
        print(f"No .cpv files found in {args.evidence_dir}", file=sys.stderr)
        return 1

    import tempfile

    with tempfile.TemporaryDirectory(prefix="24fps-benchmark-") as tmp:
        tmp_path = Path(tmp)
        evidence_root = tmp_path / "evidence"
        artifact_root = tmp_path / "artifacts"
        evidence_root.mkdir()
        artifact_root.mkdir()

        import os

        os.environ["EVIDENCE_ROOT"] = str(evidence_root)
        os.environ["ARTIFACT_ROOT"] = str(artifact_root)
        get_settings.cache_clear()

        engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        import app.models  # noqa: F401 - registers every ORM model on Base.metadata

        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine, expire_on_commit=False)()

        try:
            case = CaseManager.create_case(
                db,
                CaseCreateRequest(
                    case_id="CP-PLUS-BENCHMARK", name="CP Plus real-evidence benchmark"
                ),
            )
            officer = AuthManager.create_user(
                db,
                username="benchmark_officer",
                display_name="Benchmark Officer",
                password="benchmark-only-not-a-real-account",
            )

            case_dir = evidence_root / case.case_id
            case_dir.mkdir()
            print(f"Registering {len(cpv_files)} real CP Plus evidence file(s)...")
            for source_path in cpv_files:
                copied_path = case_dir / source_path.name
                shutil.copy2(source_path, copied_path)
                EvidenceManager.register_evidence(
                    db,
                    case.id,
                    EvidenceCreateRequest(
                        evidence_id=copied_path.stem,
                        source_type="native_export",
                        source_path=str(copied_path),
                    ),
                )

            print("Running ProcessingOrchestrator.process_case (real, synchronous run)...")
            summary = ProcessingOrchestrator.process_case(
                db, case.id, policy=ProcessingPolicy(run_ai=False), triggered_by=officer
            )
            root_job = summary.root_job

            performance = _run_response(
                root_job,
                new_finding_ids=summary.new_finding_ids,
                notification_ids=summary.notification_ids,
            )

            accuracy_metrics = []
            output_parameters = []
            for stage in sorted(root_job.child_jobs, key=lambda j: j.id):
                accuracy_metrics.extend(_accuracy_metrics_for_stage(db, stage))
                output_parameters.extend(_output_parameters_for_stage(db, stage))
            output_parameters.extend(_case_level_output_parameters(db, case.id))

            accuracy = AccuracyValidationResponse(root_job_id=root_job.id, metrics=accuracy_metrics)
            outputs = OutputParametersResponse(
                root_job_id=root_job.id, parameters=output_parameters
            )

            args.out_dir.mkdir(parents=True, exist_ok=True)
            performance_path = args.out_dir / "cp_plus_processing_benchmark.json"
            accuracy_path = args.out_dir / "cp_plus_analysis_validation_summary.json"
            outputs_path = args.out_dir / "cp_plus_output_parameters.json"

            performance_path.write_text(json.dumps(performance.model_dump(), indent=2, default=str))
            accuracy_path.write_text(json.dumps(accuracy.model_dump(), indent=2, default=str))
            outputs_path.write_text(json.dumps(outputs.model_dump(), indent=2, default=str))

            print(f"Wrote {performance_path}")
            print(f"Wrote {accuracy_path}")
            print(f"Wrote {outputs_path}")
            print(
                f"\nRoot job status: {performance.root_job.status} | "
                f"total_duration_seconds: {performance.total_duration_seconds} | "
                f"stages: {performance.stages_total}"
            )
            return 0
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)
            engine.dispose()
            get_settings.cache_clear()


if __name__ == "__main__":
    raise SystemExit(main())

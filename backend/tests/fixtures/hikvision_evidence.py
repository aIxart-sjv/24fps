"""
Shared helper for tests that use the real Hikvision evidence set (Phase 26).

The evidence set (three exported `.mp4` clips + `.txt`/`.docx` device
export-log sidecars + device configuration screenshots) deliberately
lives OUTSIDE this repository at `~/Documents/24fps-evidence/Hikvision/`
-- real, controlled forensic evidence from a confirmed Hikvision
DS-7A04HQHI-K1 (firmware V4.30.220 Build 220216) and must never be copied
into version control, renamed, re-encoded, or modified in any way.

Every test that depends on this evidence must skip (not fail) when the
directory is not present on the machine running the tests -- e.g. in CI,
where this out-of-repo evidence is not expected to exist. Mirrors
`tests.fixtures.cp_plus_evidence`'s own shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest

EVIDENCE_DIR = Path.home() / "Documents" / "24fps-evidence" / "Hikvision"

#: The three real, examiner-confirmed exported clips (Phase 26 evidence set).
KNOWN_CLIP_NAMES = (
    "A01_20260829100000.mp4",
    "A01_20260831080000.mp4",
    "A02_20260831080000.mp4",
)

#: The device serial confirmed on all three clips' export-log sidecars and
#: cross-checked against the device's own on-screen system-information
#: display (photographed alongside the evidence set).
KNOWN_DEVICE_SERIAL = "0420220517CCWRJ98043179WCVU"
KNOWN_DEVICE_MODEL = "DS-7A04HQHI-K1"


def evidence_available() -> bool:
    """Whether the real Hikvision evidence set is present on this machine."""
    return EVIDENCE_DIR.is_dir() and all(
        (EVIDENCE_DIR / name).is_file() for name in KNOWN_CLIP_NAMES
    )


requires_real_evidence = pytest.mark.skipif(
    not evidence_available(),
    reason=(
        f"real Hikvision evidence set not found at {EVIDENCE_DIR} (expected outside the "
        "repository; this test is skipped, not failed, when absent)"
    ),
)


def real_clip_paths() -> list[Path]:
    """All three real exported `.mp4` clips.

    Returns an empty list if the evidence set is not present -- callers
    combine this with `requires_real_evidence` so the test is skipped
    rather than failing on an empty list.
    """
    if not evidence_available():
        return []
    return [EVIDENCE_DIR / name for name in KNOWN_CLIP_NAMES]

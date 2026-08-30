"""
Shared helper for tests that use the real CP Plus evidence package.

The evidence package (13 real `.cpv` files + `CPV Player.exe` +
`SHA256SUMS.txt`/`MD5SUMS.txt`) deliberately lives OUTSIDE this repository
at `~/Documents/24fps-evidence/cp-plus-2026-08-28/` — it is 13 real,
hash-verified forensic evidence files (~181 MB) and must never be copied
into version control, renamed, re-encoded, or modified in any way.

Every test that depends on this evidence must skip (not fail) when the
package is not present on the machine running the tests — e.g. in CI,
where this out-of-repo evidence is not expected to exist.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

EVIDENCE_DIR = Path.home() / "Documents" / "24fps-evidence" / "cp-plus-2026-08-28"
SHA256SUMS_PATH = EVIDENCE_DIR / "SHA256SUMS.txt"

_CPV_NAME_RE = re.compile(r"^NVR_ch(\d+)_[A-Za-z0-9]+_(\d{14})_(\d{14})\.cpv$")


def evidence_available() -> bool:
    """Whether the real CP Plus evidence package is present on this machine."""
    return EVIDENCE_DIR.is_dir() and SHA256SUMS_PATH.is_file()


requires_real_evidence = pytest.mark.skipif(
    not evidence_available(),
    reason=(
        f"real CP Plus evidence package not found at {EVIDENCE_DIR} "
        "(expected outside the repository; this test is skipped, not failed, when absent)"
    ),
)


def real_cpv_paths() -> list[Path]:
    """All 13 real `.cpv` files, sorted by their filename's start timestamp.

    Returns an empty list if the evidence package is not present — callers
    combine this with `requires_real_evidence` so the test is skipped
    rather than failing on an empty list.
    """
    if not evidence_available():
        return []
    paths = sorted(EVIDENCE_DIR.glob("*.cpv"))
    matched = [p for p in paths if _CPV_NAME_RE.match(p.name)]
    return sorted(matched, key=lambda p: _CPV_NAME_RE.match(p.name).group(2))  # type: ignore[union-attr]


def smallest_real_cpv_path() -> Path | None:
    """The smallest real `.cpv` file (fastest for tests that fully walk one file)."""
    paths = real_cpv_paths()
    if not paths:
        return None
    return min(paths, key=lambda p: p.stat().st_size)


def sha256_of(path: Path) -> str:
    """Stream-hash `path` in fixed-size chunks — never loads the whole file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_expected_sha256() -> dict[str, str]:
    """Parse `SHA256SUMS.txt` into `{filename: expected_hex_digest}`."""
    expected: dict[str, str] = {}
    if not SHA256SUMS_PATH.is_file():
        return expected
    for line in SHA256SUMS_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        digest, _, name = line.partition("  ")
        name = name.strip().lstrip("./").strip("'")
        if digest and name:
            expected[Path(name).name] = digest.strip()
    return expected

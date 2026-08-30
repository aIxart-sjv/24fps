"""
Generic filesystem/index recovery (Recovery Layer 1).
Master Specification Section 21: "Recover recordings whose references/
index information still exists." Tech Stack Section 13: this is the
*preferred* method when a vendor's filesystem/index structures are
available, because it is far stronger evidence than blind carving.

This module holds no vendor-specific logic: whether a given evidence
source actually has a discoverable index/seek-table is a fact only the
vendor adapter can establish (e.g. CP Plus's CPV container was confirmed,
by Phase 8's byte-level analysis, to carry no such structure at all — see
`app.adapters.cp_plus.recovery`). This module only defines the shared
outcome shape and the trivial "no index structure available" case every
currently-supported vendor actually hits today.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.recovery import RecoveryStatus


@dataclass(frozen=True)
class FilesystemRecoveryOutcome:
    """Outcome of attempting Layer 1 (filesystem/index) recovery."""

    status: RecoveryStatus
    reason: str
    recovered_recording_ids: list[str]


def no_index_structure(reason: str) -> FilesystemRecoveryOutcome:
    """Build the honest `UNSUPPORTED` outcome for a vendor with no discoverable index.

    Args:
        reason: The evidence-based explanation for why no index/seek-table
            exists (e.g. a citation of the analysis that established this).

    Returns:
        A `FilesystemRecoveryOutcome` with `status=UNSUPPORTED`.
    """
    return FilesystemRecoveryOutcome(
        status=RecoveryStatus.UNSUPPORTED, reason=reason, recovered_recording_ids=[]
    )

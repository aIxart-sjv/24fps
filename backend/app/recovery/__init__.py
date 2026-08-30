"""
Recovery domain — layered forensic recovery of deleted/damaged/fragmented
recordings (Master Specification Section 21, "Recovery Engine").

`RecoveryStatus`/`RecoveryMethod` live here, not in `app.models`, so that
this whole package — and any vendor adapter's own `recovery.py` that needs
these vocabulary values — never depends on the database/ORM layer,
matching the layering every other adapter-facing package
(`app.acquisition`, `app.detection`, `app.hashing`) already keeps. The
persisted `RecoveryResult` ORM row (`app.models.recovery`) re-exports these
same enums for its own `status`/`method` columns rather than redefining
them.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["RecoveryMethod", "RecoveryStatus"]


class RecoveryStatus(str, Enum):
    """Outcome of one recovery attempt (a layer's, or the overall engine's).

    Never `RECOVERED` for incomplete/unverified output (Phase 10 task
    scope, section 10) — `RECOVERED` is reserved for a recovery that hit no
    truncation/corruption/gap anywhere in the recovered range. Anything
    that stopped early but still produced real, valid bytes is `PARTIAL`.
    """

    NOT_ATTEMPTED = "not_attempted"
    UNSUPPORTED = "unsupported"
    NO_RECOVERY_FOUND = "no_recovery_found"
    PARTIAL = "partial"
    RECOVERED = "recovered"
    FAILED = "failed"


class RecoveryMethod(str, Enum):
    """Which recovery layer (Master Specification Section 21) produced a result."""

    FILESYSTEM_INDEX = "filesystem_index"
    VENDOR_DAMAGED_RECOVERY = "vendor_damaged_recovery"
    CARVING = "carving"
    FRAGMENT_RECONSTRUCTION = "fragment_reconstruction"

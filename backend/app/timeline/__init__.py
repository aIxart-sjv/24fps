"""
Timeline domain — timestamp normalization for forensic evidence
(Master Specification Section 26, "Timestamp Normalization"; Section 27,
"Timestamp Data Model").

`TimestampSource`/`NormalizationStatus`/`NormalizationMethod` and the
plain `ReferencePair`/`NormalizationResult` dataclasses live here, not in
`app.models`, so this whole package — and any DB-aware caller — never
needs the ORM/database layer just to reason about normalization
vocabulary. This mirrors `app.recovery.__init__`'s `RecoveryStatus`/
`RecoveryMethod` split (Phase 10) and keeps the same layering
`app.adapters`, `app.acquisition`, `app.detection`, `app.hashing`,
`app.media`, and `app.recovery` already maintain: no import from
`app.models` anywhere in this package.

Master Specification Section 27 describes a conceptual `TimestampRecord`
shape (source_timestamp, source_timezone, reference_timestamp,
reference_timezone, offset_seconds, normalized_timestamp,
normalization_method, confidence, source_evidence_id, notes) — but
Section 50 (the actual database model list) has no corresponding table.
Its fields are instead carried by `Recording.start_original/end_original/
start_normalized/end_normalized` (already-existing typed columns) plus
the generic `metadata` key/value table Phase 9 already built for exactly
this purpose ("if frequently queried fields become stable, promote them
into typed columns rather than putting everything into a key/value
table"). `NormalizationResult` below is the in-memory/return-value
equivalent of that conceptual shape — never persisted as its own table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

__all__ = [
    "NormalizationMethod",
    "NormalizationResult",
    "NormalizationStatus",
    "ReferencePair",
    "TimestampSource",
]


class TimestampSource(str, Enum):
    """Where an original timestamp value actually came from.

    Master Specification Section 26's input list, restricted to the
    sources this codebase can currently actually produce/classify (task
    Phase 11 scope, section 2: "Do not silently treat all sources as
    equally reliable" — an explicit, closed vocabulary is how that
    non-equivalence is enforced).
    """

    VENDOR_DEVICE_TIMESTAMP = "vendor_device_timestamp"
    CPV_BINARY_TIMESTAMP = "cpv_binary_timestamp"
    FILENAME_DERIVED = "filename_derived"
    FILESYSTEM_TIMESTAMP = "filesystem_timestamp"
    NATIVE_EXPORT_METADATA = "native_export_metadata"
    ACQUISITION_TIMESTAMP = "acquisition_timestamp"
    EXAMINER_REFERENCE = "examiner_reference"
    UNKNOWN = "unknown"


class NormalizationStatus(str, Enum):
    """Outcome of one normalization attempt.

    Deliberately four states (task Phase 11 scope, section 11), precisely
    defined here since the specification names the vocabulary but not
    its exact semantics:

    - `UNKNOWN`: no usable original timestamp, or no source timezone at
      all — nothing to compute from. `start_normalized`/`end_normalized`
      must stay `NULL`.
    - `UNVERIFIED`: a source timezone is known (e.g. an examiner-supplied
      IANA zone from a device fact sheet) so a timezone-converted value
      *is* computed and stored, but no independently-verified reference-
      clock pair exists — the recorder's absolute clock accuracy is not
      confirmed. This is a real, useful, but explicitly incomplete result.
    - `PARTIAL`: some but not all of the chain is verified (e.g. an
      offset verified against one anchor point but not independently
      confirmed for the other, or verified for some but not all segments
      of a multi-segment recording).
    - `VERIFIED`: source timezone known *and* offset independently
      confirmed via a trustworthy reference pair.

    Never `VERIFIED` on a fabricated or assumed input — status downgrades
    honestly rather than defaulting upward.
    """

    UNKNOWN = "unknown"
    UNVERIFIED = "unverified"
    PARTIAL = "partial"
    VERIFIED = "verified"


class NormalizationMethod(str, Enum):
    """How a normalized timestamp was derived (Master Specification Section 27's
    "Possible normalization methods" list, restricted to what this phase
    actually implements — cross-camera correlation is Phase 12)."""

    TIMEZONE_CONVERSION = "timezone_conversion"
    EXPLICIT_DVR_CLOCK_COMPARISON = "explicit_dvr_clock_comparison"
    KNOWN_EXTERNAL_EVENT = "known_external_event"
    SYSTEM_REFERENCE_TIME = "system_reference_time"
    MANUAL_EXAMINER_ADJUSTMENT = "manual_examiner_adjustment"
    NONE = "none"


@dataclass(frozen=True)
class ReferencePair:
    """An examiner-supplied external reference timestamp to compare against
    a recorder/original timestamp (task Phase 11 scope, section 8: "we
    only need enough structure to document the reference source used for
    normalization" — deliberately just a plain value object, not a new
    trusted-time subsystem).

    `reference_timestamp` may be naive (paired with `reference_timezone`)
    or already timezone-aware (in which case `reference_timezone` is
    optional, used only for display/provenance). `method` names which of
    Section 27's normalization methods this specific reference represents
    (explicit DVR clock comparison, a known external event, system/
    reference time, or a documented manual examiner adjustment) — the
    caller states this explicitly rather than the engine guessing it from
    free text.
    """

    reference_timestamp: datetime
    reference_timezone: str | None
    reference_source: str
    reference_basis: str
    method: NormalizationMethod = NormalizationMethod.EXPLICIT_DVR_CLOCK_COMPARISON


@dataclass(frozen=True)
class NormalizationResult:
    """The full, explainable outcome of one normalization attempt.

    Answers every question task Phase 11 scope section 19 lists: original
    value/source are the inputs the caller already supplied;
    `source_timezone`/`offset_seconds`/`reference` explain how (if at
    all) the normalized value was derived; `status`/`reason` explain why
    it is or isn't trustworthy.
    """

    source: TimestampSource
    status: NormalizationStatus
    method: NormalizationMethod
    reason: str
    original_timestamp: datetime | None
    source_timezone: str | None = None
    source_timezone_basis: str | None = None
    normalized_timestamp: datetime | None = None
    offset_seconds: float | None = None
    reference: ReferencePair | None = None
    warnings: list[str] = field(default_factory=list)

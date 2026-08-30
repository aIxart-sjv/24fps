"""
Business logic for timestamp normalization (Phase 11).

This is the DB-aware orchestration layer — mirrors
`app.core.recording_manager.RecordingManager` and
`app.core.recovery_manager.RecoveryManager` exactly: it never rescans or
reopens evidence files (task Phase 11 scope, section 28 — everything
needed already lives on the `Recording` row and its `RecordingMetadata`
entries, populated by Phase 9's `RecordingManager`), and it is the one
place vendor-specific timestamp-source knowledge lives (mirroring
`RecordingManager`/`RecoveryManager`'s own CP-Plus-dispatch precedent) —
the pure engine underneath, `app.timeline.*`, has no vendor knowledge at
all.

Vendor dispatch is CP Plus-only and explicit, for the same reason
`RecordingManager` already documents: no vendor is wired into
`AdapterRegistry` via real device identification yet. For CP Plus, the
one and only source classification implemented is `FILENAME_DERIVED` —
`Recording.start_original`/`end_original` are, by Phase 8/9's own
documented, invariant contract, *always* filename-derived, never the
unresolved CPV binary counter (`app.adapters.cp_plus.models`
`CPPlusRecordingRecord`'s own docstring). The binary counter
(`RecordingMetadata` keys `raw_timestamp`/`timestamp_status`/
`timestamp_source`, written by Phase 9) is never read as a normalization
input anywhere in this module — that is the forensic safety property
task Phase 11 scope section 15 requires ("raw value preserved,
interpretation unresolved, normalized value not generated from it").
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.recording_manager import RecordingManager
from app.models import Recording, RecordingMetadata
from app.timeline import NormalizationResult, NormalizationStatus, ReferencePair, TimestampSource
from app.timeline.normalization import apply_verified_offset, normalize

__all__ = ["RecordingNormalizationOutcome", "TimestampManager"]

_STATUS_KEY = "timestamp_normalization_status"
_SOURCE_KEY = "timestamp_normalization_source"
_METHOD_KEY = "timestamp_normalization_method"
_REASON_START_KEY = "timestamp_normalization_reason_start"
_REASON_END_KEY = "timestamp_normalization_reason_end"
_SOURCE_TIMEZONE_KEY = "timestamp_source_timezone"
_SOURCE_TIMEZONE_BASIS_KEY = "timestamp_source_timezone_basis"
_OFFSET_SECONDS_KEY = "timestamp_offset_seconds"
_REFERENCE_SOURCE_KEY = "timestamp_reference_source"
_REFERENCE_BASIS_KEY = "timestamp_reference_basis"
_REFERENCE_TIMESTAMP_KEY = "timestamp_reference_timestamp"


@dataclass(frozen=True)
class RecordingNormalizationOutcome:
    """The full result of normalizing one `Recording`'s start/end timestamps."""

    recording: Recording
    start_result: NormalizationResult
    end_result: NormalizationResult
    overall_status: NormalizationStatus


class TimestampManager:
    """Service layer for computing and persisting timestamp normalization."""

    @staticmethod
    def normalize_recording(
        db: Session,
        recording_id: int,
        *,
        source_timezone: str | None = None,
        source_timezone_basis: str | None = None,
        reference: ReferencePair | None = None,
    ) -> RecordingNormalizationOutcome:
        """Normalize `Recording.start_original`/`end_original` and persist the result.

        Never overwrites `start_original`/`end_original` (task Phase 11
        scope, section 29 — forensic safety). Populates
        `start_normalized`/`end_normalized` only when a given side
        resolves to something better than `UNKNOWN`; the other side, and
        the full explanation (source, timezone, reference, offset,
        reason), is written to `RecordingMetadata` via the existing
        `RecordingManager._set_metadata` upsert-by-key helper (idempotent
        — re-running normalization updates the same rows).

        Args:
            db: Database session.
            recording_id: Primary key of the `Recording` to normalize.
            source_timezone: IANA timezone name to interpret the (naive)
                original timestamps under (e.g. `"Asia/Kolkata"`).
                Examiner-supplied — never inferred or defaulted.
            source_timezone_basis: Free-text provenance for
                `source_timezone` (e.g. "case device fact sheet: NVR
                configured for IST").
            reference: An independently-sourced reference timestamp to
                compute a verified clock offset against. Omit when no
                trustworthy reference exists.

        Returns:
            A `RecordingNormalizationOutcome`.

        Raises:
            ValueError: If the recording is not found.
        """
        recording = db.query(Recording).filter(Recording.id == recording_id).first()
        if not recording:
            raise ValueError(f"Recording with id {recording_id} not found")

        source, source_note = TimestampManager._classify_source(db, recording)

        # `start_original` is the anchor: any supplied reference pair is
        # matched against it alone. A single external reference
        # corresponds to one specific real-world instant — it must never
        # be re-compared a second time against `end_original` too (that
        # would silently derive a *different* offset from the same
        # external event, which the event does not actually evidence).
        start_result = normalize(
            recording.start_original,
            source=source,
            source_timezone=source_timezone,
            source_timezone_basis=source_timezone_basis,
            reference=reference,
        )
        if recording.end_original is None:
            end_result = normalize(None, source=source)
        elif (
            start_result.status == NormalizationStatus.VERIFIED
            and start_result.offset_seconds is not None
            and source_timezone is not None
            and reference is not None
        ):
            # Carry the already-verified offset forward to end_original
            # rather than re-deriving a second, independent offset from
            # the same reference — see `apply_verified_offset`'s
            # docstring for the negligible-clock-drift assumption this
            # makes explicit.
            end_result = apply_verified_offset(
                recording.end_original,
                source=source,
                source_timezone=source_timezone,
                source_timezone_basis=source_timezone_basis,
                offset_seconds=start_result.offset_seconds,
                method=start_result.method,
                reference=reference,
            )
        else:
            end_result = normalize(
                recording.end_original,
                source=source,
                source_timezone=source_timezone,
                source_timezone_basis=source_timezone_basis,
                reference=None,
            )
        overall_status = TimestampManager._combine_status(start_result.status, end_result.status)

        # `start_original`/`end_original` are never touched. Normalized
        # fields reflect exactly this call's outcome — set when genuinely
        # resolved past UNKNOWN (task section 12: "Do not populate
        # normalized values simply to avoid NULL"), and explicitly
        # cleared back to NULL when it is not, so a re-run with weaker
        # inputs (e.g. a timezone omitted this time) can never leave a
        # stale normalized value on the row that disagrees with the
        # freshly-written `timestamp_normalization_status` metadata.
        # `NormalizationResult.normalized_timestamp` is always UTC-aware
        # (`app.timeline.normalization`'s `to_utc()`). SQLite's
        # `DateTime(timezone=True)` column type (Phase 2, unchanged here)
        # does not preserve tzinfo across a write/read round trip — this
        # is a pre-existing characteristic of every such column in this
        # schema (confirmed against a bare SQLAlchemy/SQLite table,
        # unrelated to this phase's code), not something Phase 11
        # introduces: `recording.start_normalized` reads back as a naive
        # datetime whose numeric value is always UTC.
        recording.start_normalized = (
            start_result.normalized_timestamp
            if start_result.status != NormalizationStatus.UNKNOWN
            else None
        )
        recording.end_normalized = (
            end_result.normalized_timestamp
            if end_result.status != NormalizationStatus.UNKNOWN
            else None
        )
        db.commit()
        db.refresh(recording)

        RecordingManager._set_metadata(
            db, recording, _STATUS_KEY, overall_status.value
        )  # noqa: SLF001
        RecordingManager._set_metadata(db, recording, _SOURCE_KEY, source.value)  # noqa: SLF001
        RecordingManager._set_metadata(  # noqa: SLF001
            db, recording, _METHOD_KEY, start_result.method.value
        )
        RecordingManager._set_metadata(
            db, recording, _REASON_START_KEY, start_result.reason
        )  # noqa: SLF001
        RecordingManager._set_metadata(
            db, recording, _REASON_END_KEY, end_result.reason
        )  # noqa: SLF001
        if source_note is not None:
            RecordingManager._set_metadata(  # noqa: SLF001
                db, recording, "timestamp_source_note", source_note
            )
        if source_timezone is not None:
            RecordingManager._set_metadata(  # noqa: SLF001
                db, recording, _SOURCE_TIMEZONE_KEY, source_timezone
            )
        if source_timezone_basis is not None:
            RecordingManager._set_metadata(  # noqa: SLF001
                db, recording, _SOURCE_TIMEZONE_BASIS_KEY, source_timezone_basis
            )
        if start_result.offset_seconds is not None:
            RecordingManager._set_metadata(  # noqa: SLF001
                db, recording, _OFFSET_SECONDS_KEY, str(start_result.offset_seconds)
            )
        if reference is not None:
            RecordingManager._set_metadata(  # noqa: SLF001
                db, recording, _REFERENCE_SOURCE_KEY, reference.reference_source
            )
            RecordingManager._set_metadata(  # noqa: SLF001
                db, recording, _REFERENCE_BASIS_KEY, reference.reference_basis
            )
            RecordingManager._set_metadata(  # noqa: SLF001
                db,
                recording,
                _REFERENCE_TIMESTAMP_KEY,
                reference.reference_timestamp.isoformat(),
            )

        return RecordingNormalizationOutcome(
            recording=recording,
            start_result=start_result,
            end_result=end_result,
            overall_status=overall_status,
        )

    @staticmethod
    def resolve_timestamp_error(db: Session, recording: Recording) -> float | None:
        """Return the verified clock-offset magnitude for `recording`, if any.

        Reused by `RecoveryManager` to populate `RecoveryResult.
        timestamp_error` (task Phase 11 scope, section 13). Returns
        `None` whenever no `VERIFIED` normalization has been computed for
        this recording — never a fabricated or estimated error value.

        Args:
            db: Database session.
            recording: The recording to check.

        Returns:
            `abs(offset_seconds)` from the most recent normalization, or
            `None` if unresolved/unverified.
        """
        status = TimestampManager._get_metadata_value(db, recording, _STATUS_KEY)
        if status != NormalizationStatus.VERIFIED.value:
            return None
        offset_raw = TimestampManager._get_metadata_value(db, recording, _OFFSET_SECONDS_KEY)
        if offset_raw is None:
            return None
        try:
            return abs(float(offset_raw))
        except ValueError:
            return None

    @staticmethod
    def _classify_source(db: Session, recording: Recording) -> tuple[TimestampSource, str | None]:
        """Determine the `TimestampSource` for `recording.start_original`/`end_original`.

        The only vendor-aware decision in this module — see the module
        docstring. Unrecognized/absent vendor metadata yields
        `TimestampSource.UNKNOWN`, never a guessed classification.
        """
        vendor = TimestampManager._get_metadata_value(db, recording, "vendor")
        if vendor == "CP Plus":
            return (
                TimestampSource.FILENAME_DERIVED,
                "CP Plus Recording.start_original/end_original are always filename-derived "
                "(Phase 8/9 contract); the CPV binary counter is never used as a normalization "
                "input",
            )
        return (
            TimestampSource.UNKNOWN,
            f"no timestamp-source classification is implemented for vendor {vendor!r}",
        )

    @staticmethod
    def _combine_status(
        start_status: NormalizationStatus, end_status: NormalizationStatus
    ) -> NormalizationStatus:
        """Combine independent start/end normalization statuses into one recording-level status.

        Equal statuses pass through unchanged (both `UNKNOWN`, both
        `UNVERIFIED`, or both `VERIFIED`). Any disagreement — one side
        resolved further than the other — is `PARTIAL` (task Phase 11
        scope, section 11: "some but not all of the chain is verified").
        """
        if start_status == end_status:
            return start_status
        return NormalizationStatus.PARTIAL

    @staticmethod
    def _get_metadata_value(db: Session, recording: Recording, key: str) -> str | None:
        entry = (
            db.query(RecordingMetadata)
            .filter(RecordingMetadata.recording_id == recording.id, RecordingMetadata.key == key)
            .first()
        )
        return entry.value if entry is not None else None

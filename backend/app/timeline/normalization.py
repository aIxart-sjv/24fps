"""
The one authoritative timestamp normalization function
(Master Specification Section 26, "Canonical model": original timestamp
-> timezone interpretation -> clock offset estimation -> normalized
timestamp -> confidence).

Task Phase 11 scope, section 9: "There must be one clear authoritative
path for timestamp normalization" — `normalize()` below is that path.
Every other Phase 11 module (`app.core.timestamp_manager`, the API route)
calls this function rather than re-deriving normalization logic. It is
pure (no DB, no I/O, no vendor knowledge) and fully deterministic.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.timeline import (
    NormalizationMethod,
    NormalizationResult,
    NormalizationStatus,
    ReferencePair,
    TimestampSource,
)
from app.timeline.offset import NaiveTimestampError, compute_offset
from app.timeline.timezone import UnknownTimezoneError, attach_timezone, to_utc


def normalize(
    original_timestamp: datetime | None,
    *,
    source: TimestampSource,
    source_timezone: str | None = None,
    source_timezone_basis: str | None = None,
    reference: ReferencePair | None = None,
) -> NormalizationResult:
    """Normalize one original timestamp into a UTC instant, only as far as the evidence supports.

    Args:
        original_timestamp: The original timestamp value. May be `None`
            (source has no usable value at all), timezone-naive (the
            common case — e.g. a filename-derived local time), or already
            timezone-aware.
        source: Which kind of original value this is (task Phase 11
            scope, section 2 — every timestamp must declare its source).
        source_timezone: An IANA timezone name to interpret a naive
            `original_timestamp` under. Required whenever
            `original_timestamp` is naive; ignored (with a warning if
            supplied but unused) when it is already timezone-aware.
            **Never defaulted or guessed** — a `None` here with a naive
            timestamp means normalization stops at `UNKNOWN`.
        source_timezone_basis: Free-text provenance for `source_timezone`
            (e.g. "examiner-supplied: case device fact sheet states the
            NVR is configured for IST") — carried through into the result
            purely for explainability, never used in the calculation.
        reference: An independently-sourced timestamp to compute a
            verified clock offset against. Omit when no trustworthy
            reference exists — normalization still proceeds as far as
            timezone conversion alone (status `UNVERIFIED`), never
            fabricating an offset.

    Returns:
        A `NormalizationResult`. `status` is:
          - `UNKNOWN` when there is no original value, or no way to
            interpret its timezone;
          - `UNVERIFIED` when a timezone-converted value was produced but
            no verified reference-clock offset was applied;
          - `VERIFIED` when a timezone-converted value was produced *and*
            an offset was computed from a supplied `reference`.
        `PARTIAL` is never returned by this function directly — it is an
        aggregate status a caller computes when combining more than one
        `normalize()` call (e.g. a recording's start and end timestamps)
        that disagree in status; see `app.core.timestamp_manager`.
    """
    if original_timestamp is None:
        return NormalizationResult(
            source=source,
            status=NormalizationStatus.UNKNOWN,
            method=NormalizationMethod.NONE,
            reason="no original timestamp value is available for this source",
            original_timestamp=None,
        )

    warnings: list[str] = []

    if original_timestamp.tzinfo is not None:
        source_aware = original_timestamp
        if source_timezone is not None:
            warnings.append(
                f"original_timestamp is already timezone-aware ({original_timestamp.tzinfo!r}); "
                f"the supplied source_timezone {source_timezone!r} was not applied"
            )
    else:
        if source_timezone is None:
            return NormalizationResult(
                source=source,
                status=NormalizationStatus.UNKNOWN,
                method=NormalizationMethod.NONE,
                reason=(
                    "original timestamp is timezone-naive and no source_timezone was supplied; "
                    "its wall-clock reading cannot be interpreted without fabricating a timezone"
                ),
                original_timestamp=original_timestamp,
            )
        try:
            source_aware = attach_timezone(original_timestamp, source_timezone)
        except UnknownTimezoneError as exc:
            return NormalizationResult(
                source=source,
                status=NormalizationStatus.UNKNOWN,
                method=NormalizationMethod.NONE,
                reason=f"source_timezone could not be resolved: {exc}",
                original_timestamp=original_timestamp,
                source_timezone=source_timezone,
                source_timezone_basis=source_timezone_basis,
            )

    normalized_no_offset = to_utc(source_aware)

    if reference is None:
        return NormalizationResult(
            source=source,
            status=NormalizationStatus.UNVERIFIED,
            method=NormalizationMethod.TIMEZONE_CONVERSION,
            reason=(
                "timezone conversion applied; no independently-verified reference-clock pair "
                "was supplied, so the recorder's absolute clock accuracy is not confirmed"
            ),
            original_timestamp=original_timestamp,
            source_timezone=source_timezone,
            source_timezone_basis=source_timezone_basis,
            normalized_timestamp=normalized_no_offset,
            warnings=warnings,
        )

    reference_timestamp = reference.reference_timestamp
    if reference_timestamp.tzinfo is None:
        if reference.reference_timezone is None:
            warnings.append(
                "reference_timestamp is timezone-naive and reference has no reference_timezone; "
                "the reference was ignored and only timezone conversion was applied"
            )
            return NormalizationResult(
                source=source,
                status=NormalizationStatus.UNVERIFIED,
                method=NormalizationMethod.TIMEZONE_CONVERSION,
                reason=(
                    "a reference was supplied but could not be interpreted (no timezone); "
                    "falling back to timezone conversion only"
                ),
                original_timestamp=original_timestamp,
                source_timezone=source_timezone,
                source_timezone_basis=source_timezone_basis,
                normalized_timestamp=normalized_no_offset,
                warnings=warnings,
            )
        try:
            reference_aware = attach_timezone(reference_timestamp, reference.reference_timezone)
        except UnknownTimezoneError as exc:
            warnings.append(f"reference_timezone could not be resolved: {exc}")
            return NormalizationResult(
                source=source,
                status=NormalizationStatus.UNVERIFIED,
                method=NormalizationMethod.TIMEZONE_CONVERSION,
                reason=(
                    "a reference was supplied but its timezone was invalid; falling back to "
                    "timezone conversion only"
                ),
                original_timestamp=original_timestamp,
                source_timezone=source_timezone,
                source_timezone_basis=source_timezone_basis,
                normalized_timestamp=normalized_no_offset,
                warnings=warnings,
            )
    else:
        reference_aware = reference_timestamp

    try:
        offset_result = compute_offset(source_aware, reference_aware)
    except NaiveTimestampError as exc:  # defensive: both sides are already resolved above
        return NormalizationResult(
            source=source,
            status=NormalizationStatus.UNVERIFIED,
            method=NormalizationMethod.TIMEZONE_CONVERSION,
            reason=f"offset calculation failed unexpectedly ({exc}); falling back to timezone "
            "conversion only",
            original_timestamp=original_timestamp,
            source_timezone=source_timezone,
            source_timezone_basis=source_timezone_basis,
            normalized_timestamp=normalized_no_offset,
            warnings=warnings,
        )

    normalized_with_offset = normalized_no_offset + timedelta(seconds=offset_result.offset_seconds)

    return NormalizationResult(
        source=source,
        status=NormalizationStatus.VERIFIED,
        method=reference.method,
        reason=(
            f"clock offset of {offset_result.offset_seconds:+.3f}s computed against a reference "
            f"from {reference.reference_source!r} ({reference.reference_basis})"
        ),
        original_timestamp=original_timestamp,
        source_timezone=source_timezone,
        source_timezone_basis=source_timezone_basis,
        normalized_timestamp=normalized_with_offset,
        offset_seconds=offset_result.offset_seconds,
        reference=reference,
        warnings=warnings,
    )


def apply_verified_offset(
    original_timestamp: datetime | None,
    *,
    source: TimestampSource,
    source_timezone: str,
    source_timezone_basis: str | None,
    offset_seconds: float,
    method: NormalizationMethod,
    reference: ReferencePair,
) -> NormalizationResult:
    """Apply an already-verified clock offset to a second timestamp from the same recorder.

    A single reference pair establishes the offset for *one* specific
    recorder reading (see `normalize()`) — it must never be paired a
    second time against a *different* recorder reading from the same
    recording (e.g. calling `normalize()` independently for both
    `start_original` and `end_original` against the same
    `reference_timestamp` would silently derive two different offsets
    from one external event, which is not what that event evidences).
    Once one anchor timestamp's offset is verified, this function carries
    it forward to a second timestamp from the same clock, on the explicit
    (and stated) assumption that the recorder's clock drift over the
    short span between the two timestamps is negligible — the caller
    (`app.core.timestamp_manager`) is responsible for only invoking this
    when that assumption is reasonable (i.e. both timestamps belong to
    the same recording/session).

    Args:
        original_timestamp: The second timestamp to normalize (e.g.
            `end_original`), or `None` if unavailable.
        source: Its declared `TimestampSource`.
        source_timezone: The same IANA timezone used for the anchor
            timestamp's normalization.
        source_timezone_basis: Provenance for `source_timezone`.
        offset_seconds: The offset already verified for the anchor
            timestamp (`NormalizationResult.offset_seconds` from a prior
            `VERIFIED` call to `normalize()`).
        method: The normalization method that produced `offset_seconds`.
        reference: The reference pair that produced `offset_seconds`,
            carried through for provenance only — not re-compared here.

    Returns:
        A `NormalizationResult` with `status=VERIFIED`, or `UNKNOWN` if
        `original_timestamp` is `None`.
    """
    if original_timestamp is None:
        return NormalizationResult(
            source=source,
            status=NormalizationStatus.UNKNOWN,
            method=NormalizationMethod.NONE,
            reason="no original timestamp value is available for this source",
            original_timestamp=None,
        )

    if original_timestamp.tzinfo is None:
        try:
            source_aware = attach_timezone(original_timestamp, source_timezone)
        except UnknownTimezoneError as exc:
            return NormalizationResult(
                source=source,
                status=NormalizationStatus.UNKNOWN,
                method=NormalizationMethod.NONE,
                reason=f"source_timezone could not be resolved: {exc}",
                original_timestamp=original_timestamp,
                source_timezone=source_timezone,
                source_timezone_basis=source_timezone_basis,
            )
    else:
        source_aware = original_timestamp

    normalized = to_utc(source_aware) + timedelta(seconds=offset_seconds)
    return NormalizationResult(
        source=source,
        status=NormalizationStatus.VERIFIED,
        method=method,
        reason=(
            f"clock offset of {offset_seconds:+.3f}s, verified from a paired reference against "
            f"another timestamp in this same recording ({reference.reference_source!r}: "
            f"{reference.reference_basis}), applied here on the assumption of negligible clock "
            "drift over this recording's own short duration"
        ),
        original_timestamp=original_timestamp,
        source_timezone=source_timezone,
        source_timezone_basis=source_timezone_basis,
        normalized_timestamp=normalized,
        offset_seconds=offset_seconds,
        reference=reference,
    )

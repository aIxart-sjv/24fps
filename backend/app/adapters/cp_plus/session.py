"""
CP Plus multi-file session linking (Phase 8 implementation).

The 13-file evidence package this parser was validated against is one
continuous ~10-minute recording split into vendor-chosen segments, not 13
independent recordings (CPV_ANALYSIS_REPORT.md section 10). This module
proves/reports that relationship using the outer-header start/end counters
established in `app.adapters.cp_plus.container.parse_outer_header` — it
never assumes adjacency from filenames or list order alone.

This is deliberately a standalone function, not a new adapter method:
`app.adapters.cp_plus.CPPlusAdapter` and `CPPlusParser` are bound to a
single `EvidenceStorageReader` per the existing Phase 5/7 contract. Linking
requires comparing *multiple* files' headers, so it operates on the small,
already-extracted `CPVSegmentDescriptor` values a caller builds one at a
time (e.g. by opening each file's reader in turn, calling
`parse_outer_header`, and closing it) — never on multiple open readers at
once, and never on a full file read.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

from app.adapters.cp_plus.models import (
    CPVOuterHeader,
    CPVSegmentDescriptor,
    CPVSegmentLink,
    CPVSessionLinkResult,
    CPVSessionLinkStatus,
)


def segment_descriptor_from_header(label: str, header: CPVOuterHeader) -> CPVSegmentDescriptor:
    """Build a `CPVSegmentDescriptor` from one file's parsed outer header.

    Args:
        label: Caller-chosen identifier for the segment (e.g. its filename).
        header: The result of `container.parse_outer_header` for that file.

    Returns:
        A `CPVSegmentDescriptor`. `readable` is `False` (and both counters
        `None`) if the header's magic did not validate or a counter could
        not be read — never a guessed counter value.
    """
    if not header.magic_valid or header.start_counter is None or header.end_counter is None:
        return CPVSegmentDescriptor(
            label=label, start_counter=None, end_counter=None, readable=False
        )
    return CPVSegmentDescriptor(
        label=label,
        start_counter=header.start_counter,
        end_counter=header.end_counter,
        readable=True,
    )


def _link_pair(previous: CPVSegmentDescriptor, current: CPVSegmentDescriptor) -> CPVSegmentLink:
    if not previous.readable or not current.readable:
        return CPVSegmentLink(
            previous_label=previous.label,
            next_label=current.label,
            status=CPVSessionLinkStatus.UNKNOWN,
            detail=(
                f"{previous.label!r} readable={previous.readable}, "
                f"{current.label!r} readable={current.readable}; counters not comparable"
            ),
        )

    # mypy: readable already guarantees both counters are non-None.
    prev_start, prev_end = previous.start_counter, previous.end_counter
    cur_start, cur_end = current.start_counter, current.end_counter
    assert prev_start is not None and prev_end is not None
    assert cur_start is not None and cur_end is not None

    if prev_start == cur_start and prev_end == cur_end:
        return CPVSegmentLink(
            previous_label=previous.label,
            next_label=current.label,
            status=CPVSessionLinkStatus.DUPLICATE,
            detail=(
                f"{previous.label!r} and {current.label!r} report an identical counter pair "
                f"(start={prev_start}, end={prev_end})"
            ),
        )

    if cur_start == prev_end:
        return CPVSegmentLink(
            previous_label=previous.label,
            next_label=current.label,
            status=CPVSessionLinkStatus.CONTINUOUS,
            detail=f"{current.label!r} start counter ({cur_start}) equals {previous.label!r}'s end counter",
        )

    if cur_start > prev_end:
        return CPVSegmentLink(
            previous_label=previous.label,
            next_label=current.label,
            status=CPVSessionLinkStatus.MISSING_SEGMENT,
            detail=(
                f"gap of {cur_start - prev_end} counter unit(s) between {previous.label!r}'s end "
                f"({prev_end}) and {current.label!r}'s start ({cur_start}); no supplied segment "
                "covers that range"
            ),
        )

    return CPVSegmentLink(
        previous_label=previous.label,
        next_label=current.label,
        status=CPVSessionLinkStatus.DISCONTINUITY,
        detail=(
            f"{current.label!r} start counter ({cur_start}) is before {previous.label!r}'s end "
            f"counter ({prev_end}); overlap or out-of-order segment"
        ),
    )


def link_cpv_session(segments: Sequence[CPVSegmentDescriptor]) -> CPVSessionLinkResult:
    """Link an ordered sequence of CPV segment descriptors into one session.

    Args:
        segments: Segment descriptors in the caller-asserted playback
            order (e.g. sorted by filename). This function does not
            reorder them — order is provenance the caller is responsible
            for (typically the export filenames' own start timestamps).

    Returns:
        A `CPVSessionLinkResult` covering every adjacent pair. With fewer
        than 2 segments, `links` is empty and `overall_status` is
        `CONTINUOUS` (there is nothing to be discontinuous with) unless
        the single segment itself is unreadable, in which case it is
        `UNKNOWN`.
    """
    segments = list(segments)
    if len(segments) < 2:
        overall = (
            CPVSessionLinkStatus.CONTINUOUS
            if segments and segments[0].readable
            else CPVSessionLinkStatus.UNKNOWN
        )
        warnings = (
            [] if segments and segments[0].readable else ["fewer than 2 readable segments supplied"]
        )
        return CPVSessionLinkResult(
            segments=tuple(segments), links=(), overall_status=overall, warnings=tuple(warnings)
        )

    links = [_link_pair(prev, cur) for prev, cur in pairwise(segments)]
    statuses = {link.status for link in links}

    if statuses == {CPVSessionLinkStatus.CONTINUOUS}:
        overall = CPVSessionLinkStatus.CONTINUOUS
    elif CPVSessionLinkStatus.UNKNOWN in statuses and len(statuses) == 1:
        overall = CPVSessionLinkStatus.UNKNOWN
    elif CPVSessionLinkStatus.MISSING_SEGMENT in statuses:
        overall = CPVSessionLinkStatus.MISSING_SEGMENT
    elif CPVSessionLinkStatus.DUPLICATE in statuses:
        overall = CPVSessionLinkStatus.DUPLICATE
    else:
        overall = CPVSessionLinkStatus.DISCONTINUITY

    warnings = [link.detail for link in links if link.status != CPVSessionLinkStatus.CONTINUOUS]

    return CPVSessionLinkResult(
        segments=tuple(segments),
        links=tuple(links),
        overall_status=overall,
        warnings=tuple(warnings),
    )

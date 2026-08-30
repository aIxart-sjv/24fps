"""Tests for CP Plus multi-file session linking (app/adapters/cp_plus/session.py).

Phase 8 real-parser implementation. Isolated status-classification cases
(CONTINUOUS/MISSING_SEGMENT/DISCONTINUITY/DUPLICATE/UNKNOWN) use small,
hand-built `CPVSegmentDescriptor` values — these are pure logic tests, not
a fabricated CP Plus structure claim, since the descriptors are exactly
what `container.parse_outer_header` + `segment_descriptor_from_header`
would produce from real bytes. The main claim this module makes — "the 13
real evidence files form one continuous session" — is proven against the
real evidence in `test_real_all_13_segments_link_as_one_continuous_session`
below and in test_cp_plus_real_evidence_integration.py.
"""

from __future__ import annotations

from app.acquisition.storage_reader import FileBackedReader
from app.adapters.cp_plus.container import parse_outer_header
from app.adapters.cp_plus.models import CPVSegmentDescriptor, CPVSessionLinkStatus
from app.adapters.cp_plus.session import link_cpv_session, segment_descriptor_from_header
from tests.fixtures.cp_plus_evidence import real_cpv_paths, requires_real_evidence


def _seg(
    label: str, start: int | None, end: int | None, readable: bool = True
) -> CPVSegmentDescriptor:
    return CPVSegmentDescriptor(
        label=label, start_counter=start, end_counter=end, readable=readable
    )


# --- pairwise status classification (synthetic, isolated logic cases) ---


def test_two_continuous_segments():
    result = link_cpv_session([_seg("a", 0, 10), _seg("b", 10, 25)])
    assert result.overall_status == CPVSessionLinkStatus.CONTINUOUS
    assert result.links[0].status == CPVSessionLinkStatus.CONTINUOUS
    assert result.warnings == ()


def test_missing_segment_gap_between_segments():
    result = link_cpv_session([_seg("a", 0, 10), _seg("b", 15, 25)])
    assert result.overall_status == CPVSessionLinkStatus.MISSING_SEGMENT
    assert result.links[0].status == CPVSessionLinkStatus.MISSING_SEGMENT
    assert "gap of 5" in result.links[0].detail


def test_discontinuity_on_overlap_or_out_of_order():
    result = link_cpv_session([_seg("a", 0, 20), _seg("b", 10, 30)])
    assert result.overall_status == CPVSessionLinkStatus.DISCONTINUITY
    assert result.links[0].status == CPVSessionLinkStatus.DISCONTINUITY


def test_duplicate_segment_pair():
    result = link_cpv_session([_seg("a", 0, 10), _seg("b", 0, 10)])
    assert result.overall_status == CPVSessionLinkStatus.DUPLICATE
    assert result.links[0].status == CPVSessionLinkStatus.DUPLICATE


def test_unknown_when_a_segment_is_unreadable():
    result = link_cpv_session([_seg("a", 0, 10), _seg("b", None, None, readable=False)])
    assert result.links[0].status == CPVSessionLinkStatus.UNKNOWN


def test_single_readable_segment_is_continuous_by_definition():
    result = link_cpv_session([_seg("a", 0, 10)])
    assert result.overall_status == CPVSessionLinkStatus.CONTINUOUS
    assert result.links == ()


def test_single_unreadable_segment_is_unknown():
    result = link_cpv_session([_seg("a", None, None, readable=False)])
    assert result.overall_status == CPVSessionLinkStatus.UNKNOWN


def test_empty_segment_list_is_unknown():
    result = link_cpv_session([])
    assert result.overall_status == CPVSessionLinkStatus.UNKNOWN
    assert result.segments == ()


def test_three_segment_chain_with_one_gap_reports_mixed_links():
    result = link_cpv_session([_seg("a", 0, 10), _seg("b", 10, 20), _seg("c", 25, 30)])
    assert [link.status for link in result.links] == [
        CPVSessionLinkStatus.CONTINUOUS,
        CPVSessionLinkStatus.MISSING_SEGMENT,
    ]
    assert result.overall_status == CPVSessionLinkStatus.MISSING_SEGMENT


# --- segment_descriptor_from_header ---


def test_segment_descriptor_from_header_unreadable_when_magic_invalid():
    from app.adapters.cp_plus.models import CPVOuterHeader

    header = CPVOuterHeader(
        magic_valid=False,
        version_field=b"",
        start_counter=None,
        end_counter=None,
        reserved_all_zero=None,
        bytes_read=0,
    )
    descriptor = segment_descriptor_from_header("x", header)
    assert descriptor.readable is False
    assert descriptor.start_counter is None


# --- real evidence: the actual multi-file session claim ---


@requires_real_evidence
def test_real_all_13_segments_link_as_one_continuous_session():
    paths = real_cpv_paths()
    assert len(paths) == 13

    descriptors = []
    for path in paths:
        with FileBackedReader(path) as reader:
            header = parse_outer_header(reader)
        descriptors.append(segment_descriptor_from_header(path.name, header))

    assert all(d.readable for d in descriptors)

    result = link_cpv_session(descriptors)

    assert result.overall_status == CPVSessionLinkStatus.CONTINUOUS
    assert len(result.links) == 12
    assert all(link.status == CPVSessionLinkStatus.CONTINUOUS for link in result.links)
    assert result.warnings == ()


@requires_real_evidence
def test_real_subset_of_segments_reports_missing_segment():
    """Demonstrates a PARTIAL session using a real (not fabricated) gap.

    Dropping real segments 2 and 4 from the ordered list produces a
    genuinely incomplete session — the descriptors are real bytes from
    real files, only the *selection* is deliberately partial.
    """
    paths = real_cpv_paths()
    assert len(paths) == 13
    subset = [paths[0], paths[2], paths[4]]  # skip index 1 and 3

    descriptors = []
    for path in subset:
        with FileBackedReader(path) as reader:
            header = parse_outer_header(reader)
        descriptors.append(segment_descriptor_from_header(path.name, header))

    result = link_cpv_session(descriptors)

    assert result.overall_status == CPVSessionLinkStatus.MISSING_SEGMENT
    assert all(link.status == CPVSessionLinkStatus.MISSING_SEGMENT for link in result.links)

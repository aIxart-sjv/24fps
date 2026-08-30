"""
Standardized PDF report rendering (Phase 18).
Master Specification Section 43 ("Reporting Engine"): "produces...
human-readable PDF." Section 44 ("Forensic Report Content") gives the
recommended section list this module follows.

Pure with respect to case state: takes an already-assembled `ReportData`
(see `app.reporting.evidence_report`) and renders PDF bytes with
ReportLab. No DB access, no HTTP -- this module never queries anything
itself, it only lays out what `ReportData` already contains. It never
dumps raw JSON into the PDF; every section is rendered as headings,
explicit status text, and tables.

============================================================================
REPRODUCIBILITY
============================================================================
`SimpleDocTemplate(..., invariant=1)` asks ReportLab to omit its default
wall-clock `/CreationDate`/`/ModDate` and randomized document ID, and
`title`/`author`/`subject`/`creator` are set to fixed, content-derived
strings rather than anything environment-specific -- see
`tests/test_pdf_report.py` for an explicit byte-for-byte reproducibility
check across two renders of identical `ReportData`. If a future ReportLab
version changes this behavior, that test will fail loudly rather than
silently claiming reproducibility that no longer holds (task Phase 18
scope section 22: document the limitation rather than pretend).
"""

from __future__ import annotations

import io
from collections.abc import Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.reporting.evidence_report import ReportData

__all__ = ["render_pdf"]

_STYLES = getSampleStyleSheet()
_TITLE_STYLE = ParagraphStyle(
    "ReportTitle", parent=_STYLES["Title"], fontSize=18, spaceAfter=6 * mm
)
_HEADING_STYLE = ParagraphStyle(
    "ReportHeading",
    parent=_STYLES["Heading2"],
    spaceBefore=6 * mm,
    spaceAfter=2 * mm,
)
_BODY_STYLE = _STYLES["BodyText"]
_SMALL_STYLE = ParagraphStyle("ReportSmall", parent=_STYLES["BodyText"], fontSize=8, leading=10)
_WARNING_STYLE = ParagraphStyle(
    "ReportWarning", parent=_STYLES["BodyText"], textColor=colors.HexColor("#8a1f11")
)

_TABLE_STYLE = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdbdbd")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
    ]
)


def _p(text: str, style: ParagraphStyle = _BODY_STYLE) -> Paragraph:
    return Paragraph(text, style)


def _cell(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _table(headers: list[str], rows: Sequence[Sequence[object]]) -> Table:
    data: list[list[object]] = [[_p(h, _SMALL_STYLE) for h in headers]]
    for row in rows:
        data.append([_p(_cell(v), _SMALL_STYLE) for v in row])
    table = Table(data, repeatRows=1)
    table.setStyle(_TABLE_STYLE)
    return table


def _section_heading(title: str) -> Paragraph:
    return Paragraph(title, _HEADING_STYLE)


def _empty_notice(text: str) -> Paragraph:
    return Paragraph(f"<i>{text}</i>", _BODY_STYLE)


def render_pdf(data: ReportData) -> bytes:
    """Render `data` as a standardized, human-readable PDF.

    Args:
        data: The assembled report content.

    Returns:
        PDF file bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=f"24FPS Forensic Report — {data.metadata.case_identifier}",
        author="24FPS Forensic Analysis Platform",
        subject=f"Standardized forensic report for case {data.metadata.case_identifier}",
        creator="24FPS ReportManager",
        invariant=1,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    story: list[object] = []
    story.append(_p("24FPS Forensic Analysis Report", _TITLE_STYLE))
    story.append(
        _p(
            f"Case: {data.metadata.case_identifier} (id={data.metadata.case_id}) &nbsp;|&nbsp; "
            f"Report schema version: {data.metadata.report_schema_version} &nbsp;|&nbsp; "
            f"Software version: {_cell(data.metadata.software_version)} &nbsp;|&nbsp; "
            f"Generated: {data.metadata.generated_at}"
        )
    )
    story.append(Spacer(1, 4 * mm))

    _render_case_section(story, data)
    _render_evidence_section(story, data)
    _render_acquisition_section(story, data)
    _render_identification_section(story, data)
    _render_recordings_section(story, data)
    _render_recovery_section(story, data)
    _render_timeline_section(story, data)
    _render_correlation_section(story, data)
    _render_ai_section(story, data)
    _render_validation_section(story, data)
    _render_provenance_section(story, data)
    _render_audit_section(story, data)
    _render_blockchain_section(story, data)
    _render_limitations_section(story, data)

    doc.build(story)
    return buffer.getvalue()


def _render_case_section(story: list[object], data: ReportData) -> None:
    case = data.case
    story.append(_section_heading("1. Case Information"))
    rows: list[list[object]] = [
        ["Case identifier", case.case_identifier],
        ["Case number", case.case_number],
        ["Name", case.name],
        ["Description", case.description],
        ["Examiner", case.examiner],
        ["Status", case.status],
        ["Created", case.created_at],
        ["Updated", case.updated_at],
        ["Evidence items", case.evidence_count],
        ["Recordings", case.recording_count],
        ["Recovery results", case.recovery_result_count],
        ["AI detections", case.ai_result_count],
        ["AI tracks", case.ai_track_count],
        ["Motion events", case.motion_event_count],
        ["Validation metrics", case.validation_metric_count],
        ["Timeline events", case.timeline_event_count],
        ["Correlation events", case.correlation_event_count],
        ["Processing/provenance events", case.processing_event_count],
        ["Blockchain anchors", case.blockchain_anchor_count],
        ["Reports generated (including this one)", case.report_count],
    ]
    story.append(_table(["Field", "Value"], rows))


def _render_evidence_section(story: list[object], data: ReportData) -> None:
    story.append(_section_heading("2. Evidence Inventory"))
    if not data.evidence:
        story.append(_empty_notice("No evidence items are registered for this case."))
        return
    for item in data.evidence:
        block: list[object] = [
            _p(
                f"<b>Evidence {item.evidence_identifier}</b> (id={item.evidence_id}, "
                f"source_type={item.source_type}, status={item.status})"
            )
        ]
        rows: list[list[object]] = [
            ["Source description", item.source_description],
            ["Registered", item.created_at],
            ["Artifacts", item.artifact_count],
            ["Recordings", item.recording_count],
        ]
        block.append(_table(["Field", "Value"], rows))
        if item.hashes:
            hash_rows = [
                [h.algorithm, h.hash_value, h.verification_status, h.calculated_at]
                for h in item.hashes
            ]
            block.append(
                _table(["Algorithm", "Hash", "Verification status", "Calculated"], hash_rows)
            )
        else:
            block.append(_empty_notice("No hashes recorded for this evidence item."))
        story.append(KeepTogether(block))
        story.append(Spacer(1, 2 * mm))


def _render_acquisition_section(story: list[object], data: ReportData) -> None:
    story.append(_section_heading("3. Acquisition / Storage Image Information"))
    if not data.acquisition:
        story.append(_empty_notice("No evidence items to report acquisition information for."))
        return
    rows = []
    any_present = False
    for a in data.acquisition:
        if not a.storage_present:
            rows.append([a.evidence_id, "no imaged storage device (native export)"] + [None] * 6)
            continue
        any_present = True
        rows.append(
            [
                a.evidence_id,
                a.manufacturer,
                a.model,
                a.capacity_bytes,
                a.image_format,
                a.read_only,
                a.status,
                a.image_path,
            ]
        )
    if not any_present:
        story.append(
            _empty_notice("No evidence item in this case has an imaged storage device on record.")
        )
    story.append(
        _table(
            [
                "Evidence ID",
                "Manufacturer",
                "Model",
                "Capacity (bytes)",
                "Image format",
                "Read-only",
                "Status",
                "Image path",
            ],
            rows,
        )
    )


def _render_identification_section(story: list[object], data: ReportData) -> None:
    story.append(_section_heading("4. Device Identification"))
    if not data.identification:
        story.append(_empty_notice("No evidence items to report identification for."))
        return
    rows = []
    for entry in data.identification:
        if not entry.device_present:
            rows.append([entry.evidence_id, "not identified", None, None, None, None, None])
            continue
        rows.append(
            [
                entry.evidence_id,
                entry.vendor,
                entry.model,
                entry.firmware,
                entry.device_type,
                entry.camera_count,
                entry.confidence,
            ]
        )
    story.append(
        _table(
            [
                "Evidence ID",
                "Vendor",
                "Model",
                "Firmware",
                "Device type",
                "Cameras",
                "Confidence",
            ],
            rows,
        )
    )


def _render_recordings_section(story: list[object], data: ReportData) -> None:
    story.append(_section_heading("5. Recordings"))
    if not data.recordings:
        story.append(_empty_notice("No recordings are registered for this case."))
        return
    story.append(
        _p(
            "The H.265 master artifact (or the original CPV source) is the authoritative "
            "recording. An H.264 preview artifact, where present, exists only for "
            "convenience/compatibility playback and is never authoritative."
        )
    )
    rows = [
        [
            r.recording_identifier,
            r.camera_id,
            r.start_normalized or r.start_original,
            r.duration_ms,
            r.codec,
            r.recovery_status,
            r.master_artifact_path,
            "yes" if r.preview_artifact_id is not None else "no",
        ]
        for r in data.recordings
    ]
    story.append(
        _table(
            [
                "Recording",
                "Camera",
                "Start (normalized)",
                "Duration (ms)",
                "Codec",
                "Recovery status",
                "Master artifact path",
                "Preview exists",
            ],
            rows,
        )
    )


def _render_recovery_section(story: list[object], data: ReportData) -> None:
    story.append(_section_heading("6. Recovery"))
    if not data.recovery:
        story.append(_empty_notice("No recovery results are recorded for this case."))
        return
    rows = [
        [
            rr.recovery_result_id,
            rr.recording_id,
            rr.method,
            rr.status,
            rr.frames_recovered,
            rr.frames_expected,
            rr.confidence,
            rr.validation_state.upper(),
        ]
        for rr in data.recovery
    ]
    story.append(
        _table(
            [
                "Result ID",
                "Recording ID",
                "Method",
                "Status",
                "Frames recovered",
                "Frames expected",
                "Confidence",
                "Validation state",
            ],
            rows,
        )
    )


def _render_timeline_section(story: list[object], data: ReportData) -> None:
    story.append(_section_heading("7. Timeline"))
    if not data.timeline:
        story.append(_empty_notice("No timeline events are recorded for this case."))
        return
    rows = [
        [
            t.event_id,
            t.event_type,
            t.camera_id,
            t.normalized_timestamp or t.original_timestamp,
            t.source,
            t.confidence,
        ]
        for t in data.timeline
    ]
    story.append(
        _table(
            ["Event ID", "Type", "Camera", "Timestamp (normalized)", "Source", "Confidence"], rows
        )
    )


def _render_correlation_section(story: list[object], data: ReportData) -> None:
    story.append(_section_heading("8. Cross-Camera Correlation"))
    story.append(
        _p(
            "Correlation identifies temporally/spatially related events across cameras. "
            "It does not, by itself, confirm identity."
        )
    )
    if not data.correlation:
        story.append(_empty_notice("No correlated events are recorded for this case."))
        return
    rows = [
        [
            c.correlated_event_id,
            ", ".join(str(i) for i in c.contributing_event_ids),
            ", ".join(c.camera_ids),
            c.normalized_timestamp,
            c.confidence,
        ]
        for c in data.correlation
    ]
    story.append(
        _table(
            ["Correlated event ID", "Contributing event IDs", "Cameras", "Timestamp", "Confidence"],
            rows,
        )
    )


def _render_ai_section(story: list[object], data: ReportData) -> None:
    story.append(_section_heading("9. AI Analysis"))
    story.append(
        _p(
            "AI results are automated analytical output. Face detections identify the "
            "presence of a face; they are not identity recognition. No confidence value "
            "below was recalculated for this report."
        )
    )
    if data.ai.detections:
        rows = [
            [
                d.detection_id,
                d.recording_id,
                d.analysis_type,
                d.class_name,
                round(d.confidence, 3),
                d.frame_number,
                f"{d.model_name} {d.model_version}",
            ]
            for d in data.ai.detections
        ]
        story.append(
            _table(
                ["ID", "Recording", "Type", "Class", "Confidence", "Frame", "Model"],
                rows,
            )
        )
    else:
        story.append(_empty_notice("No AI detections are recorded for this case."))

    if data.ai.tracks:
        rows = [
            [
                t.track_id_db,
                t.recording_id,
                t.camera_id,
                t.class_name,
                t.frame_count,
                round(t.average_confidence, 3),
            ]
            for t in data.ai.tracks
        ]
        story.append(Spacer(1, 2 * mm))
        story.append(
            _table(["Track ID", "Recording", "Camera", "Class", "Frames", "Avg confidence"], rows)
        )

    if data.ai.motion_events:
        rows = [
            [
                m.motion_event_id,
                m.recording_id,
                m.camera_id,
                m.start_time,
                m.end_time,
                m.score,
                m.method,
            ]
            for m in data.ai.motion_events
        ]
        story.append(Spacer(1, 2 * mm))
        story.append(
            _table(["Motion ID", "Recording", "Camera", "Start", "End", "Score", "Method"], rows)
        )


def _render_validation_section(story: list[object], data: ReportData) -> None:
    story.append(_section_heading("10. Validation"))
    if not data.validation:
        story.append(_empty_notice("No validation metrics are recorded for this case."))
        return
    rows = [
        [
            v.metric_id,
            v.dataset_id,
            v.validation_type,
            v.metric_name,
            v.metric_value,
            v.evidence_kind.upper().replace("_", " "),
        ]
        for v in data.validation
    ]
    story.append(_table(["ID", "Dataset", "Type", "Metric", "Value", "Evidence kind"], rows))
    story.append(
        _p(
            "CONTROLLED/SYNTHETIC metrics describe measured performance on a controlled "
            "or synthetic dataset, not production real-world accuracy.",
            _SMALL_STYLE,
        )
    )


def _render_provenance_section(story: list[object], data: ReportData) -> None:
    story.append(_section_heading("11. Provenance / Processing History"))
    if not data.provenance:
        story.append(_empty_notice("No processing events are recorded for this case."))
        return
    rows = [
        [p.event_id, p.operation, p.actor, p.actor_type, p.tool, p.status, p.completed_at]
        for p in data.provenance
    ]
    story.append(
        _table(["ID", "Operation", "Actor", "Actor type", "Tool", "Status", "Completed"], rows)
    )


def _render_audit_section(story: list[object], data: ReportData) -> None:
    story.append(_section_heading("12. Hash-Linked Audit Chain"))
    audit = data.audit
    status_text = "VALID" if audit.valid else "INVALID"
    style = _BODY_STYLE if audit.valid else _WARNING_STYLE
    story.append(_p(f"Chain {audit.chain_id}: <b>{status_text}</b>", style))
    rows: list[list[object]] = [
        ["Chain scope", audit.chain_scope],
        ["Algorithm", audit.chain_algorithm],
        ["Event count", audit.event_count],
        ["First event ID", audit.first_event_id],
        ["Last event ID", audit.last_event_id],
        ["Checked at", audit.checked_at],
    ]
    if not audit.valid:
        rows.append(["First invalid event", audit.failure_event_id])
        rows.append(["Failure reason", audit.failure_reason])
        rows.append(["Failure detail", audit.failure_detail])
    story.append(_table(["Field", "Value"], rows))


def _render_blockchain_section(story: list[object], data: ReportData) -> None:
    story.append(_section_heading("13. Blockchain Anchors"))
    if not data.blockchain:
        story.append(_empty_notice("No blockchain anchors are recorded for this case."))
        return
    rows = []
    for a in data.blockchain:
        network_label = "REAL NETWORK" if a.is_real_network else "LOCAL/TEST PROVIDER"
        rows.append(
            [
                a.anchor_id,
                a.provider,
                network_label,
                a.status,
                a.transaction_reference,
                a.created_at,
                a.verified_at,
            ]
        )
    story.append(
        _table(
            [
                "Anchor ID",
                "Provider",
                "Network kind",
                "Status",
                "Transaction reference",
                "Created",
                "Last verified",
            ],
            rows,
        )
    )
    story.append(
        _p(
            "A LOCAL/TEST PROVIDER anchor is not a real public blockchain transaction.",
            _SMALL_STYLE,
        )
    )


def _render_limitations_section(story: list[object], data: ReportData) -> None:
    story.append(_section_heading("14. Limitations"))
    if not data.limitations:
        story.append(_empty_notice("No limitations were identified for this report's content."))
        return
    for limitation in data.limitations:
        story.append(_p(f"<b>[{limitation.category.upper()}]</b> {limitation.description}"))

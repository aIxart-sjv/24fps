"""Tests for app/reporting/pdf_report.py (Phase 18). Uses `pypdf` (a
dev-only test dependency) to actually parse the generated PDF and
inspect its extracted text, rather than only checking "file exists".
"""

from __future__ import annotations

import io

import pytest
from pypdf import PdfReader

from app.reporting.evidence_report import assemble_report_data
from app.reporting.pdf_report import render_pdf
from app.schemas.case import CaseCreateRequest
from app.storage.db import Base
from tests.fixtures.report_case import build_rich_case


@pytest.fixture
def db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _extract_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_render_pdf_produces_non_empty_valid_pdf(db) -> None:
    rich = build_rich_case(db)
    data = assemble_report_data(db, rich.case, software_version="0.1.0")
    pdf_bytes = render_pdf(data)

    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF-")

    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1


def test_render_pdf_contains_case_and_report_identifiers(db) -> None:
    rich = build_rich_case(db)
    data = assemble_report_data(db, rich.case, software_version="0.1.0")
    text = _extract_text(render_pdf(data))

    assert rich.case.case_id in text
    assert "Case Information" in text


def test_render_pdf_contains_evidence_reference(db) -> None:
    rich = build_rich_case(db)
    data = assemble_report_data(db, rich.case, software_version="0.1.0")
    text = _extract_text(render_pdf(data))

    assert rich.evidence.evidence_id in text


def test_render_pdf_represents_audit_status(db) -> None:
    rich = build_rich_case(db)
    data = assemble_report_data(db, rich.case, software_version="0.1.0")
    text = _extract_text(render_pdf(data))

    assert "Audit Chain" in text
    assert "VALID" in text


def test_render_pdf_represents_blockchain_status(db) -> None:
    rich = build_rich_case(db)
    data = assemble_report_data(db, rich.case, software_version="0.1.0")
    text = _extract_text(render_pdf(data))

    assert "Blockchain Anchors" in text
    assert "LOCAL/TEST PROVIDER" in text
    assert "not a real public blockchain transaction" in text


def test_render_pdf_never_claims_local_test_is_real_network(db) -> None:
    rich = build_rich_case(db)
    data = assemble_report_data(db, rich.case, software_version="0.1.0")
    text = _extract_text(render_pdf(data))

    # A local/test anchor row must never be labeled REAL NETWORK.
    assert "REAL NETWORK" not in text


def test_render_pdf_contains_limitations_section(db) -> None:
    rich = build_rich_case(db)
    data = assemble_report_data(db, rich.case, software_version="0.1.0")
    text = _extract_text(render_pdf(data))

    assert "Limitations" in text
    for limitation in data.limitations:
        assert limitation.category.upper() in text


def test_render_pdf_does_not_dump_raw_json(db) -> None:
    rich = build_rich_case(db)
    data = assemble_report_data(db, rich.case, software_version="0.1.0")
    text = _extract_text(render_pdf(data))

    # Raw JSON-shaped output would contain literal braces/quotes framing
    # the whole document; a structured PDF should not.
    assert '{"metadata"' not in text
    assert '": "' not in text


def test_render_pdf_is_reproducible_for_identical_content(db) -> None:
    rich = build_rich_case(db)
    data = assemble_report_data(db, rich.case, software_version="0.1.0")
    pdf1 = render_pdf(data)
    pdf2 = render_pdf(data)
    assert pdf1 == pdf2


def test_render_pdf_changes_when_content_changes(db) -> None:
    rich = build_rich_case(db)
    data1 = assemble_report_data(db, rich.case, software_version="0.1.0")

    case2 = build_rich_case(db, case_id="CASE-REPORT-2").case
    data2 = assemble_report_data(db, case2, software_version="0.1.0")

    assert render_pdf(data1) != render_pdf(data2)


def test_render_pdf_minimal_case_still_produces_valid_pdf(db) -> None:
    from app.core.case_manager import CaseManager

    case = CaseManager.create_case(db, CaseCreateRequest(case_id="CASE-MIN-PDF", name="Minimal"))
    data = assemble_report_data(db, case, software_version="0.1.0")
    pdf_bytes = render_pdf(data)

    assert pdf_bytes.startswith(b"%PDF-")
    text = _extract_text(pdf_bytes)
    assert "No evidence items are registered" in text

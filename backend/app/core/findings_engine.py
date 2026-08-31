"""
Findings generation and deduplication (Phase 22).
Master Specification Section 57's orchestrator output feeds this module,
which turns already-computed results into `Finding` rows an officer can
review without knowing which backend API produced them.

This module never recomputes, reinterprets, or second-guesses a result --
every `_from_*` classmethod below reads fields off an already-persisted
row (`RecoveryResult`, `EvidenceHash`, ...) or an already-returned
dataclass (`RecordingNormalizationOutcome`, `ChainVerificationResult`,
...) and only ever *describes* it. Every description is deliberately
hedged (task Phase 22 scope, "Important Forensic Language"): an anomaly
is reported as an anomaly, never promoted to "tampering", "identity", or
"guilt".

Deduplication (task Phase 22 scope, "Finding Deduplication"): before
inserting, `_upsert` looks for an existing, still-open finding with the
identical `(case_id, finding_type, evidence_id, recording_id)` scope and
merges into it (bumping `occurrence_count`, extending
`source_reference`, refreshing `updated_at`) rather than creating a
near-duplicate row. A finding that has already moved to `RESOLVED`/
`DISMISSED` is left alone -- a fresh occurrence of the same condition
opens a *new* finding rather than silently reopening a closed one.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Finding, FindingConfidence, FindingSeverity, FindingStatus, FindingType

__all__ = ["FindingsEngine"]

_OPEN_STATUSES = (
    FindingStatus.OPEN.value,
    FindingStatus.ACKNOWLEDGED.value,
    FindingStatus.IN_REVIEW.value,
)


class FindingsEngine:
    """Service layer for creating, deduplicating, and querying findings."""

    # ---- Generic upsert ---------------------------------------------------

    @staticmethod
    def upsert_finding(
        db: Session,
        *,
        case_id: int,
        finding_type: FindingType,
        severity: FindingSeverity,
        confidence: FindingConfidence,
        title: str,
        description: str,
        evidence_id: int | None = None,
        recording_id: int | None = None,
        source_job_id: int | None = None,
        source_reference: dict[str, object] | None = None,
        limitations: list[str] | None = None,
    ) -> tuple[Finding, bool]:
        """Create a finding, or merge into a matching still-open one.

        Returns:
            `(finding, is_new)` -- `is_new` is `False` when an existing
            open finding was merged into instead of a row being created;
            callers use this to avoid re-notifying for an unchanged
            condition.
        """
        existing = (
            db.query(Finding)
            .filter(
                Finding.case_id == case_id,
                Finding.finding_type == finding_type.value,
                Finding.evidence_id == evidence_id,
                Finding.recording_id == recording_id,
                Finding.status.in_(_OPEN_STATUSES),
            )
            .order_by(Finding.id.desc())
            .first()
        )
        if existing is not None:
            merged_reference = json.loads(existing.source_reference or "{}")
            for key, value in (source_reference or {}).items():
                new_items = value if isinstance(value, list) else [value]
                existing_value = merged_reference.get(key)
                combined = (
                    list(existing_value)
                    if isinstance(existing_value, list)
                    else ([existing_value] if existing_value is not None else [])
                )
                for item in new_items:
                    if item not in combined:
                        combined.append(item)
                # A single-occurrence scalar reference stays a scalar (never
                # wrapped in a list just because this code path *could*
                # merge); only a second, distinct occurrence promotes the
                # field to an accumulating list.
                merged_reference[key] = combined if len(combined) > 1 else combined[0]
            existing.source_reference = json.dumps(merged_reference) if merged_reference else None
            existing.occurrence_count += 1
            existing.updated_at = datetime.now(UTC)
            # A repeated occurrence never *lowers* the reported severity --
            # it may raise it (a condition seen again is at least as
            # worth reviewing), and description/confidence are refreshed
            # to the latest computed values.
            if _SEVERITY_RANK[severity.value] > _SEVERITY_RANK[existing.severity]:
                existing.severity = severity.value
            existing.confidence = confidence.value
            existing.description = description
            if source_job_id is not None:
                existing.source_job_id = source_job_id
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing, False

        finding = Finding(
            case_id=case_id,
            evidence_id=evidence_id,
            recording_id=recording_id,
            source_job_id=source_job_id,
            finding_type=finding_type.value,
            severity=severity.value,
            confidence=confidence.value,
            title=title,
            description=description,
            status=FindingStatus.OPEN.value,
            source_reference=json.dumps(source_reference) if source_reference else None,
            limitations=json.dumps(limitations) if limitations else None,
            occurrence_count=1,
        )
        db.add(finding)
        db.commit()
        db.refresh(finding)
        return finding, True

    # ---- Queries ------------------------------------------------------

    @staticmethod
    def list_case_findings(
        db: Session,
        case_id: int,
        *,
        status: str | None = None,
        severity: str | None = None,
    ) -> list[Finding]:
        """List a case's findings, most-severe-and-least-resolved first
        (task Phase 22 scope, "Finding Prioritization": a deterministic
        rule, never plain creation-time order).

        Rule: unresolved (`OPEN`/`ACKNOWLEDGED`/`IN_REVIEW`) before
        resolved/dismissed; within that, higher severity first; within
        that, most recently updated first. This is computed in Python
        (not SQL `ORDER BY`) so the rule stays in one readable place
        rather than a database-specific `CASE WHEN` expression.
        """
        query = db.query(Finding).filter(Finding.case_id == case_id)
        if status is not None:
            query = query.filter(Finding.status == status)
        if severity is not None:
            query = query.filter(Finding.severity == severity)
        findings = query.all()
        return sorted(findings, key=_priority_key)

    @staticmethod
    def get_finding(db: Session, finding_id: int) -> Finding | None:
        return db.query(Finding).filter(Finding.id == finding_id).first()


_SEVERITY_RANK = {
    FindingSeverity.INFO.value: 0,
    FindingSeverity.LOW.value: 1,
    FindingSeverity.MEDIUM.value: 2,
    FindingSeverity.HIGH.value: 3,
    FindingSeverity.CRITICAL.value: 4,
}

_UNRESOLVED_STATUSES = frozenset(_OPEN_STATUSES)


def _priority_key(finding: Finding) -> tuple[int, int, float]:
    unresolved_first = 0 if finding.status in _UNRESOLVED_STATUSES else 1
    severity_rank = -_SEVERITY_RANK.get(finding.severity, 0)
    recency = -finding.updated_at.timestamp()
    return (unresolved_first, severity_rank, recency)

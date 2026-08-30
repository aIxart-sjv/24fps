"""
SQLAlchemy ORM model for physical evidence custody transfers (Phase 21,
"Physical Chain of Custody + QR Handoff").

============================================================================
PHYSICAL EVIDENCE IDENTITY (task Phase 21 scope section 5)
============================================================================
`Evidence` (Phase 4) already has a unique `evidence_id`/primary key --
this model reuses it directly (`CustodyTransfer.evidence_id` is a plain
FK to `evidence.id`) rather than inventing a duplicate "physical evidence
ID". `Evidence` itself is not modified in any way by Phase 21 (task:
"Do not modify the original evidence model unnecessarily").

============================================================================
CURRENT CUSTODIAN (task Phase 21 scope section 6)
============================================================================
There is deliberately no `current_custodian` column anywhere -- not on
`Evidence`, not here. The task is explicit: "Do NOT rely only on...
with no history... Source of truth: custody history -> latest completed
handoff -> current custodian." `app.core.custody_manager.CustodyManager.
get_current_custodian` derives it by querying the latest `ACCEPTED`
`CustodyTransfer` row for an evidence item, every time -- a real,
append-only query over this table, never a mutable cached field that
could drift from history.

============================================================================
INITIAL INTAKE (task Phase 21 scope section 16)
============================================================================
`Evidence` registration (Phase 4, `EvidenceManager.register_evidence`)
captures no "received by" identity today, and this phase does not modify
it (touching a completed Phase 4 file to add a field only Phase 21 needs
is exactly the kind of scope creep the task boundary forbids). Instead,
`transfer_type=CustodyTransferType.INTAKE` is a first, self-contained
`CustodyTransfer` row: `releasing_user_id=NULL` (there is no prior human
custodian -- evidence enters the tracked chain here), `receiving_user_id`
= whoever took initial physical possession, `status=ACCEPTED` from
creation (an intake has no pending/QR step -- see `app.core.
custody_manager.CustodyManager.record_initial_custody`). This keeps
`get_current_custodian`'s query uniform (always "the latest `ACCEPTED`
row", whether that row is the intake or a real handoff) with no special
case for "no history yet".

============================================================================
HANDOFF LIFECYCLE / STATES (task Phase 21 scope sections 7-8)
============================================================================
    (current custodian initiates)
                |
                v
            PENDING  ---(releaser cancels)--> CANCELLED
                |
                |--(intended receiver scans + explicitly rejects)--> REJECTED
                |
                |--(expires_at reached before acceptance)--> EXPIRED
                |
                v
            ACCEPTED  (terminal; current custodian becomes receiving_user)

`PENDING` is the only non-terminal state; every other state is reached
exactly once and never re-transitions (task: "Never replace prior
transfers with only current-custodian state" / "Do not overwrite
history" -- each transfer row's own final state is permanent once set,
and a new handoff is always a brand-new row, never an edit of an old
one). Scanning the QR alone never changes `status` -- only an explicit
accept/reject call does (task Phase 21 scope section 8: "Scanning alone
is NOT acceptance").

============================================================================
TOKENS (task Phase 21 scope sections 9-10)
============================================================================
`token_hash` stores only `app.security.tokens.hash_token(raw_token)` --
the raw, cryptographically random token (`app.security.tokens.
generate_token`, QR-encoded) is returned to the releasing user exactly
once, at initiation, and is never persisted anywhere. `expires_at` is
fixed at creation (short-lived, configurable -- see
`app.config.Settings.custody_token_ttl_minutes`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.evidence import Evidence
    from app.models.user import User

__all__ = ["CustodyTransfer", "CustodyTransferStatus", "CustodyTransferType"]


class CustodyTransferStatus(str, Enum):
    """Controlled custody-transfer states (task Phase 21 scope section 7's
    own exact vocabulary)."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class CustodyTransferType(str, Enum):
    """Distinguishes the first, "no prior human custodian" row for an
    evidence item from every ordinary person-to-person handoff that
    follows it (see module docstring, "Initial intake")."""

    INTAKE = "intake"
    TRANSFER = "transfer"


class CustodyTransfer(Base):
    """One physical custody transfer -- either the initial intake of an
    evidence item into tracked custody, or a person-to-person handoff.

    Never updated once terminal: `status` moves from `PENDING` to exactly
    one terminal value one time; `INTAKE` rows are created already
    terminal (`ACCEPTED`). The one field this model allows updating after
    creation is `status`/`accepted_at` themselves, exactly once, via the
    atomic conditional-update pattern in `app.core.custody_manager`
    (`UPDATE ... WHERE status = 'pending'`) -- never a second, silent
    rewrite (task Phase 21 scope section 27, race-condition safety).
    """

    __tablename__ = "custody_transfers"
    __table_args__ = (
        # Task Phase 21 scope: "handle concurrent/pending transfers so
        # two transfers can't silently take ownership from the same
        # custodian" -- a DB-level constraint, not just an application
        # check, so two concurrent `initiate_handoff` calls for the same
        # evidence item cannot both insert a second PENDING row no
        # matter how the race lands (`app.core.custody_manager.
        # CustodyManager.initiate_handoff` catches the resulting
        # `IntegrityError` and reports it as an ordinary domain error).
        # The literal 'PENDING' (not 'pending') matches how
        # `native_enum=False` stores this enum -- by member *name*, not
        # `.value` -- confirmed against this table's own DDL.
        Index(
            "ix_custody_transfers_one_pending_per_evidence",
            "evidence_id",
            unique=True,
            sqlite_where=text("status = 'PENDING'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transfer_type: Mapped[CustodyTransferType] = mapped_column(
        SQLEnum(CustodyTransferType, native_enum=False),
        nullable=False,
        default=CustodyTransferType.TRANSFER,
    )
    status: Mapped[CustodyTransferStatus] = mapped_column(
        SQLEnum(CustodyTransferStatus, native_enum=False),
        nullable=False,
        default=CustodyTransferStatus.PENDING,
    )
    #: `NULL` only for `transfer_type == INTAKE` (see module docstring).
    releasing_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    receiving_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    #: SHA-256 of the raw opaque token (`app.security.tokens.hash_token`)
    #: -- `NULL` for `INTAKE` rows, which have no QR/token step at all.
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    initiated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    #: `NULL` for `INTAKE` rows (no expiry: they are created already
    #: `ACCEPTED`) and for any `PENDING` transfer not yet resolved.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Set once the completed transfer's Phase 15 `ProcessingEvent` is
    #: recorded (task Phase 21 scope section 19) -- `NULL` until then,
    #: and permanently for any transfer that never completes.
    provenance_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("processing_events.id", ondelete="SET NULL"), nullable=True
    )

    evidence: Mapped[Evidence] = relationship("Evidence")
    releasing_user: Mapped[User | None] = relationship("User", foreign_keys=[releasing_user_id])
    receiving_user: Mapped[User] = relationship("User", foreign_keys=[receiving_user_id])

    def __repr__(self) -> str:
        return (
            f"<CustodyTransfer evidence_id={self.evidence_id} "
            f"status={self.status!r} type={self.transfer_type!r}>"
        )

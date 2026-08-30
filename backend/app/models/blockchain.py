"""
SQLAlchemy ORM model for blockchain anchors (Phase 17).
Master Specification Section 42 ("Blockchain Anchoring"), Section 50's
`blockchain_anchors` table (`id`, `case_id`, `audit_state_hash`,
`network`, `transaction_reference`, `created_at`, `status`,
`verified_at`).

Fields beyond that literal table are added, each directly required by a
task Phase 17 scope instruction rather than speculative:
- `chain_id`: Section 4 ("Store an explicit chain identifier. The chain
  identifier must be deterministic and traceable to the case and audit
  chain") -- a documented table field is missing that the narrative text
  explicitly requires; `app.core.blockchain_manager.BlockchainManager`
  sets this deterministically to `f"case-{case_id}"` (Phase 16's own
  chain scope is one chain per case, so this is the natural, traceable
  identifier -- never a random value).
- `provider`: Section 5 allows an additional field for "provider/network
  identification"; `network` alone (e.g. `"local"`/`"sepolia"`) does not
  say *which* `BlockchainProvider` implementation produced/must be used
  to look up this anchor, which `verify_anchor` needs to resolve the
  right provider again later.
- `reason` and `error`: Section 5 explicitly allows fields for "error
  information", and Section 11 requires supporting multiple anchors per
  case ("periodic anchor, important-case anchor, post-review anchor,
  final-case anchor") -- `reason` is the free-text label distinguishing
  why a given anchor was created.
- `event_count`/`last_event_id`: NOT cosmetic -- required for `verify_
  anchor` to be correct at all. An anchor commits to "the chain through
  event `last_event_id`". Recording the anchoring action itself as a
  further `ProcessingEvent` (Section 23) necessarily appends *one more*
  event right after `create_anchor` finishes. Without pinning
  `last_event_id`, a later verification recomputing "the current full
  chain" would always find a mismatch immediately -- even with zero
  tampering -- because the chain has legitimately grown by that one
  bookkeeping event. Pinning to `last_event_id` makes "ANCHOR VALID
  immediately after anchoring, before any further change" (task Phase 17
  scope section 14 step 3) actually hold, while later, unrelated chain
  growth correctly does not retroactively invalidate an earlier
  checkpoint -- only edits/deletions within the anchored prefix, or a
  currently-broken overall Phase 16 chain, do.

`status` and `AnchorStatus` are the same "plain `String` column
holding a controlled-vocabulary enum's `.value`, enum defined in the
pure domain module rather than colocated here" pattern Phase 15 already
established for `ProcessingEvent.actor_type`/`.operation`
(`app.audit.events.ActorType`/`ProcessingOperation`) -- see
`app.blockchain.anchor.AnchorStatus`'s own docstring for why.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.case import Case

__all__ = ["BlockchainAnchor"]


class BlockchainAnchor(Base):
    """One recorded external anchor of a case's Phase 16 hash-linked
    audit chain state.

    Append-only by construction: `BlockchainManager.create_anchor`
    inserts a new row for every anchor and never updates
    `audit_state_hash`/`provider`/`network`/`transaction_reference`/
    `status` afterward (task Phase 17 scope section 10/11 -- a later
    anchor is always a new row, never a silent replacement of an
    earlier one). `verified_at` is the one deliberate exception:
    bookkeeping about when this anchor was last *checked*, not part of
    the anchored content itself, updated by `BlockchainManager.
    verify_anchor` on every verification attempt regardless of outcome.
    """

    __tablename__ = "blockchain_anchors"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chain_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    audit_state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    network: Mapped[str] = mapped_column(String(64), nullable=False)
    transaction_reference: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    last_event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    case: Mapped[Case] = relationship("Case", back_populates="blockchain_anchors")

    def __repr__(self) -> str:
        return (
            f"<BlockchainAnchor case_id={self.case_id} status={self.status!r} "
            f"transaction_reference={self.transaction_reference!r}>"
        )

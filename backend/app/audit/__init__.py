"""
Provenance / chain-of-custody vocabulary (Phase 15, Master Specification
Section 39 "Provenance Engine", Section 40 "Chain of Custody").

Pure, DB-free, HTTP-free package: `app.core.provenance_manager` is the
DB-aware orchestration layer built on top of it, mirroring every prior
phase's pure-engine/DB-manager split (Phase 9-14).

`app.audit.hash_chain` (Master Specification Section 41, "Hash-Linked
Audit Log") is explicitly Phase 16's territory and stays an empty stub --
not implemented, not even referenced here.
"""

from __future__ import annotations

from app.audit.chain_of_custody import CustodyEventType
from app.audit.events import ActorType, ProcessingOperation

__all__ = ["ActorType", "CustodyEventType", "ProcessingOperation"]

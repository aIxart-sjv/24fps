"""
Vendor-adapter framework (Phase 7).
Master Specification Section 16 ("Vendor Adapter Interface"), Section 92
("Third Backend Milestone").

This package is the framework only: `DVRAdapter` (the contract every
vendor adapter must satisfy) and `AdapterRegistry` (registration,
matching, selection). It contains no vendor-specific parsing — each real
vendor's implementation lives in its own `app.adapters.<vendor>`
sub-package (Phase 8+), subclassing `DVRAdapter` from here.

Boundary with Phase 6: this package depends on
`app.schemas.device.DeviceIdentificationResult` as the sole input to
adapter selection. It never imports SQLAlchemy, FastAPI, or
`app.detection` — identification stays entirely decoupled from which
adapters happen to be registered.
"""

from __future__ import annotations

from app.adapters.base import (
    AdapterCapability,
    AdapterCapabilityNotImplementedError,
    AdapterResult,
    DVRAdapter,
)
from app.adapters.registry import (
    AdapterMatchAttempt,
    AdapterRegistry,
    AdapterSelectionResult,
    AdapterSelectionStatus,
    MatchStrength,
)

__all__ = [
    "AdapterCapability",
    "AdapterCapabilityNotImplementedError",
    "AdapterMatchAttempt",
    "AdapterRegistry",
    "AdapterResult",
    "AdapterSelectionResult",
    "AdapterSelectionStatus",
    "DVRAdapter",
    "MatchStrength",
]

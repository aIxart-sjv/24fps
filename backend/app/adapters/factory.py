"""
Default `AdapterRegistry` composition (Phase 19, "Additional OEM
Adapters").

This is the one place in the codebase allowed to import every vendor
package at once -- a composition root, exactly like `app.main.create_app`
already imports every API route module to wire the application together.
It is NOT part of the generic adapter framework itself (`app.adapters.
base`/`app.adapters.registry` stay vendor-agnostic, per Master
Specification Section 16); it is a convenience for callers (and tests)
that want a fully-populated registry without hand-listing every adapter.

`app.core.recording_manager`/`app.core.recovery_manager` do NOT use this
factory -- their CP Plus dispatch remains direct and explicit, as
documented in `app.core.recording_manager`'s own module docstring. This
factory exists to prove and test the registry's own behavior (Phase 19
task scope: "Verify that: AdapterRegistry still selects CP Plus
correctly... new vendor adapters register deterministically... registry
listing accurately reports support levels/capabilities"), not to change
how recording extraction actually dispatches today.
"""

from __future__ import annotations

from app.adapters.cp_plus import CPPlusAdapter
from app.adapters.dahua import DahuaAdapter
from app.adapters.godrej import GodrejAdapter
from app.adapters.hikvision import HikvisionAdapter
from app.adapters.honeywell import HoneywellAdapter
from app.adapters.matrix import MatrixAdapter
from app.adapters.registry import AdapterRegistry
from app.adapters.tp_link import TPLinkAdapter
from app.adapters.uniview import UniviewAdapter

__all__ = ["build_default_registry"]


def build_default_registry() -> AdapterRegistry:
    """Build an `AdapterRegistry` with every vendor this codebase
    currently represents, one identity-only adapter instance each
    (Master Specification Section 17's eight NTRO-named OEMs).

    Registration order is deterministic (CP Plus first, then the other
    seven in the same order Section 17 lists them) -- meaningful because
    `AdapterRegistry.select_adapter` breaks ties between equal-strength
    matches by first-registered-wins.

    Returns:
        A freshly-built registry. Each call returns a new instance (no
        shared mutable global) -- callers that want one process-wide
        registry should cache the result themselves.
    """
    registry = AdapterRegistry()
    registry.register_adapter(CPPlusAdapter())
    registry.register_adapter(DahuaAdapter())
    registry.register_adapter(HoneywellAdapter())
    registry.register_adapter(HikvisionAdapter())
    registry.register_adapter(TPLinkAdapter())
    registry.register_adapter(GodrejAdapter())
    registry.register_adapter(UniviewAdapter())
    registry.register_adapter(MatrixAdapter())
    return registry

"""
Standardized JSON report serialization (Phase 18).
Master Specification Section 43 ("Reporting Engine"): "produces
standardized JSON."

Pure: takes an already-assembled `ReportData` (see
`app.reporting.evidence_report`) and produces deterministic, reproducible
JSON bytes. No DB, no file I/O, no HTTP.

============================================================================
DETERMINISM
============================================================================
`ReportData` and every nested section dataclass hold only JSON-primitive
values (`str`/`int`/`float`/`bool`/`None`/`list`/`dict`/`tuple`) --
`app.reporting.evidence_report` already converts every `datetime` to a
UTC ISO-8601 string and every enum to its `.value` at assembly time, so
this module never has to guess how to serialize anything itself.

Key order is the nested dataclasses' own declared field order (Python
preserves both `dataclasses.fields()` order and `dict` insertion order,
so this is fixed by the class definitions, not by runtime dict-building
order or database iteration) -- `sort_keys=False` is deliberate here,
unlike `app.audit.hash_chain.canonicalize_event`'s `sort_keys=True`.
That function's job is producing a byte-for-byte reproducible payload for
*cryptographic hashing*, where any fixed, independently-reconstructible
order works and alphabetical is the simplest to specify. This function's
job is producing a *readable, standardized report document* for a human
or downstream tool, where the logical section order (case, evidence,
acquisition, ... limitations) documented in Master Specification Section
44 is far more useful than alphabetical. Both are equally deterministic;
they simply serve different purposes and must not be confused.

`ensure_ascii=True` and explicit UTF-8 encoding keep the output stable
across environments, matching every other canonical-serialization
convention already established in this codebase (Phase 16/17).
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any

from app.reporting.evidence_report import ReportData

__all__ = ["render_json"]


def _to_plain(value: Any) -> Any:
    """Recursively convert a (possibly nested) dataclass/tuple structure
    into plain `dict`/`list` values `json.dumps` can serialize directly,
    preserving field declaration order at every level."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _to_plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (list, tuple)):
        return [_to_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_plain(item) for key, item in value.items()}
    return value


def render_json(data: ReportData) -> bytes:
    """Render `data` as standardized, deterministic JSON bytes.

    Args:
        data: The assembled report content.

    Returns:
        UTF-8-encoded JSON bytes, indented for human readability, with
        section/field order matching `ReportData`'s own declaration
        order (Master Specification Section 44's recommended section
        list).
    """
    payload = _to_plain(data)
    text = json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=True)
    return text.encode("utf-8")

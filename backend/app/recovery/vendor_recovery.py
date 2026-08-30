"""
Generic Recovery Layer 2 (vendor-specific recovery) dispatch.
Master Specification Section 16: the adapter owns "vendor-specific storage
understanding"; the common engine owns orchestration. This module is the
thin, vendor-agnostic wrapper around a `DVRAdapter`'s three recovery
methods (`find_deleted_recordings`, `recover_recording`,
`reconstruct_fragments`) — it converts the one exception the base contract
defines for "this adapter does not implement this operation"
(`AdapterCapabilityNotImplementedError`) into the same clean, structured
`AdapterResult` shape every other outcome already uses, so callers never
need a try/except around a vendor-recovery call.
"""

from __future__ import annotations

from app.adapters.base import AdapterCapabilityNotImplementedError, AdapterResult, DVRAdapter


def _not_implemented_result(adapter: DVRAdapter, operation: str, exc: Exception) -> AdapterResult:
    return AdapterResult(
        vendor=adapter.vendor,
        model=None,
        firmware=None,
        detected_format=None,
        capability_set=adapter.capabilities,
        warnings=[f"{adapter.vendor} adapter does not implement {operation}(): {exc}"],
        parser_version=adapter.adapter_version,
        confidence=0.0,
    )


def attempt_deleted_recording_search(adapter: DVRAdapter) -> AdapterResult:
    """Ask a bound adapter to search for deleted-but-referenced recordings.

    Args:
        adapter: A `DVRAdapter` bound to one evidence item's reader.

    Returns:
        The adapter's `AdapterResult`, or a clean "not implemented" result
        if this adapter has no deleted-recording search capability — never
        raises `AdapterCapabilityNotImplementedError` to the caller.
    """
    try:
        return adapter.find_deleted_recordings()
    except AdapterCapabilityNotImplementedError as exc:
        return _not_implemented_result(adapter, "find_deleted_recordings", exc)


def attempt_vendor_recovery(adapter: DVRAdapter, recording_id: str) -> AdapterResult:
    """Ask a bound adapter to recover/repair one known, damaged recording.

    Args:
        adapter: A `DVRAdapter` bound to one evidence item's reader.
        recording_id: The recording to recover, as returned by this
            adapter's own `enumerate_recordings()`.

    Returns:
        The adapter's `AdapterResult`, or a clean "not implemented" result
        if this adapter has no vendor-specific recovery capability.
    """
    try:
        return adapter.recover_recording(recording_id)
    except AdapterCapabilityNotImplementedError as exc:
        return _not_implemented_result(adapter, "recover_recording", exc)


def attempt_fragment_reconstruction(adapter: DVRAdapter, recording_id: str) -> AdapterResult:
    """Ask a bound adapter to reconstruct fragment relationships for a recording.

    Args:
        adapter: A `DVRAdapter` bound to one evidence item's reader.
        recording_id: The recording whose fragments should be reconstructed.

    Returns:
        The adapter's `AdapterResult`, or a clean "not implemented" result
        if this adapter has no fragment-reconstruction capability.
    """
    try:
        return adapter.reconstruct_fragments(recording_id)
    except AdapterCapabilityNotImplementedError as exc:
        return _not_implemented_result(adapter, "reconstruct_fragments", exc)

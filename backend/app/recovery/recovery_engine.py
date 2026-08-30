"""
Top-level layered recovery orchestration (Master Specification Section 21).

    Layer 1: filesystem/index recovery
    Layer 2: vendor-specific recovery
    Layer 3: carving
    Layer 4: fragment reconstruction

This module knows nothing about CP Plus or any other vendor's byte
structures — it only knows how to run whichever layer callables it is
given, in order, and to record an explicit outcome for every layer it
considers (Phase 10 task scope: "Do not silently fall through layers").
Which concrete callables to supply (CP Plus's `recover_recording`, its
carving scan, ...) is decided by the caller — `app.core.recovery_manager`
— exactly the same "generic engine, vendor-specific dispatch decided by
the DB-aware orchestration layer" split Phase 9 already established
between `app.media` and `app.core.recording_manager`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.adapters.base import AdapterResult
from app.recovery import RecoveryMethod, RecoveryStatus
from app.recovery.filesystem_recovery import FilesystemRecoveryOutcome

#: Version identifier for this recovery engine implementation (Phase 10
#: task scope, "RECOVERY OUTPUT": "recovery engine version"). Independent
#: of any vendor adapter's own `adapter_version`/`parser_version`.
RECOVERY_ENGINE_VERSION = "0.1.0"


@dataclass(frozen=True)
class RecoveryLayerResult:
    """One layer's outcome, normalized to a single common shape.

    `bytes_recovered`/`frames_recovered`/`frame_continuity`/`fragments_*`
    are read from a producing layer's `AdapterResult.metadata` dict by
    convention (the same "stringly-typed metadata dict" convention Phase 9
    already established for `CPPlusAdapter.extract_recording`) — a `None`
    value means "not reported by this layer/adapter", never a fabricated 0.
    """

    method: RecoveryMethod
    status: RecoveryStatus
    reason: str
    bytes_recovered: int | None = None
    frames_recovered: int | None = None
    frame_continuity: float | None = None
    fragments_found: int | None = None
    fragments_used: int | None = None
    fragments_missing: int | None = None
    confidence: float | None = None
    confidence_basis: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RecoveryEngineResult:
    """The full recovery attempt: every layer considered, plus the authoritative one."""

    layers: list[RecoveryLayerResult]
    final: RecoveryLayerResult
    engine_version: str = RECOVERY_ENGINE_VERSION


def _int_metadata(metadata: dict[str, str], key: str) -> int | None:
    value = metadata.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _float_metadata(metadata: dict[str, str], key: str) -> float | None:
    value = metadata.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _status_from_adapter_result(result: AdapterResult) -> RecoveryStatus:
    """Classify a vendor recovery `AdapterResult` into a `RecoveryStatus`.

    Prefers an explicit `metadata["recovery_status"]` value when the
    producing adapter already computed one (e.g. CP Plus's
    `recover_recording`, which has vendor-specific knowledge of exactly
    where a walk stopped) — falling back to a generic
    bytes-written/truncated/corrupted heuristic only when no adapter-
    computed status is present. Never `RECOVERED` for a truncated/
    corrupted/empty result either way (Phase 10 task scope, section 10).
    """
    explicit_status = result.metadata.get("recovery_status")
    if explicit_status is not None:
        try:
            return RecoveryStatus(explicit_status)
        except ValueError:
            pass  # fall through to the generic heuristic below

    bytes_recovered = _int_metadata(result.metadata, "bytes_recovered") or _int_metadata(
        result.metadata, "bytes_written"
    )
    if not bytes_recovered:
        return RecoveryStatus.NO_RECOVERY_FOUND
    truncated = result.metadata.get("truncated") == "True"
    corrupted = result.metadata.get("corrupted") == "True"
    if truncated or corrupted:
        return RecoveryStatus.PARTIAL
    return RecoveryStatus.RECOVERED


def layer_result_from_filesystem_outcome(outcome: FilesystemRecoveryOutcome) -> RecoveryLayerResult:
    """Wrap a Layer 1 `FilesystemRecoveryOutcome` into a `RecoveryLayerResult`."""
    return RecoveryLayerResult(
        method=RecoveryMethod.FILESYSTEM_INDEX, status=outcome.status, reason=outcome.reason
    )


def layer_result_from_adapter_result(
    method: RecoveryMethod, result: AdapterResult
) -> RecoveryLayerResult:
    """Wrap a Layer 2/4 `AdapterResult` (vendor recovery / fragment reconstruction)
    into a `RecoveryLayerResult`, per the metadata-dict convention documented on
    `RecoveryLayerResult`."""
    status = _status_from_adapter_result(result)
    reason = (
        result.warnings[-1]
        if result.warnings
        else ("recovered cleanly" if status == RecoveryStatus.RECOVERED else "no detail reported")
    )
    return RecoveryLayerResult(
        method=method,
        status=status,
        reason=reason,
        bytes_recovered=_int_metadata(result.metadata, "bytes_recovered")
        or _int_metadata(result.metadata, "bytes_written"),
        frames_recovered=_int_metadata(result.metadata, "frames_recovered")
        or _int_metadata(result.metadata, "frames_written"),
        frame_continuity=_float_metadata(result.metadata, "frame_continuity"),
        fragments_found=_int_metadata(result.metadata, "fragments_found"),
        fragments_used=_int_metadata(result.metadata, "fragments_used"),
        fragments_missing=_int_metadata(result.metadata, "fragments_missing"),
        confidence=result.confidence if result.confidence > 0 else None,
        warnings=list(result.warnings),
    )


@dataclass
class RecoveryLayerCallables:
    """The concrete, vendor-specific layer implementations for one recovery attempt.

    Any field left `None` means that layer was not attempted for this
    evidence/recording (reported as `NOT_ATTEMPTED`, never silently
    skipped without a trace entry).
    """

    filesystem_recovery: Callable[[], FilesystemRecoveryOutcome] | None = None
    vendor_recovery: Callable[[], AdapterResult] | None = None
    carving: Callable[[], RecoveryLayerResult] | None = None
    fragment_reconstruction: Callable[[], AdapterResult] | None = None


def run_recovery_layers(callables: RecoveryLayerCallables) -> RecoveryEngineResult:
    """Run Layers 1-4 in order, stopping at the first fully `RECOVERED` layer.

    Every layer is recorded in `RecoveryEngineResult.layers`, whether it
    ran, was skipped (`NOT_ATTEMPTED`), or errored (`FAILED`) — this is the
    "never silently fall through layers" guarantee (Phase 10 task scope).

    Args:
        callables: The concrete layer implementations to run.

    Returns:
        A `RecoveryEngineResult` with the full layer trace and the
        authoritative `final` result. Only Layer 1 (`RECOVERED`) short-
        circuits the remaining layers — a genuine, vendor-index-confirmed
        recovery leaves nothing for content/carving/structure checks to
        add. Layers 2-4 otherwise **all** run unconditionally (never
        skipped just because an earlier layer already looked
        successful): Layer 4 in particular must get the chance to detect
        a structurally missing fragment even when every fragment *present*
        had perfectly clean content, and Layer 3 must get the chance to
        find extra bytes even when Layer 2 recovered something already —
        see `_combine_final` for exactly how the four layers are
        reconciled, and why a later layer is never allowed to silently
        upgrade what an earlier, more content-authoritative layer already
        found (Phase 10 task scope, section 10: "Never report RECOVERED
        when the recovered media is incomplete or unverified").
    """
    layers: list[RecoveryLayerResult] = []

    def _run_layer(
        method: RecoveryMethod, layer_callable: Callable[[], RecoveryLayerResult] | None
    ) -> RecoveryLayerResult:
        if layer_callable is None:
            return RecoveryLayerResult(
                method=method,
                status=RecoveryStatus.NOT_ATTEMPTED,
                reason="no implementation supplied for this evidence/vendor",
            )
        try:
            return layer_callable()
        except Exception as exc:  # noqa: BLE001 - a layer failure must never crash recovery
            return RecoveryLayerResult(
                method=method, status=RecoveryStatus.FAILED, reason=f"layer raised: {exc}"
            )

    fs_result = _run_layer(
        RecoveryMethod.FILESYSTEM_INDEX,
        (
            (lambda: layer_result_from_filesystem_outcome(callables.filesystem_recovery()))  # type: ignore[misc]
            if callables.filesystem_recovery is not None
            else None
        ),
    )
    layers.append(fs_result)
    if fs_result.status == RecoveryStatus.RECOVERED:
        return RecoveryEngineResult(layers=layers, final=fs_result)

    vendor_result = _run_layer(
        RecoveryMethod.VENDOR_DAMAGED_RECOVERY,
        (
            (
                lambda: layer_result_from_adapter_result(
                    RecoveryMethod.VENDOR_DAMAGED_RECOVERY, callables.vendor_recovery()  # type: ignore[misc]
                )
            )
            if callables.vendor_recovery is not None
            else None
        ),
    )
    layers.append(vendor_result)

    carving_result = _run_layer(RecoveryMethod.CARVING, callables.carving)
    layers.append(carving_result)

    fragment_result = _run_layer(
        RecoveryMethod.FRAGMENT_RECONSTRUCTION,
        (
            (
                lambda: layer_result_from_adapter_result(
                    RecoveryMethod.FRAGMENT_RECONSTRUCTION,
                    callables.fragment_reconstruction(),  # type: ignore[misc]
                )
            )
            if callables.fragment_reconstruction is not None
            else None
        ),
    )
    layers.append(fragment_result)

    final = _combine_final(vendor_result, fs_result, carving_result, fragment_result)
    return RecoveryEngineResult(layers=layers, final=final)


_STATUS_RANK = {
    RecoveryStatus.RECOVERED: 5,
    RecoveryStatus.PARTIAL: 4,
    RecoveryStatus.NO_RECOVERY_FOUND: 3,
    RecoveryStatus.UNSUPPORTED: 2,
    RecoveryStatus.NOT_ATTEMPTED: 1,
    RecoveryStatus.FAILED: 0,
}


def _combine_final(
    vendor: RecoveryLayerResult,
    filesystem: RecoveryLayerResult,
    carving: RecoveryLayerResult,
    fragments: RecoveryLayerResult,
) -> RecoveryLayerResult:
    """Reconcile all four layers into one authoritative result.

    Vendor (content-level) recovery is the base whenever it was actually
    attempted — it is the only layer that inspects the media's own bytes.
    Carving may only *replace* that base when the base found nothing at
    all (`NO_RECOVERY_FOUND`/`UNSUPPORTED`) and carving found something —
    it can never override a base that already has real content. Fragment
    reconstruction may only *downgrade* the result (e.g. a genuinely
    missing whole segment pulls a per-segment-clean result down to
    `PARTIAL`) — it can never upgrade a base to `RECOVERED` on its own,
    since fragment ordering says nothing about whether the fragments that
    *are* present are themselves undamaged.
    """
    base = vendor if vendor.status != RecoveryStatus.NOT_ATTEMPTED else filesystem

    if (
        base.status in (RecoveryStatus.NO_RECOVERY_FOUND, RecoveryStatus.UNSUPPORTED)
        and _STATUS_RANK[carving.status] > _STATUS_RANK[base.status]
    ):
        base = carving

    if (
        fragments.status != RecoveryStatus.NOT_ATTEMPTED
        and _STATUS_RANK[fragments.status] < _STATUS_RANK[base.status]
    ):
        base = fragments

    return base

"""
Vendor-adapter base contract.
Master Specification Section 16 ("Vendor Adapter Interface"), Section 92
("Third Backend Milestone": DVRAdapter, AdapterRegistry, AdapterCapability).

This module defines the CONTRACT ONLY — what a future vendor adapter must
declare and expose. It contains no vendor-specific logic and performs no
parsing. Concrete vendor adapters (CP Plus, Hikvision, Dahua, ...) are
Phase 8+ work, implemented under their own `app/adapters/<vendor>/`
package, each subclassing `DVRAdapter` from here.

Per Section 16: "The adapter should not own the entire application. Its
job is: Vendor-specific storage understanding. The common engine should
own: evidence objects, timeline, validation, provenance, reporting,
common recovery logic, AI, correlation." Nothing in this module reaches
into any of those common systems.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, IntEnum


class AdapterCapability(str, Enum):
    """A capability a vendor adapter can declare support for.

    Master Specification Section 16 (adapter methods) and Section 92
    (item 2 of this phase's own scope): each value corresponds to a group
    of the conceptual adapter methods below, so a capability declaration
    and the methods it gates stay traceable to each other. Only
    capabilities with a documented basis are listed here — recovery
    sub-steps (carving, fragment reconstruction, confidence scoring),
    timeline/correlation, AI, validation, and reporting are common-engine
    concerns (Section 16) or later-phase capabilities, not adapter
    capabilities, and are deliberately not represented here.
    """

    DEVICE_IDENTIFICATION = "device_identification"
    FILESYSTEM_DETECTION = "filesystem_detection"
    RECORDING_ENUMERATION = "recording_enumeration"
    METADATA_EXTRACTION = "metadata_extraction"
    TIMESTAMP_EXTRACTION = "timestamp_extraction"
    RECORDING_EXTRACTION = "recording_extraction"
    RECOVERY = "recovery"
    NATIVE_EXPORT_HANDLING = "native_export_handling"


class SupportLevel(IntEnum):
    """How much of a vendor's format an adapter actually implements
    (Phase 19, Master Specification Section 17: "Vendor support is not
    just a brand checkbox... capability reporting should be
    model/firmware aware").

    Ordered so a higher value always means more implemented, never a
    claim of "brand support" by itself — `AdapterRegistry` selecting an
    adapter (a vendor/model/firmware pattern match) says nothing about
    which of these levels that adapter has actually reached; read
    `DVRAdapter.support_level`/`.capabilities` for that.
    """

    #: Public information exists (research paper, vendor documentation,
    #: third-party tool), but nothing in this codebase implements or
    #: validates it. No adapter capability is ever declared at this level.
    LEVEL_0_RESEARCH_ONLY = 0
    #: The vendor/format can be recognized deterministically from a
    #: documented, evidence-backed signature, but recording/index parsing
    #: is not implemented.
    LEVEL_1_DETECTION = 1
    #: Storage/recording structure (index, channel, timestamp fields) can
    #: be identified and parsed, but full media extraction is incomplete.
    LEVEL_2_STRUCTURE_PARSING = 2
    #: Recordings can be enumerated and extracted into standard media,
    #: but this has not been validated against real or authoritative
    #: controlled evidence for a defined model/firmware/format scope.
    LEVEL_3_RECORDING_EXTRACTION = 3
    #: Implementation has been tested against real or authoritative
    #: controlled evidence for a defined model/firmware/format scope
    #: (e.g. CP Plus's "ADIT-v1" signature, Phase 8).
    LEVEL_4_VALIDATED = 4


class EvidenceBasis(str, Enum):
    """What kind of evidence backs a `DVRAdapter`'s declared
    `support_level` (Phase 19 task scope: "For every vendor, explicitly
    classify the evidence basis"). A single adapter may cite more than
    one -- e.g. a public reference implementation *and* public format
    documentation that independently corroborate each other."""

    #: This project's own real, hash-verified evidence (e.g. CP Plus's
    #: analyzed `.cpv` package).
    REAL_PROJECT_EVIDENCE = "real_project_evidence"
    #: An existing, inspected open-source parser/tool/library (license
    #: reviewed) that independently implements/tests the format.
    PUBLIC_REFERENCE_IMPLEMENTATION = "public_reference_implementation"
    #: Published vendor documentation, peer-reviewed research, or a
    #: reproducible technical writeup describing the format, without an
    #: inspected reference implementation.
    PUBLIC_FORMAT_DOCUMENTATION = "public_format_documentation"
    #: Legally-usable public sample files were available and used.
    PUBLIC_SAMPLE_DATA = "public_sample_data"
    #: Only a synthetic fixture built from documented (not this
    #: project's own) behavior was used -- never presented as validation
    #: against real evidence.
    SYNTHETIC_ONLY = "synthetic_only"
    #: A reasoned hypothesis with no direct format documentation, sample,
    #: or reference implementation backing it -- the weakest basis;
    #: never sufficient alone to justify `LEVEL_1_DETECTION` or above.
    INFERENCE = "inference"


@dataclass(frozen=True)
class AdapterResult:
    """Normalized output of a vendor adapter (Master Specification Section 16).

    Phase 7 defines this shape only — every adapter built in this phase
    (the dummy/test adapter included) returns it with empty/placeholder
    content, since no adapter may actually parse proprietary data yet.
    Phase 8+ adapters populate it for real.
    """

    vendor: str
    model: str | None
    firmware: str | None
    detected_format: str | None
    capability_set: frozenset[AdapterCapability]
    recordings: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    recovery_candidates: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    parser_version: str = "0.0.0"
    confidence: float = 0.0


class AdapterCapabilityNotImplementedError(NotImplementedError):
    """Raised by a `DVRAdapter` operation the concrete adapter has not implemented.

    Distinct from "no adapter matched this evidence at all" (an
    `AdapterRegistry` selection outcome) — this fires only after an
    adapter has already been selected, when one of its operations is
    invoked but that specific operation was never overridden. Master
    Specification Section 92: "At this stage, the parser can return
    'unsupported' cleanly" — this is that clean, typed signal, never a
    bare `AttributeError` or a guessed result.
    """


class DVRAdapter(ABC):
    """Base contract every vendor adapter must satisfy.

    Identity (`vendor`, `model_pattern`, `firmware_pattern`,
    `capabilities`, `adapter_version`) is declarative metadata an
    `AdapterRegistry` reads to decide whether this adapter applies to a
    given `app.schemas.device.DeviceIdentificationResult` — it must be
    determinable without opening or reading any evidence.

    The operation methods mirror Section 16's conceptual adapter methods
    by name, so the contract stays traceable to the specification. Every
    one of them defaults to raising `AdapterCapabilityNotImplementedError`
    here; a concrete adapter overrides only the operations it actually
    implements. This phase's own dummy/test adapter overrides none of
    them — proving the framework never requires real parsing to exist.
    """

    @property
    @abstractmethod
    def vendor(self) -> str:
        """Exact vendor name this adapter handles (e.g. `"CP Plus"`)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def model_pattern(self) -> str:
        """Regular expression matched against a candidate's declared model.

        Master Specification Section 92's `register_adapter(vendor=...,
        model_pattern=..., firmware_pattern=...)` pattern. Use `".*"` to
        declare a vendor-level generic adapter that does not depend on a
        specific model — the registry treats this as the weakest possible
        match strength (Section 17: "Never report 'CP Plus fully
        supported' if only one model is tested.").
        """
        raise NotImplementedError

    @property
    def firmware_pattern(self) -> str | None:
        """Regular expression matched against a candidate's declared firmware.

        `None` (the default) means this adapter does not depend on
        firmware version. Section 17: "Real support may depend on... exact
        firmware" — an adapter that does care must declare this pattern so
        the registry can tell a known-incompatible firmware apart from an
        unconfirmed one.
        """
        return None

    @property
    @abstractmethod
    def capabilities(self) -> frozenset[AdapterCapability]:
        """The set of capabilities this adapter actually implements."""
        raise NotImplementedError

    @property
    @abstractmethod
    def adapter_version(self) -> str:
        """Version identifier for this adapter implementation.

        Distinct from the DVR's own firmware version. Master
        Specification Section 59 ("Deterministic/Reproducible
        Processing"): "store parser version" — this is that value, kept
        as plain metadata rather than a version-management subsystem.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def support_level(self) -> SupportLevel:
        """How much of this vendor's format this adapter actually
        implements (Phase 19). Mandatory and never defaulted: forcing
        every adapter to state this explicitly is what prevents a
        registered vendor name from silently reading as "supported"."""
        raise NotImplementedError

    @property
    @abstractmethod
    def evidence_basis(self) -> tuple[EvidenceBasis, ...]:
        """What kind of evidence backs `support_level` (Phase 19). Must
        be non-empty; an adapter with nothing to cite belongs at
        `SupportLevel.LEVEL_0_RESEARCH_ONLY` with `(EvidenceBasis.
        PUBLIC_FORMAT_DOCUMENTATION,)` or `(EvidenceBasis.INFERENCE,)`,
        whichever is honest, never an empty tuple standing in for "we
        don't know why we believe this"."""
        raise NotImplementedError

    @property
    def model_scope(self) -> str:
        """Free-text description of exactly which model(s)/firmware
        `support_level` applies to (Master Specification Section 17:
        "Never report 'CP Plus fully supported' if only one model is
        tested"). Defaults to an explicit "nothing validated" statement
        rather than silence -- a subclass with real scope should always
        override this."""
        return "no specific model/firmware has been validated for this adapter"

    @property
    def limitations(self) -> tuple[str, ...]:
        """Free-text known limitations of this adapter's implementation
        (Phase 19 task scope: support-matrix "Limitations" column).
        Empty by default; a subclass with real limitations should always
        override this rather than leaving them implicit."""
        return ()

    def supports(self, capability: AdapterCapability) -> bool:
        """Return whether this adapter declares support for `capability`."""
        return capability in self.capabilities

    def _not_implemented(self, operation: str) -> AdapterCapabilityNotImplementedError:
        return AdapterCapabilityNotImplementedError(
            f"{self.vendor} adapter (version {self.adapter_version}) does not implement "
            f"{operation}()"
        )

    # --- Section 16 conceptual adapter methods ---
    # Every method below defaults to a clean "not implemented by this
    # adapter" signal. None of them may be called during Phase 7 itself —
    # the framework only registers, matches, and selects; it never invokes
    # these (Section 92 scope boundary).

    def identify(self) -> AdapterResult:
        """Vendor-specific device identification, beyond Phase 6's generic pass."""
        raise self._not_implemented("identify")

    def detect_capabilities(self) -> frozenset[AdapterCapability]:
        """Vendor/model/firmware-aware capability report (Section 17)."""
        raise self._not_implemented("detect_capabilities")

    def inspect_storage(self) -> AdapterResult:
        """Vendor-specific storage/partition layout inspection."""
        raise self._not_implemented("inspect_storage")

    def parse_filesystem(self) -> AdapterResult:
        """Parse the vendor's proprietary filesystem/recording index."""
        raise self._not_implemented("parse_filesystem")

    def parse_metadata(self) -> AdapterResult:
        """Extract vendor-specific recording metadata."""
        raise self._not_implemented("parse_metadata")

    def enumerate_recordings(self) -> AdapterResult:
        """List recordings discoverable from the vendor's recording index."""
        raise self._not_implemented("enumerate_recordings")

    def extract_recording(self, recording_id: str) -> AdapterResult:
        """Extract one recording's stream/container data."""
        raise self._not_implemented("extract_recording")

    def find_deleted_recordings(self) -> AdapterResult:
        """Locate deleted-but-still-referenced recordings (Phase 10 territory)."""
        raise self._not_implemented("find_deleted_recordings")

    def recover_recording(self, recording_id: str) -> AdapterResult:
        """Recover one deleted/damaged recording (Phase 10 territory)."""
        raise self._not_implemented("recover_recording")

    def reconstruct_fragments(self, recording_id: str) -> AdapterResult:
        """Reassemble scattered recording fragments (Phase 10 territory)."""
        raise self._not_implemented("reconstruct_fragments")

    def decode_metadata(self) -> AdapterResult:
        """Decode vendor-specific timestamp/metadata encodings."""
        raise self._not_implemented("decode_metadata")

    def validate_recording(self, recording_id: str) -> AdapterResult:
        """Validate a recovered/extracted recording (Phase 14 territory)."""
        raise self._not_implemented("validate_recording")

    def normalize_evidence(self) -> AdapterResult:
        """Produce this adapter's final normalized `AdapterResult`.

        The adapter's primary entry point — where vendor-specific findings
        are translated into the common, vendor-agnostic evidence model the
        rest of the backend consumes (Master Specification Section 6:
        "Every adapter must eventually translate vendor-specific
        information into the same conceptual evidence representation.").
        """
        raise self._not_implemented("normalize_evidence")

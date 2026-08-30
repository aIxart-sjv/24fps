"""
Matrix vendor adapter (Phase 19, "Additional OEM Adapters").
Master Specification Section 17 ("Target OEM Adapters" names Matrix).

============================================================================
RESEARCH SUMMARY -- read before touching `capabilities`/`support_level`
============================================================================
No real Matrix evidence exists in this project, and no public filesystem
reverse-engineering study or published forensic parser was found for any
Matrix DVR/NVR. This adapter is therefore `SupportLevel.
LEVEL_0_RESEARCH_ONLY`: identity-only, zero capabilities, no detection
code.

============================================================================
SOURCES CONSULTED (with what each one actually established)
============================================================================
1. `docs/SIH_NTRO_REQUIREMENTS.md` (this project's own prior research,
   section "15. Matrix") -- confirms Matrix as a real Indian surveillance
   manufacturer with real DVR/NVR products, but explicitly states: "we do
   not currently have enough evidence to claim a specific proprietary
   filesystem structure or published forensic parser", concluding the
   exact filesystem architecture is UNKNOWN.
2. A live web search for Matrix DVR/NVR forensic filesystem research
   during this phase's own research pass did not surface any additional
   technical source beyond what source 1 already summarized -- no
   academic paper, no open-source parser, no vendor technical
   documentation describing on-disk structure was located.

============================================================================
WHY LEVEL 0, NOT HIGHER
============================================================================
No byte-level signature, header layout, index format, or named
proprietary filesystem generation was found anywhere for Matrix. This is
the most research-thin of all eight NTRO-named OEMs in this project's
findings -- there is nothing here to encode as a signature without
inventing one, which this phase explicitly forbids.

============================================================================
PATH TO UPGRADE
============================================================================
    current: vendor/product-family existence confirmed; zero published
              technical/byte-level structure
                         |
                         v
             MatrixAdapter.support_level == LEVEL_0_RESEARCH_ONLY
                         |
             (real or authoritative sample Matrix DVR/NVR evidence
              becomes available for direct binary analysis)
                         |
                         v
    binary-analyze the acquired storage; identify any structural
    markers; validate against the specific model/firmware tested
                         |
                         v
    raise support_level to LEVEL_1_DETECTION only once a real,
    evidence-backed signature is confirmed, never before
"""

from __future__ import annotations

from app.adapters.base import AdapterCapability, DVRAdapter, EvidenceBasis, SupportLevel

ADAPTER_VERSION = "0.1.0-research"

__all__ = ["ADAPTER_VERSION", "MatrixAdapter"]


class MatrixAdapter(DVRAdapter):
    """Vendor-level Matrix adapter -- research-only (`SupportLevel.
    LEVEL_0_RESEARCH_ONLY`). No detection or parsing capability is
    implemented. See this module's docstring for the full research basis
    and why no signature is encoded."""

    def __init__(self) -> None:
        pass

    @property
    def vendor(self) -> str:
        return "Matrix"

    @property
    def model_pattern(self) -> str:
        return ".*"

    @property
    def capabilities(self) -> frozenset[AdapterCapability]:
        return frozenset()

    @property
    def adapter_version(self) -> str:
        return ADAPTER_VERSION

    @property
    def support_level(self) -> SupportLevel:
        return SupportLevel.LEVEL_0_RESEARCH_ONLY

    @property
    def evidence_basis(self) -> tuple[EvidenceBasis, ...]:
        return (EvidenceBasis.INFERENCE,)

    @property
    def model_scope(self) -> str:
        return (
            "unknown model, unknown firmware, unknown filesystem; Matrix is a "
            "confirmed Indian DVR/NVR manufacturer with no published technical "
            "structure found -- see module docstring"
        )

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "no public filesystem reverse-engineering study, byte-level signature, or "
            "forensic parser was found for any Matrix DVR/NVR -- no detection "
            "capability is implemented",
            "no real or sample Matrix evidence has been tested in this project -- "
            "REAL VALIDATION PENDING",
        )

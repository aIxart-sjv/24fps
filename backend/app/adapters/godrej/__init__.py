"""
Godrej vendor adapter (Phase 19, "Additional OEM Adapters").
Master Specification Section 17 ("Target OEM Adapters" names Godrej).

============================================================================
RESEARCH SUMMARY -- read before touching `capabilities`/`support_level`
============================================================================
No real Godrej evidence exists in this project, and no public filesystem
reverse-engineering study was found for any Godrej DVR/NVR. This adapter
is therefore `SupportLevel.LEVEL_0_RESEARCH_ONLY`: identity-only, zero
capabilities, no detection code.

============================================================================
SOURCES CONSULTED (with what each one actually established)
============================================================================
1. An Indian Kanoon court-record citation (a Delhi High Court case in
   which Godrej DVR hard disks were removed by Godrej's own technicians,
   then sealed and seized for investigation) --
   cited in `docs/SIH_NTRO_REQUIREMENTS.md` section "14. Godrej".
   This establishes real forensic *relevance*: Godrej DVR storage has
   directly become evidence in an actual Indian criminal investigation.
   It says nothing about the filesystem's technical structure.
2. `docs/SIH_NTRO_REQUIREMENTS.md` itself (section "14. Godrej") --
   explicitly concludes: "I have not found a strong public, peer-reviewed
   Godrej filesystem reverse-engineering study" and frames the correct
   status as "UNKNOWN / research gap", explicitly distinct from "Godrej
   is definitely unsupported" -- a distinction this module preserves.
3. A live web search for Godrej DVR/NVR forensic filesystem research
   during this phase's own research pass did not surface any additional
   technical source beyond what source 2 already summarized.

============================================================================
WHY LEVEL 0, NOT HIGHER
============================================================================
No byte-level signature, header layout, index format, or even a named
proprietary filesystem generation (contrast Dahua's "DHFS4.1" or
Hikvision's documented Master Sector) was found anywhere. The evidence
that exists (source 1) proves forensic *relevance*, not technical
*understanding* -- these are different things, and this module does not
conflate them.

============================================================================
PATH TO UPGRADE
============================================================================
    current: real-world forensic relevance confirmed (source 1); zero
              published technical/byte-level structure
                         |
                         v
             GodrejAdapter.support_level == LEVEL_0_RESEARCH_ONLY
                         |
             (real or authoritative sample Godrej DVR/NVR evidence
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

__all__ = ["ADAPTER_VERSION", "GodrejAdapter"]


class GodrejAdapter(DVRAdapter):
    """Vendor-level Godrej adapter -- research-only (`SupportLevel.
    LEVEL_0_RESEARCH_ONLY`). No detection or parsing capability is
    implemented. See this module's docstring for the full research basis
    and why no signature is encoded."""

    def __init__(self) -> None:
        pass

    @property
    def vendor(self) -> str:
        return "Godrej"

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
            "unknown model, unknown firmware, unknown filesystem; Godrej DVR storage "
            "has real documented forensic relevance (an Indian court case) but no "
            "published technical structure -- see module docstring"
        )

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "no public filesystem reverse-engineering study or byte-level signature "
            "was found for any Godrej DVR/NVR -- no detection capability is implemented",
            "no real or sample Godrej evidence has been tested in this project -- "
            "REAL VALIDATION PENDING",
            "status is an explicit research gap (UNKNOWN), not a claim that Godrej "
            "storage is definitively unsupportable",
        )

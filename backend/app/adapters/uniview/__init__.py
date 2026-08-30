"""
Uniview vendor adapter (Phase 19, "Additional OEM Adapters").
Master Specification Section 17 ("Target OEM Adapters" names Uniview).

============================================================================
RESEARCH SUMMARY -- read before touching `capabilities`/`support_level`
============================================================================
No real Uniview evidence exists in this project, and no public
byte-level signature or reverse-engineering study was found for
Uniview's proprietary storage technology. This adapter is therefore
`SupportLevel.LEVEL_0_RESEARCH_ONLY`: identity-only, zero capabilities,
no detection code. It exists so the vendor is architecturally
represented, not because anything here is implemented.

============================================================================
SOURCES CONSULTED (with what each one actually established)
============================================================================
1. Uniview's own 2025 CCTV Product Guide (official vendor
   documentation) --
   https://www.uniview.com/res/202502/25/20250225_1940546_CCTV%20Product%20Guide%202025-%20read%20-%2020250224_1006124_168459_0.pdf
   Uniview itself documents "UBS" (Uniview Block Storage): the vendor's
   own marketing/technical material explicitly contrasts a traditional
   stack (application -> virtual filesystem -> FAT/NTFS/EXT/UFS -> block
   device -> HDD) against UBS's own (application -> block device driver
   -> HDD, with "a proprietary algorithm for data mapping" that
   "prevents direct access to video data on the HDD"). This VERIFIES
   that Uniview storage is genuinely proprietary at the block level (not
   merely "unfamiliar" or "undocumented" -- the vendor states this
   directly), but a vendor confirming a technology *exists* is not the
   same as documenting its byte-level structure. No signature, header
   layout, or index format is published.
2. `docs/SIH_NTRO_REQUIREMENTS.md` (this project's own prior research,
   section "12. Uniview -- particularly interesting") -- summarizes
   source 1 and reaches the same "storage confirmed proprietary; no
   forensic reverse-engineering coverage established" conclusion
   reflected here.

============================================================================
WHY LEVEL 0, NOT HIGHER
============================================================================
Source 1 proves UBS's proprietary nature (a genuinely useful fact for
the project's own NTRO framing -- "why proprietary DVR storage parsing
matters" -- see the sources cited in section 2 of docs/
SIH_NTRO_REQUIREMENTS.md) but supplies no byte-level detail whatsoever:
no magic bytes, no header offsets, no block-mapping algorithm
description. There is nothing here that could be encoded as a
deterministic signature without inventing one, which this phase
explicitly forbids.

============================================================================
PATH TO UPGRADE
============================================================================
    current: vendor-confirmed proprietary block storage (UBS), zero
              published byte-level structure
                         |
                         v
             UniviewAdapter.support_level == LEVEL_0_RESEARCH_ONLY
                         |
             (real or authoritative sample Uniview NVR evidence becomes
              available, or a credible reverse-engineering source is
              found that this research pass did not locate)
                         |
                         v
    identify and validate an actual UBS structural marker against real
    evidence before encoding any signature
                         |
                         v
    raise support_level to LEVEL_1_DETECTION only once a real match is
    confirmed, never before
"""

from __future__ import annotations

from app.adapters.base import AdapterCapability, DVRAdapter, EvidenceBasis, SupportLevel

ADAPTER_VERSION = "0.1.0-research"

__all__ = ["ADAPTER_VERSION", "UniviewAdapter"]


class UniviewAdapter(DVRAdapter):
    """Vendor-level Uniview adapter -- research-only (`SupportLevel.
    LEVEL_0_RESEARCH_ONLY`). No detection or parsing capability is
    implemented. See this module's docstring for the full research basis
    and why no signature is encoded."""

    def __init__(self) -> None:
        pass

    @property
    def vendor(self) -> str:
        return "Uniview"

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
        return (EvidenceBasis.PUBLIC_FORMAT_DOCUMENTATION,)

    @property
    def model_scope(self) -> str:
        return (
            "unknown model, unknown firmware; vendor documentation confirms "
            "proprietary 'UBS' (Uniview Block Storage) exists generally, but no "
            "model-specific or byte-level detail is published -- see module docstring"
        )

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "no public byte-level signature, header layout, or index format has been "
            "found for UBS -- no detection capability is implemented",
            "no real or sample Uniview evidence has been tested in this project -- "
            "REAL VALIDATION PENDING",
            "the vendor's own documentation confirms proprietary block-level storage "
            "exists, but this is confirmation of existence, not a parseable structure",
        )

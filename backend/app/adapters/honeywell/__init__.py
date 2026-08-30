"""
Honeywell Security vendor adapter (Phase 19, "Additional OEM Adapters").
Master Specification Section 17 ("Target OEM Adapters" names Honeywell
Security).

============================================================================
RESEARCH SUMMARY -- read before touching `capabilities`/`support_level`
============================================================================
No real Honeywell evidence exists in this project, and no deterministic,
cross-corroborated byte signature was found for Honeywell's proprietary
surveillance filesystem. This adapter is therefore `SupportLevel.
LEVEL_0_RESEARCH_ONLY`: identity-only, zero capabilities, no detection
code at all. It exists so the vendor is architecturally represented
(Master Specification Section 17: "Project architecture must nevertheless
be designed so all named vendors can be represented by adapters"), not
because anything here is implemented.

============================================================================
SOURCES CONSULTED (with what each one actually established)
============================================================================
1. A 2026 DFRWS-track paper (also posted to arXiv and published in
   ScienceDirect/FDTC) analyzing an "undocumented proprietary Honeywell
   surveillance filesystem" via binary diffing --
   https://dfrws.org/presentation/forensic-analysis-of-video-data-deletion-and-recovery-in-honeywell-surveillance-file-system/
   https://arxiv.org/abs/2605.07430
   https://www.sciencedirect.com/science/article/pii/S2666281726000739
   Real, recent, peer-reviewed research. It analyzed one specific device
   (Honeywell NVR model HN35080200 with HN40E-2030I cameras; exact
   firmware not disclosed in the paper) and documented device-specific
   findings: a GPT-based partition scheme (GPT itself is a standard,
   non-proprietary partitioning scheme -- not evidence of a proprietary
   Honeywell signature), a custom 20-byte header preceding H.264 NAL
   units on that one device, and video data beginning at a *fixed disk
   offset specific to that one device* (0x80000000 within Partition 1).
   The paper explicitly scopes itself: "our analysis is currently limited
   to a single Honeywell device" and does not publish a vendor-wide magic
   byte signature or filesystem name.
2. `docs/SIH_NTRO_REQUIREMENTS.md` (this project's own prior research,
   section "11. Honeywell -- very interesting new development" and
   section "14. New 2026 Honeywell research") -- summarizes source 1 and
   independently reaches the same conclusion reflected here.

============================================================================
WHY LEVEL 0, NOT HIGHER
============================================================================
Source 1 is real and credible, but it documents a single-device offset
convention (0x80000000, a device-specific constant, not a discovered
magic-byte signature) rather than a cross-model/cross-firmware
deterministic marker. The paper itself declines to generalize beyond its
one tested device. Encoding that offset as a "Honeywell signature" here
would be exactly the "invent field semantics from coincidental byte
patterns" / "do not invent signatures" failure mode this phase must
avoid -- a fixed offset that happened to work on one specific unit is not
the same as a documented, vendor-wide structural marker (contrast with
Hikvision's "HIKVISION@HANGZHOU" ASCII string, corroborated across two
independent sources as an intentional identifying marker, not an
incidental offset).

============================================================================
PATH TO UPGRADE
============================================================================
    current: real 2026 peer-reviewed research exists, describing exactly
              one device's structure, with no vendor-wide signature
                         |
                         v
             HoneywellAdapter.support_level == LEVEL_0_RESEARCH_ONLY
                         |
             (real or authoritative sample Honeywell NVR evidence
              becomes available, ideally including the exact device
              studied in source 1, HN35080200)
                         |
                         v
    verify whether source 1's device-specific offsets/header format
    apply to the available evidence; if so, encode them as a genuine,
    evidence-backed signature (mirroring app.adapters.dahua/hikvision)
                         |
                         v
    raise support_level to LEVEL_1_DETECTION once a real match is
    confirmed against real evidence, never before
"""

from __future__ import annotations

from app.adapters.base import AdapterCapability, DVRAdapter, EvidenceBasis, SupportLevel

ADAPTER_VERSION = "0.1.0-research"

__all__ = ["ADAPTER_VERSION", "HoneywellAdapter"]


class HoneywellAdapter(DVRAdapter):
    """Vendor-level Honeywell Security adapter -- research-only
    (`SupportLevel.LEVEL_0_RESEARCH_ONLY`). No detection or parsing
    capability is implemented. See this module's docstring for the full
    research basis and why no signature is encoded."""

    def __init__(self) -> None:
        pass

    @property
    def vendor(self) -> str:
        return "Honeywell Security"

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
            "unknown model, unknown firmware; public 2026 research analyzed one "
            "specific device (Honeywell NVR HN35080200 with HN40E-2030I cameras) with "
            "no stated generalization to other models -- see module docstring"
        )

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "no deterministic, cross-corroborated Honeywell filesystem signature was "
            "found -- no detection capability is implemented",
            "no real or sample Honeywell evidence has been tested in this project -- "
            "REAL VALIDATION PENDING",
            "public research describes only a single device's structure; do not "
            "generalize its findings to other Honeywell models/firmware",
        )

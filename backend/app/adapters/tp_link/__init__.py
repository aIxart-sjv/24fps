"""
TP-Link vendor adapter (Phase 19, "Additional OEM Adapters").
Master Specification Section 17 ("Target OEM Adapters" names TP-Link).

============================================================================
RESEARCH SUMMARY -- read before touching `capabilities`/`support_level`
============================================================================
No real TP-Link evidence exists in this project, and no public forensic
filesystem reverse-engineering study was found for TP-Link's VIGI NVR
storage. This adapter is therefore `SupportLevel.LEVEL_0_RESEARCH_ONLY`:
identity-only, zero capabilities, no detection code.

============================================================================
SOURCES CONSULTED (with what each one actually established)
============================================================================
1. TP-Link's own VIGI surveillance solution documentation --
   https://static.tp-link.com/configuration-guides/2021/202107/20210713/vigi-surveillance-solution.pdf
   and the VIGI NVR product/user-guide pages (e.g.
   https://www.tp-link.com/us/user-guides/vigi-network-video-recorder/chapter-4-recording-and-storage.html) --
   document VIGI NVR user-facing recording/storage/search functionality
   (search by date/event/channel/tag, disk-quota assignment per camera,
   GUI-driven export/backup) and SATA HDD compatibility. This confirms
   the *product family* and its general capabilities, but says nothing
   about the on-disk proprietary structure.
2. `docs/SIH_NTRO_REQUIREMENTS.md` (this project's own prior research,
   section "13. TP-Link") -- explicitly concludes: "we have not
   established a public forensic filesystem reverse-engineering study
   comparable to Hikvision/Dahua" and "we should not claim today that
   TP-Link has an entirely unknown filesystem without testing the exact
   model" -- both conclusions are reflected here.
3. A live web search for TP-Link VIGI forensic/filesystem research
   during this phase's own research pass, independently confirming that
   available public material remains user/GUI-level documentation, not
   low-level technical/forensic detail.

============================================================================
WHY LEVEL 0, NOT HIGHER
============================================================================
No byte-level signature, header layout, or index format has been
published anywhere located during this research pass. TP-Link's own
documentation is entirely about GUI-level export, not native disk
structure -- exporting via the GUI (a standard file, per source 1)
should not be conflated with proprietary on-disk HDD storage (task Phase
19 scope: "Do not assume a generic export is equivalent to proprietary
HDD storage"). This project's own docs note that real TP-Link hardware
may become available for direct testing later, which would be the
correct way to establish a signature -- not inference from documentation
that does not describe the on-disk format at all.

============================================================================
PATH TO UPGRADE
============================================================================
    current: vendor product documentation only (GUI/user-facing, not
              on-disk structure); no forensic reverse-engineering found
                         |
                         v
             TPLinkAdapter.support_level == LEVEL_0_RESEARCH_ONLY
                         |
             (real TP-Link VIGI NVR storage/HDD becomes available for
              direct binary analysis -- this project's own docs note
              physical TP-Link equipment may exist for this purpose)
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

__all__ = ["ADAPTER_VERSION", "TPLinkAdapter"]


class TPLinkAdapter(DVRAdapter):
    """Vendor-level TP-Link adapter -- research-only (`SupportLevel.
    LEVEL_0_RESEARCH_ONLY`). No detection or parsing capability is
    implemented. See this module's docstring for the full research basis
    and why no signature is encoded."""

    def __init__(self) -> None:
        pass

    @property
    def vendor(self) -> str:
        return "TP-Link"

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
            "unknown model, unknown firmware; TP-Link's own VIGI NVR documentation "
            "covers user/GUI-level recording and storage features, not on-disk "
            "proprietary structure -- see module docstring"
        )

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "no public forensic filesystem reverse-engineering study was found for "
            "TP-Link VIGI NVR storage -- no detection capability is implemented",
            "no real or sample TP-Link evidence has been tested in this project -- "
            "REAL VALIDATION PENDING",
            "TP-Link's own documentation describes GUI-driven export, which must not "
            "be conflated with native proprietary HDD storage structure",
        )

# Phase 26 — Hikvision Integration

## 1. Validated device

Hikvision **DS-7A04HQHI-K1** ("Embedded Net DVR"), serial
`0420220517CCWRJ98043179WCVU`, hardware version `0xe9711`.

This validation scope is **exactly one device**. Nothing here should be
read as "Hikvision fully supported" — see Section 22 ("Known limitations")
and `app.adapters.hikvision`'s own module docstring, which spells out the
same boundary in code.

## 2. Model

`DS-7A04HQHI-K1`

## 3. Firmware

`V4.30.220, Build 220216`

## 4. Channels

4 total (camera `A1`/channel 1 and `A2`/channel 2 are represented in the
real evidence set; channels 3–4 were not exercised).

## 5. Resolution

1920×1080 configured (main stream, continuous + event). `ffprobe`
measures the encoded frame as 1920×1088 (HEVC macroblock padding to a
16-pixel boundary) — this project reports the raw `ffprobe` value rather
than "correcting" it to the configured 1080, consistent with never
substituting a device-configured value for a measured one.

## 6. FPS

Device configured: 15 fps (main stream, continuous + event).
**Measured** (`ffprobe`, all three real files): `avg_frame_rate` is
`30/1`; `r_frame_rate` is `25/1`. These two ffprobe-reported rates
disagree with each other and with the device's configured 15 fps. This
project does not attempt to resolve or explain that discrepancy — it is
recorded as an observed fact, and the code never hardcodes 15 (or 25, or
30) as a substitute for whatever a given file's own `ffprobe` measurement
reports.

## 7. Codec

H.265 / HEVC, Main profile, `yuv420p`, level 120. Audio: G.711 mu-law
(`pcm_mulaw`), 8 kHz, mono.

## 8. Timezone

`GMT+05:30` ("Madras, Bombay, ..."), confirmed from the device's own
System Settings screen (photographed alongside the evidence set).
Deliberately **not** baked into filename-derived timestamps — see
Section 13.

## 9. NTP configuration

Enabled. Server `time.windows.com`, port `123`, 30-minute sync interval.
NTP being enabled is recorded as configuration fact only; it is never
treated as proof that any specific recorded timestamp is accurate (Phase
26 task scope).

## 10. Evidence files tested

Real, controlled evidence at `~/Documents/24fps-evidence/Hikvision/`
(outside the repository, read-only, never modified — verified by
SHA-256 hash-stability tests before/after every parse pass):

| File | Size | Container (actual) | Sidecar |
|---|---|---|---|
| `A01_20260829100000.mp4` | 49,811,456 B | MPEG-PS (not ISOBMFF, despite `.mp4`) | `A01_20260829100000.txt` |
| `A01_20260831080000.mp4` | 33,034,240 B | MPEG-PS | `A01_20260831080000.txt` (+ `_001.txt`) |
| `A02_20260831080000.mp4` | 32,346,112 B | MPEG-PS | `A02_20260831080000.txt` (+ `_001.txt`, `.docx`) |

Also inspected (not directly used by the parser): nine device
configuration/screenshot images confirming the device fact sheet above,
and a `.docx` sidecar whose extracted text is identical to its
same-stem `.txt` sidecar.

## 11. Supported media formats

| Format | Status |
|---|---|
| `.mp4` (device-exported, MPEG-PS payload) | **SUPPORTED** — validated end to end against all three real files |
| `.dav` / `.mav` / `.iav` | **UNSUPPORTED** — the recorder's export UI offers these; no parsing implemented, no evidence tested |
| `.bin` | **UNSUPPORTED** — same |
| `.avi`, `.jpg`, `.xls`, `.zip` (export UI combinations) | **UNSUPPORTED** — not evidence tested |
| Native Hikvision HDD/filesystem (raw disk image) | **NOT_VALIDATED** — see Section 14 |

The device's export UI offering a format is not treated as this project
supporting it — only `.mp4` was actually tested and validated.

## 12. Metadata extraction

Identification is **two-signal, sidecar-corroborated**, not an
in-container magic byte:

1. Export filename convention: `<channel>_<YYYYMMDDHHMMSS>.mp4`.
2. A same-stem `.txt`/`.docx` device export-log sidecar (the DVR's own
   generated export receipt) carrying a "Copyright Hikvision Digital
   Technology Co., Ltd." banner and a
   `User: <user> Date:DD/MM/YYYY Time: HH:MM:SS made video export from
   device <serial>` line.

Both signals agreeing → `CONFIRMED_BY_EXPORT_LOG` (the strongest
identification this project makes without a native filesystem
acquisition). Filename alone (no sidecar, or a sidecar without the
banner) → `FILENAME_PATTERN_ONLY`, never treated as a positive Hikvision
identification. Neither → `UNSUPPORTED`.

A real, deterministic 4-byte `"IMKH"` marker precedes the MPEG-PS payload
at offset 0 in all three real files (confirmed by direct byte
inspection). This project **deliberately does not use it for vendor
identification** — no public documentation or reference implementation
establishes it as Hikvision-specific (unlike Phase 19's
`"HIKVISION@HANGZHOU"`, which two independent sources corroborate), and
treating an unattributed byte pattern as proof of vendor origin is
exactly the failure mode this project's rules forbid. `ffmpeg`/`ffprobe`
already skip past it on their own demuxer probing, so it needs no special
handling to decode — only to *identify*, and it is not used for that.

Once identified, technical metadata (codec, container, width, height,
fps, duration, audio presence/codec) is read via a real, read-only
`ffprobe` pass over the source evidence file itself
(`app.media.media_probe.probe_media`), reusing the same infrastructure
CP Plus's derived-artifact probing uses.

## 13. Timestamp normalization

- `start_original`: parsed from the export filename convention
  (`FILENAME_DERIVED`). The filename encodes no timezone; this project
  does not attach one implicitly — the device's confirmed `GMT+05:30` is
  supplied explicitly through the existing
  `app.core.timestamp_manager.TimestampManager.normalize_recording` flow,
  the same vendor-agnostic normalization architecture CP Plus uses. No
  Hikvision-only timestamp code was added.
- `end_original`: computed from `start_original` + the real, measured
  stream duration (never itself parsed from the filename — the naming
  convention encodes a start time only).
- The sidecar's own `export_timestamp` (when present) is recorded
  separately as **provenance** (`hikvision_export_timestamp` recording
  metadata) — it is the export *action* time, never confused with the
  recording's own start time.

## 14. Recovery capability

- **Deleted-recording recovery**: `UNSUPPORTED`,
  `not_supported_for_exported_media`. The evidence set is three
  standalone exported clips — there is no HIKBTREE recording index or
  deletion-marker structure to search (that requires a native
  filesystem/HDD acquisition, not implemented — see Section 15).
- **Damaged-segment recovery**: `UNSUPPORTED`, same reason code. No
  independent PS-packet-level carving/reconstruction is implemented
  beyond what FFmpeg's own demuxer already tolerates/reports during
  remux (surfaced as extraction warnings, not a separate recovery
  capability).
- **Media extraction** (a distinct, real, working capability — not
  "recovery"): `SUPPORTED`. See Section 19/final report.

## 15. Native Hikvision HDD/filesystem forensics

**NOT_VALIDATED.** Unchanged from Phase 19: `HikvisionAdapter`'s Track A
(`inspect_storage`/`parse_filesystem`) still only recognizes the
documented `"HIKVISION@HANGZHOU"` Master Sector marker within a bounded
search window, built entirely from public research
(`EvidenceBasis.PUBLIC_FORMAT_DOCUMENTATION`/
`PUBLIC_REFERENCE_IMPLEMENTATION`), never validated against any real
Hikvision HDD/disk image. No HIKBTREE recording index, embedded SQLite
metadata database, or channel/timestamp structure is parsed. Phase 26's
real evidence is exported-media only and does not change this.

## 16. AI compatibility

Once a Hikvision export is remuxed into a standard MP4 by
`app.media.decoder.remux_container_to_mp4`, it flows through the exact
same common recording pipeline CP Plus's own derived MP4 does — no
Hikvision-specific AI code exists or was added. YOLO/YuNet/ByteTrack/
motion detection/visual attribute search operate on the normalized
recording exactly as before. Visual search continues to report appearance
matches (timestamp, frame, bounding box) — never an identity claim.

## 17. Exact-seek behavior

`start_original` (filename-derived) + measured stream duration gives an
absolute wall-clock window for the recording, consistent with the
project's preferred `recording_start_timestamp + target_event_timestamp`
seek strategy. No fallback to `frame_number / fps` was needed for this
evidence set (each exported file is a single continuous recording with a
known start), and the device's configured 15 fps is never hardcoded — the
`fps` value used anywhere in the pipeline is always what `ffprobe`
measured on that specific file (see Section 6 for the observed
frame-rate ambiguity).

## 18. Integrity

Unchanged, common infrastructure: SHA-256 + MD5 via `app.hashing`, same
as CP Plus. Verified specifically for Hikvision by tests that hash every
real evidence file (and its sidecar) before and after a full parse/probe/
extraction pass and assert the digests are identical.

## 19. Provenance

Unchanged, common `app.core.provenance_manager` model. Every
Hikvision-derived artifact (`hikvision_export_master_mp4`,
`hikvision_export_preview_mp4`) is registered through
`EvidenceManager.register_artifact` exactly as CP Plus's derived
artifacts are, carrying source evidence, adapter/parser version
(`app.adapters.hikvision.parser.PARSER_VERSION`), and FFmpeg tool
version.

## 20. Audit

Unchanged, common `app.audit`/`app.core.audit_chain_manager`. No
Hikvision-specific audit system was created; evidence intake,
identification, enumeration, extraction, and case-access operations for
Hikvision evidence all flow through the same audit chain CP Plus's do.

## 21. Blockchain interaction

Unchanged, common `app.core.blockchain_manager`/`app.blockchain`. Only
the cryptographic/audit-state representation is ever anchored — never the
video itself. Hikvision evidence follows the identical
hash → processing → audit-state → anchor model as CP Plus.

## 22. Frontend integration

No Hikvision-specific frontend was built. The existing, already
vendor-generic components render Hikvision data automatically once the
backend reports it:

- `AdminOemSupport.tsx` (OEM/vendor support matrix) reads
  `support_level`/`evidence_basis`/`capabilities`/`limitations` directly
  from `AdapterRegistry.support_matrix()` — Hikvision's Phase 26 status
  (Track A/B split) renders with zero frontend code changes.
- `EvidenceView.tsx`'s derived-artifact label map gained two entries
  (`hikvision_export_master_mp4`, `hikvision_export_preview_mp4`) so
  Hikvision's derived master/preview files get the same
  human-readable, "derived (not source)" labeling CP Plus's already had.
  This was the only frontend change Phase 26 required.
- Device/evidence/recording/timeline/AI/findings/report views are all
  already vendor-neutral and required no changes.

## 23. Validation level

`SupportLevel.LEVEL_4_VALIDATED` for the exported-clip pathway ("Track
B"), validated against exactly the device/firmware/evidence scope in
Section 1, and `LEVEL_1_DETECTION` for the raw-filesystem pathway ("Track
A", unchanged from Phase 19, public-research-basis only). The adapter
reports the union honestly — `HikvisionAdapter.model_scope`/`.limitations`
spell out, per capability, which track it belongs to; neither track's
validation is generalized to the other, and Track B's validation is never
generalized beyond the DS-7A04HQHI-K1/V4.30.220 scope.

## 24. Known limitations

- Validated against **one** device/firmware/evidence scope only (Section
  1). No other Hikvision model/firmware/export-tool version has been
  tested.
- Only `.mp4` (MPEG-PS payload) exports are supported. `.dav`/`.mav`/
  `.iav`/`.bin` and other export-UI format combinations are
  `UNSUPPORTED` — not parsed, not tested.
- Identification requires a same-stem `.txt`/`.docx` sidecar next to the
  registered evidence file. A Hikvision-compatible `.mp4` with no
  sidecar (or a sidecar an examiner did not preserve/register alongside
  it) is reported as `FILENAME_PATTERN_ONLY`, never a confirmed
  identification — this is a genuine capability gap for evidence acquired
  without its sidecar, not a bug.
- The observed `ffprobe` frame-rate ambiguity (`r_frame_rate=25/1` vs.
  `avg_frame_rate=30/1`, neither matching the device's configured 15 fps)
  is unresolved and undocumented by any consulted source — recorded as
  an open question, not silently picked one way.
- No native Hikvision HDD/filesystem forensics (deleted recordings,
  HIKBTREE index, embedded SQLite metadata) — Section 15.
- No damaged-segment or deleted-recording recovery for exported media —
  Section 14.
- Audio in the derived MP4 outputs is a lossy AAC transcode (G.711
  mu-law has no MP4 container tag); only the video track is
  byte-preserved (`-c:v copy`). This is disclosed in provenance/warnings,
  never presented as a byte-identical audio original.

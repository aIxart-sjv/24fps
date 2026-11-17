# Phase 26 — Hikvision Integration (repaired and re-validated)

> **Validation scope: exactly one recorder.** Hikvision **DS-7A04HQHI-K1**
> ("Embedded Net DVR"), firmware **V4.30.220, Build 220216**, serial
> `0420220517CCWRJ98043179WCVU`. Nothing here is generalized to other Hikvision
> models, firmware versions, export formats or products.
>
> **What 24FPS supports:** analysis of `.mp4` clips exported from that recorder
> (which are Hikvision-header + MPEG-PS files, see §12) through the real
> upload → process → play → seek → AI → report workflow.
> **What it does not:** native Hikvision HDD/filesystem parsing, deleted-recording
> recovery, and the recorder's other export formats — see §14/§15/§24.

## 0. Why this document was rewritten

The first Phase 26 delivery reported "complete" and passed its tests, but **did not
work in the real application**. The user's own database showed it: three separate
attempts to upload Hikvision clips ended with `Device.vendor = NULL`, the
orchestrator's `enumeration` stage `skipped`, and **zero recordings** — so nothing
downstream (extraction, playback, seek, timeline, AI) ever ran.

**Why the tests did not catch it.** They copied a clip into a scratch evidence root
under its *original filename*, put its `.txt` export-log *next to it*, and registered
it *by path*. The real UI does none of that: it uploads **one file** through
`POST /cases/{id}/evidence/upload`, which stores it as
`<evidence_id>_<original filename>` and has no way to place a sidecar beside it. The
tests proved the parser on ideal input, not the application.

### Root causes found and fixed

| # | Root cause | Evidence | Fix |
|---|---|---|---|
| 1 | **Identification required an exactly-anchored filename *and* a same-stem sidecar** — both impossible for a UI upload (`EV-XXXX_A01_2026….mp4`, no sidecar). Every real upload was rejected, so nothing ran. | User DB (evidence 8/11/12): vendor NULL, `enumeration: skipped`, 0 recordings; reproduced live over HTTP. | Identify from the file's **own Hikvision header** (`IMKH`, §12); tolerate the upload prefix; sidecar is optional corroboration. |
| 2 | **Enumeration overwrote what extraction stored** (the "probe-owned field" bug class): after extraction `fps` went 15.0 → **30.0** and `container` `mp4` → `mpeg` on the next view of the Evidence tab. | Live: recording row after `GET /evidence/{id}/recordings`. | Probe-owned fields fill once, never overwritten; source facts kept separately as `source_*` metadata. |
| 3 | **`start_normalized` was wiped on every view** (shared bug — **also affects CP Plus**): metadata said normalization succeeded (`Asia/Kolkata`) while the row read `NULL`. | Scratch DB after a UI session. | `start/end_normalized` and `recovery_*` are never written by enumeration (both vendors). |
| 4 | **Recovery ran CP Plus's ADIT/CPAV engine on Hikvision files** and persisted a `RecoveryResult` citing "ADIT-v1", "CPAV record boundaries", `fragments_found: 1`, `confidence 0.5`. | Live `recovery-results`. | Vendor-aware branch: Hikvision layers only, honestly `unsupported` / `not_supported_for_exported_media`, no fragments/confidence/artifact. |
| 5 | **Declared frame rate is wrong for these files.** Container says `avg 30/1`, `r 25/1`; counting packets gives **15.00 fps** (9016 frames / 601.0 s). | `ffprobe -count_packets` on all three clips. | `Recording.fps` = measured rate; declared rates preserved in metadata + a visible discrepancy note. |
| 6 | **Seek landed 5–6 frames (0.24 s) early** and every overlay box was misplaced: the served preview's video track starts 0.2 s into the container (audio leads video in the source) but the UI assumed frame 0 ↔ `t=0`. | Measured in Brave via `requestVideoFrameCallback`. | Backend measures the played artifact's video start offset; the player adds it (per-clip: 0.200 s and 0.120 s measured). |
| 7 | **Recording IDs were the file stem and looked up globally** — the same clip in two cases would silently hijack the other case's row. | Code review + test. | `HIKVISION-EXPORT-<evidence_id>`, lookup scoped to the evidence (like CP Plus's `CPPLUS-ADIT-V1-<evidence_id>`). |
| 8 | **Timestamp source was `unknown` for Hikvision** ("no timestamp-source classification is implemented for vendor 'Hikvision'"); device model/firmware/serial never reached the `Device` row the UI reads; extraction "warnings" were an ffmpeg banner dump; the AAC encoder warned on every run (`64k` exceeds AAC-LC's 48 kbps ceiling at 8 kHz); the orchestrator told users only CP Plus was supported; an uploaded export-log was flagged as an unparseable DVR export. | Live data. | Each fixed (§13, §19, §22). |

Also corrected: the first delivery's docstrings claimed the `IMKH` marker was
"unattributable" and deliberately not used. That was wrong — see §12.

## 1. Validated device

Hikvision **DS-7A04HQHI-K1**, device name "Embedded Net DVR", hardware `0xe9711`,
serial `0420220517CCWRJ98043179WCVU`, 4 channels, firmware **V4.30.220, Build 220216**.
Confirmed from the recorder's own screens (photographed alongside the evidence).

## 2. Model / 3. Firmware / 4. Channels

`DS-7A04HQHI-K1` / `V4.30.220, Build 220216` / 4. **These are asserted only when an
export-log sidecar names the examiner-confirmed serial** (`KNOWN_HIKVISION_DEVICES`).
An MP4 alone cannot prove them — the header carries no device id, model or serial
(§12) — so a bare upload shows **"Not available"**, never a guessed model.

## 5. Resolution

Configured 1920×1080 (main stream, continuous + event). `ffprobe` measures the
encoded frame as **1920×1088** on all three clips; the project reports the measured
value and does not "correct" it.

## 6. FPS

| | value |
|---|---|
| Recorder configured | 15 fps |
| Container **declares** | `avg_frame_rate = 30/1`, `r_frame_rate = 25/1` (both wrong) |
| **Measured** (video packets ÷ stream duration) | A01_20260829100000 **15.001** (9016 / 601.027 s); A01_20260831080000 **15.004** (6700 / 446.55 s); A02_20260831080000 **15.001** (9016 / 601.024 s) |

Frame timestamps sit on a 25 Hz grid with alternating 40/80 ms gaps. `Recording.fps`
is the measured rate; the declared rates and the packet count are preserved as
`source_declared_avg_frame_rate` / `source_declared_r_frame_rate` /
`source_video_packet_count` / `source_measured_fps` plus a
`source_frame_rate_discrepancy` note the UI shows. 15, 25 and 30 are never hardcoded.

## 7. Codec

H.265/HEVC (Main, `yuv420p`, level 120); audio G.711 mu-law (`pcm_mulaw`), 8 kHz,
mono, 64 kb/s.

## 8. Timezone / 9. NTP

`GMT+05:30` "(Madras, Bombay, …)", DST disabled. NTP enabled (`time.windows.com`,
port 123, 30 min). **NTP being enabled is recorded as configuration only** — it does
not verify any individual timestamp; normalization stays `unverified`.

## 10. Evidence files tested

Real evidence at `~/Documents/24fps-evidence/Hikvision/` (read-only; SHA-256 verified
unchanged by tests before/after every pass).

| File | Size | Duration | Frames | Audio leads video by |
|---|---|---|---|---|
| `A01_20260829100000.mp4` | 49,811,456 B | 601.0 s | 9016 | 0.210 s |
| `A01_20260831080000.mp4` | 33,034,240 B | 446.6 s | 6700 | 0.109 s |
| `A02_20260831080000.mp4` | 32,346,112 B | 601.0 s | 9016 | 0.113 s |

Sidecars: a same-stem `.txt` for each (plus `_001.txt` extras and one `.docx` whose
text equals its `.txt`); nine photographed recorder screens.

**Independent timestamp check.** The camera's own burned-in OSD clock, read from the
*source* files at +20 s, shows `29-08-2026 Sat 10:00:20`, `31-08-2026 Mon 08:00:20`
and `31-08-2026 Mon 08:00:20` — matching each filename-derived start (10:00:00 /
08:00:00 / 08:00:00) plus 20 s. So `start_original` = the first video frame's time on
the recorder's local clock.

## 11. Supported media formats

| Format | 24FPS status | Actual test | Notes |
|---|---|---|---|
| `.mp4` (recorder export: Hikvision header + MPEG-PS, HEVC + G.711) | **SUPPORTED** (this recorder/firmware only) | 3 real clips uploaded through the real UI/HTTP, processed, played, sought, AI-analysed, reported | See §12 |
| `.dav`, `.mav`, `.iav`, `.bin` | **UNSUPPORTED / NOT_VALIDATED** | none — no such files exist in this project | The recorder's export UI offers them; that is not support. Registering one yields no recordings and the `unsupported_format` finding. |
| `.avi`, `.jpg`, `.xls`, `.zip` | **UNSUPPORTED** | none | Same. |
| Native Hikvision HDD / filesystem image | **NOT_VALIDATED** | none — no raw HDD/image exists | §15 |

## 12. Identification and metadata extraction

The evidence is **not** an ISOBMFF MP4. It is a 24-byte Hikvision media header at
offset 0, zero padding (4532 / 7204 / 6940 bytes in the three files), then a standard
MPEG-2 Program Stream. Decoding the header little-endian as Hikvision's public SDK
struct `HIK_MEDIAINFO` (`media_fourcc` = `0x484B4D49` "HKMI", stored on disk as
`IMKH`):

| field | value in all three files | ffprobe's *independent* reading of the payload |
|---|---|---|
| `system_format` | `0x0002` | MPEG-PS ✓ |
| `video_format` | `0x0005` | hevc ✓ |
| `audio_format` | `0x7110` | pcm_mulaw ✓ |
| channels / sample rate | 1 / 8000 | mono / 8000 Hz ✓ |

Every field agrees with an independent decoder, so this is a structured header, not a
coincidental byte pattern. The web search that attributed `HIK_MEDIAINFO`/`HKMI` to
Hikvision's `plaympeg4.h` could not fetch the header text itself, so only the
code↔codec pairings observed on real evidence are asserted (`OBSERVED_HEADER_CODE_MEANINGS`);
other codes are reported raw. The remaining 232 bytes of the header region are zero:
**it carries no timestamp and no device id/model/serial**, and the PS private-stream
(0xBD) payloads are not readable.

Identification, in order of strength (`HikvisionClipIdentificationStatus`):

1. `CONFIRMED_BY_EXPORT_LOG` (1.0) — filename matches `<channel>_<YYYYMMDDHHMMSS>.mp4`
   (any `<evidence_id>_` upload prefix tolerated) **and** a `.txt`/`.docx` export log
   with the "Copyright Hikvision Digital Technology" banner sits beside the clip
   (exact stem, original stem, or `<evidence_id>_<original stem>` — i.e. the log
   uploaded as its own evidence item). The only route to a serial → model/firmware.
2. `CONFIRMED_BY_CONTAINER_HEADER` (**0.9**) — the file itself has the header + PS
   payload. **Vendor only.** 0.5 if a decoded field contradicts ffprobe.
3. `FILENAME_PATTERN_ONLY` (0.4) — never persisted as Hikvision.
4. `UNSUPPORTED` — a generic MP4 (even named like a Hikvision export, even H.265) is
   **not** identified as Hikvision.

Extracted and preserved: vendor, model/firmware/serial/channels (confirmed device only),
camera/channel (`A01`/1), recording start (filename), end (start + measured duration),
duration, codec, container, resolution, **measured** fps and the declared rates, audio
presence/codec, decoded header, header↔ffprobe consistency, sidecar path/export time,
hashes, and the extraction parameters (§19).

## 13. Timestamp normalization

Uses the existing `TimestampManager`; no Hikvision-only engine.

- `start_original`: from the filename, timezone-naive, source `filename_derived`
  (previously `unknown`). `end_original` = start + measured duration.
- Recorder timezone is applied **only** for the examiner-confirmed device (`Asia/Kolkata`
  = fixed +05:30, with its provenance recorded); an examiner-supplied timezone always
  wins. Result: `unverified`, method `timezone_conversion`
  (08:00:00 IST → 02:30:00 UTC, verified in the UI).
- A bare upload has no knowable timezone → normalization stays **`unknown`**, the
  normalized columns stay empty, and the UI says "unresolved" / "not determined".
- Originals are never overwritten (§0 root cause 3 fixed). The sidecar's export time is
  recorded as provenance, never confused with the recording time.
- The UI labels normalized times **UTC** (they are naive-UTC values).

## 14. Recovery capability

`UNSUPPORTED`, reason `not_supported_for_exported_media`, for both deleted-recording
search and damaged-segment recovery: an exported clip has no recording index or deletion
marker, and no independent PS-level carving exists beyond what FFmpeg tolerates during
remux. The recovery card shows the real `RecoveryResult` (status `UNSUPPORTED`,
recovery confidence `—`, no artifact, no fragments). **Media extraction** (remux +
preview) is a separate, working capability and is not called "recovery".

## 15. Native Hikvision HDD / filesystem forensics

**NOT_VALIDATED.** Only the Phase 19 `HIKVISION@HANGZHOU` Master Sector marker is
recognized, from public research; no HIKBTREE index, embedded SQLite or deleted-record
structure is parsed; nothing was tested against a real disk image.
Exported-media analysis, native filesystem parsing, deleted-file recovery and fragment
reconstruction are four different things; only the first exists.

## 16. AI compatibility

Verified through the **real UI**: object + motion detection ran on the derived MP4 (165 s;
738 persons, cars, motorcycles… at 1 fps sampling); YOLOv8n + YuNet on `cuda:0`; results
list, click-to-seek and overlays work. Visual search "red shirt person" ran
(`deterministic_hsv_color_attribute_match`, 738 detections examined, 96 sightings) and
carries the disclaimer *"not identity recognition. Appearance similarity is evidence, not
proof"*. No Hikvision-specific AI code exists. Tracking was not exercised here.

## 17. Exact-seek behavior

Preferred: absolute detection timestamp − recording start (needs normalized time).
Fallback: `frame_number / fps` with the **measured** fps. Both are relative to the first
video frame, so the player adds the played file's measured video start offset
(`preview_video_start_offset_seconds`, e.g. 0.200 s / 0.120 s).

Measured in Brave with `requestVideoFrameCallback` (frame actually presented):

| | frame shown vs intended |
|---|---|
| before the fix (`t = N/fps`) | **−5 frames (−0.24 s)**, −6 at the end |
| after (`t = N/fps + offset`) | **−1 to −2 frames (0.04–0.08 s)** |

Real UI clicks on detections: frame 180 → −2, 300 → −1, car@105 → −2 (clip A01), and
225/360/510 → −1 each (clip A02, timestamp path). **Residual ≤ 2 frames** is the source's
non-uniform frame timing (40/80 ms gaps on a 25 Hz grid), which `frame/fps` cannot
represent: it deviates 0–0.127 s from true timestamps with no drift over the clip.
Removing it would need per-frame timestamps in the API — not done.

## 18. Integrity

Unchanged common infrastructure (SHA-256 + MD5). Uploaded copies are byte-identical to
the originals; `POST /evidence/{id}/verify` → `verified` for both algorithms; tests hash
originals before/after.

## 19. Provenance

Existing model. Artifacts carry `evidence_id` (source), `parent_artifact_id`
(preview ← master), ffmpeg `tool_version`, SHA-256/MD5. New: `extraction_parameters`
recording metadata — adapter + version, the exact operations, and the disclosure that
**only the video is byte-preserved**: the master's audio is re-encoded to AAC 48k (mu-law
has no MP4 tag) and the preview is an H.264 transcode ("NOT the forensic record").
Orchestrator stage events do not carry tool/parameters for *any* vendor (CP Plus's are
identical) — unchanged.

## 20. Audit

Existing chain; no Hikvision-specific audit. Verified `valid: true` over the Hikvision
runs (18 events).

## 21. Blockchain

**NOT_VALIDATED on a real chain.** This deployment has `BLOCKCHAIN_PROVIDER=none`:
anchoring returns HTTP 503 and no anchor exists — none is claimed. A test creates and
verifies an anchor for a Hikvision case with the in-memory `LocalTestBlockchainProvider`
(not a blockchain transaction) to show the case participates in the existing flow
unchanged; only the audit-state hash is anchored, never video.

## 22. Frontend integration

No Hikvision-specific UI; existing components, real backend data only.

- Evidence tab: source→derived chain labels, **measured frame rate** + the declared-rate
  discrepancy note, "Source Timezone Applied", "Parse Confidence" (moved out from under
  the recovery heading), "Normalized Start (UTC)", and a recovery card that reads the
  real `RecoveryResult`.
- Acquisition tab: Vendor, **Model, Firmware, Serial, Channels** (`Not available` unless
  confirmed), method, confidence.
- Player: video-start-offset compensation for seek and overlay-frame matching.

Verified end-to-end in a real browser (Brave 149): upload via the modal, "Run automatic
processing", every tab, playback (H.264 + AAC, HTTP 206 range streaming, no console
errors), detection click → seek → overlay, timeline, findings, report.

## 23. Validation level

`SupportLevel.LEVEL_4_VALIDATED` for the exported-clip pathway ("Track B"), for the
single device/firmware/evidence scope in §1. `LEVEL_1_DETECTION` for the raw-filesystem
pathway ("Track A", unchanged, public-research only). Not generalized.

## 24. Known limitations

- One recorder/firmware only; other Hikvision models, firmware and export tools untested.
- Model/firmware/serial/channels need the export-log sidecar (beside the clip, or uploaded
  as a second evidence item **before** processing). Linked by filename only. Uploaded
  logs are recognized and not flagged; without one, the fields read "Not available".
- Without the sidecar the recorder timezone is unknown → normalized times are `unknown`
  (originals still shown; examiner can supply a timezone).
- `.dav`/`.mav`/`.iav`/`.bin`/`.avi`/… unsupported; native HDD/deleted recovery not validated.
- Seek is accurate to ≤ 2 frames (§17); the H.265 master often does not play in
  browsers, so playback uses the H.264 preview (≈115 MB for 10 min).
- Derived audio is lossy AAC; only video bytes are preserved in the master.
- Blockchain not configured here; tracking and PDF visual content were not exercised in
  the browser.

## 25. Test evidence

- **Backend:** 1283 passed, 5 skipped (pre-existing: this environment's pyewf build cannot
  write E01 fixtures), `ruff` clean, `mypy` clean (276 source files). +61 tests over the
  first delivery, including the CP Plus regression tests (all pass).
  - `test_hikvision_upload_workflow_real_evidence_integration.py` (14): the **real UI path** —
    single-file upload through `POST /cases/{id}/evidence/upload`, `POST /cases/{id}/process`,
    then device, recordings, metadata, recovery, byte-range streaming, immutability,
    provenance, and blockchain-manager participation, on real evidence, over HTTP.
  - `test_hikvision_identification_and_pipeline.py` (43, synthetic bytes): header decode,
    the "generic MP4 is never Hikvision" guard, prefix-tolerant filenames, sidecar
    discovery (incl. `.docx` and prefixed uploads), recording-scoping, re-enumeration
    field ownership (both vendors), recovery truthfulness, timezone handling, export-log
    evidence.
  - `test_media_probe.py` (+3), `test_recording_manager.py` (+1, CP Plus shared-bug regression).
- **Frontend:** typecheck clean, 27 unit tests, production build OK.
- **Database:** Alembic `d886e2345a1b (head)`, `alembic check`: no new operations; **no
  migration needed** (no model changed).
- **Real browser (Brave 149) end-to-end**, on isolated data: upload via the modal → "Run
  automatic processing" → Evidence / Acquisition / Recovery / Timeline / AI / Findings →
  playback → detection click → seek → overlay → JSON + PDF report; two scenarios (bare
  clip; clip + its export log uploaded as a second evidence item).
- Not tested: Firefox playback, Windows/packaged build, object tracking (ByteTrack), any
  Hikvision hardware other than the one recorder, any real blockchain.

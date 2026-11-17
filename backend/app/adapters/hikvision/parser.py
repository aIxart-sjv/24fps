"""
Hikvision exported-media parser (Phase 26, "Hikvision Integration").

Identifies and describes an already-exported Hikvision `.mp4` clip (Master
Specification Section 9, acquisition Path 1, "native export"). Despite the
extension, the real evidence is NOT an ISOBMFF MP4: it is Hikvision's own
24-byte media header (`IMKH`, see `app.adapters.hikvision.models`) followed
by zero padding and then a standard MPEG-2 Program Stream carrying HEVC
video and G.711 mu-law audio.

HOW IDENTIFICATION WORKS (and why it changed)
---------------------------------------------
The first Phase 26 delivery identified a clip only by (a) an exactly-anchored
export filename AND (b) a same-stem `.txt`/`.docx` device export-log sidecar.
The real application can supply neither: the browser UI uploads exactly one
file through `POST /cases/{id}/evidence/upload`, which stores it as
`<evidence_id>_<original filename>` -- so every real upload was rejected, and
nothing downstream ever ran. Identification now reads what is actually in the
evidence, in this order of strength:

  1. `CONFIRMED_BY_EXPORT_LOG` (confidence 1.0): the export filename matches
     `<channel>_<YYYYMMDDHHMMSS>.mp4` (after tolerating any leading
     `<evidence_id>_` prefix) AND a sidecar export log carrying the
     "Copyright Hikvision Digital Technology" banner sits next to the clip.
     Only this status can yield a device serial (-> known-device model).
  2. `CONFIRMED_BY_CONTAINER_HEADER` (0.9): the file itself starts with
     Hikvision's `IMKH` media header and wraps an MPEG-PS payload. Vendor
     only -- never a model/serial/firmware. Dropped to 0.5 if a decoded
     header field contradicts ffprobe's independent reading of the payload.
  3. `FILENAME_PATTERN_ONLY` (0.4): only the filename matches. Never treated
     as a Hikvision identification (a filename can be anything).
  4. `UNSUPPORTED`.

TECHNICAL METADATA
------------------
Read from a read-only `ffprobe` pass over the source file
(`app.media.media_probe.probe_media`) -- no vendor-specific stream
reconstruction is needed. One real-evidence quirk is handled explicitly: the
container DECLARES `avg_frame_rate=30/1` and `r_frame_rate=25/1` for every
real clip, but counting video packets gives ~15.00 fps (the recorder's
configured rate; frames sit on a 25 Hz timestamp grid with 40/80 ms gaps).
`fps` is therefore the MEASURED rate (`-count_packets`), and both declared
rates are preserved separately so the discrepancy stays visible. The
device's configured 15 fps is never substituted for a measurement, and 25/30
are never hardcoded.

Distinct from `app.adapters.hikvision.detector.detect_hikvision_structure`
(Phase 19, raw DVR filesystem "Master Sector" detection): this module parses
the *exported clip*, not the DVR's internal filesystem.
"""

from __future__ import annotations

import re
import struct
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element  # noqa: S405 -- typing only, never parses untrusted XML

from defusedxml import ElementTree as defused_et

from app.acquisition.storage_reader import EvidenceStorageReader
from app.adapters.hikvision.models import (
    HIKVISION_MEDIA_HEADER_MAGIC,
    HIKVISION_MEDIA_HEADER_SIZE,
    HIKVISION_MEDIA_HEADER_STRUCT,
    HIKVISION_PS_SEARCH_WINDOW,
    MPEG_PS_PACK_START_CODE,
    OBSERVED_HEADER_CODE_MEANINGS,
    HikvisionClipFilenameInfo,
    HikvisionClipIdentificationResult,
    HikvisionClipIdentificationStatus,
    HikvisionClipTimestampSource,
    HikvisionEnumerationResult,
    HikvisionExportLogSidecar,
    HikvisionMediaHeader,
    HikvisionRecordingRecord,
    lookup_known_hikvision_device,
)
from app.media.media_probe import MediaProbeResult, probe_media

#: Version of this parser implementation (Master Specification Section 59,
#: "store parser version"). Validated against exactly one device/firmware
#: (DS-7A04HQHI-K1, V4.30.220 Build 220216) and three real export files --
#: never treated as universal Hikvision support (Section 17).
PARSER_VERSION = "0.3.0"

#: Confidence per identification status (see the module docstring).
CONFIDENCE_EXPORT_LOG = 1.0
CONFIDENCE_CONTAINER_HEADER = 0.9
CONFIDENCE_CONTAINER_HEADER_CONTRADICTED = 0.5
CONFIDENCE_FILENAME_ONLY = 0.4

# `<channel>_<YYYYMMDDHHMMSS>` at the END of the stem, tolerating any leading
# prefix ending in `_` (the upload route stores `<evidence_id>_<name>`, and the
# evidence id itself may contain hyphens/underscores). Anchored at the end so a
# prefix can never be mistaken for the channel label. Observed channel labels
# are `A01`/`A02` (letters + digits); 1+ digits accepted since no second export
# tool has been observed to confirm digit width is fixed.
_FILENAME_RE = re.compile(r"^(?:.*_)?(?P<channel>[A-Za-z]+\d+)_(?P<start>\d{14})$")

_COPYRIGHT_RE = re.compile(r"Copyright\s+Hikvision\s+Digital\s+Technology", re.IGNORECASE)

# The real sidecar log line, e.g.:
#   "User: admin Date:30/08/2026 Time: 19:04:47 made video export from
#    device 0420220517CCWRJ98043179WCVU"
_EXPORT_LINE_RE = re.compile(
    r"User:\s*(?P<user>\S+)\s+Date:\s*(?P<date>\d{2}/\d{2}/\d{4})\s+"
    r"Time:\s*(?P<time>\d{2}:\d{2}:\d{2})\s+made\s+video\s+export\s+from\s+device\s+(?P<serial>\S+)"
)

# The sidecar's own "N logs output" line (observed: "0 logs output" / "2 logs output").
_LOG_COUNT_RE = re.compile(r"(?P<count>\d+)\s+logs?\s+output", re.IGNORECASE)

_DOCX_TEXT_TAG = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"

#: Relative disagreement between a declared frame rate and the measured one
#: above which the discrepancy is reported.
_FPS_DISCREPANCY_TOLERANCE = 0.05

#: A real export log is a few hundred bytes to a few KB (observed 518 B - 2 KB). Anything larger
#: is not read as a sidecar: sidecar discovery and `is_hikvision_export_log` open files supplied as
#: evidence, so they stay bounded.
_MAX_SIDECAR_BYTES = 1024 * 1024

#: `-count_packets` reads every video packet header (no decoding); allow more
#: than the default probe timeout for multi-gigabyte exports.
_COUNT_PACKETS_TIMEOUT_SECONDS = 180


def _split_export_name(name: str) -> re.Match[str] | None:
    path = Path(name)
    if path.suffix.lower() != ".mp4":
        return None
    return _FILENAME_RE.match(path.stem)


def parse_hikvision_export_filename(name: str) -> HikvisionClipFilenameInfo | None:
    """Best-effort parse of a Hikvision export filename's channel/start.

    Tolerates a leading `<evidence_id>_` prefix (see `_FILENAME_RE`).

    Args:
        name: A filename (not a full path).

    Returns:
        A `HikvisionClipFilenameInfo`, or `None` if `name` does not match the
        expected `<channel>_<YYYYMMDDHHMMSS>.mp4` convention at all (never a
        partially-guessed result).
    """
    match = _split_export_name(name)
    if match is None:
        return None
    try:
        # Deliberately naive: the filename encodes no timezone. The device's own
        # configured timezone is external context, not something this filename
        # asserts -- attaching one here would fabricate precision. It is applied
        # (only for an examiner-confirmed device, or when an examiner supplies
        # it) through `TimestampManager.normalize_recording`.
        start = datetime.strptime(match.group("start"), "%Y%m%d%H%M%S")  # noqa: DTZ007
    except ValueError:
        return None
    channel_label = match.group("channel")
    digits = re.sub(r"^[A-Za-z]+", "", channel_label)
    channel_number = int(digits) if digits.isdigit() else None
    return HikvisionClipFilenameInfo(
        channel_label=channel_label, channel_number=channel_number, start_original=start
    )


def read_hikvision_media_header(reader: EvidenceStorageReader) -> HikvisionMediaHeader | None:
    """Decode the file's leading Hikvision media header, if it has one.

    A bounded read (`HIKVISION_PS_SEARCH_WINDOW` bytes at most) at a FIXED
    offset (0): checks the `IMKH` magic, decodes the 24-byte struct
    (little-endian), and looks for the standard MPEG-PS pack start code after
    it. Never raises for malformed/truncated/empty input.

    Returns:
        A `HikvisionMediaHeader` (with `ps_payload_offset=None` when no PS
        start code was found in the window), or `None` when the file does not
        begin with the Hikvision header at all.
    """
    try:
        size = reader.size()
        if size < HIKVISION_MEDIA_HEADER_SIZE:
            return None
        buffer = reader.read(0, min(size, HIKVISION_PS_SEARCH_WINDOW))
    except (OSError, ValueError):
        return None
    if len(buffer) < HIKVISION_MEDIA_HEADER_SIZE or not buffer.startswith(
        HIKVISION_MEDIA_HEADER_MAGIC
    ):
        return None
    (
        _fourcc,
        version,
        device_id,
        system_format,
        video_format,
        audio_format,
        audio_channels,
        audio_bits,
        audio_sample_rate,
        audio_bitrate_field,
    ) = struct.unpack_from(HIKVISION_MEDIA_HEADER_STRUCT, buffer, 0)
    ps_offset = buffer.find(MPEG_PS_PACK_START_CODE, HIKVISION_MEDIA_HEADER_SIZE)
    return HikvisionMediaHeader(
        version=version,
        device_id=device_id,
        system_format=system_format,
        video_format=video_format,
        audio_format=audio_format,
        audio_channels=audio_channels,
        audio_bits_per_sample=audio_bits,
        audio_sample_rate=audio_sample_rate,
        audio_bitrate_field=audio_bitrate_field,
        ps_payload_offset=ps_offset if ps_offset != -1 else None,
    )


def _read_docx_text(path: Path) -> str | None:
    """Extract plain text from a `.docx`'s `word/document.xml` part.

    Uses `defusedxml` (never stdlib `xml.etree` directly): this parses a file
    supplied as evidence, i.e. untrusted input.

    Returns:
        The concatenated text, or `None` if `path` is not a readable,
        well-formed `.docx` (never raises).
    """
    try:
        with zipfile.ZipFile(path) as archive:
            data = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile):
        return None
    try:
        root: Element = defused_et.fromstring(data)
    except Exception:  # noqa: BLE001 -- any malformed-XML failure mode is equally "unreadable"
        return None
    return "".join(node.text or "" for node in root.iter(_DOCX_TEXT_TAG))


def _read_sidecar_text(path: Path) -> str | None:
    """Read a `.txt`/`.docx` sidecar's text content. Never raises; refuses files over
    `_MAX_SIDECAR_BYTES` (a real export log is ~2 KB at most)."""
    try:
        if path.stat().st_size > _MAX_SIDECAR_BYTES:
            return None
    except OSError:
        return None
    if path.suffix.lower() == ".docx":
        return _read_docx_text(path)
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _parse_sidecar_text(source_path: Path, text: str) -> HikvisionExportLogSidecar:
    """Extract the fields this project can actually read from a Hikvision
    export-log sidecar's own text. Every field stays `None` when its expected
    line is not found -- never guessed."""
    is_banner = _COPYRIGHT_RE.search(text) is not None
    export_match = _EXPORT_LINE_RE.search(text)
    device_serial = export_match.group("serial") if export_match else None
    export_user = export_match.group("user") if export_match else None
    export_timestamp: datetime | None = None
    if export_match is not None:
        try:
            export_timestamp = datetime.strptime(  # noqa: DTZ007 -- see parse_hikvision_export_filename
                f"{export_match.group('date')} {export_match.group('time')}", "%d/%m/%Y %H:%M:%S"
            )
        except ValueError:
            export_timestamp = None
    log_count_match = _LOG_COUNT_RE.search(text)
    log_entry_count = int(log_count_match.group("count")) if log_count_match else None
    return HikvisionExportLogSidecar(
        source_path=str(source_path),
        is_hikvision_copyright_banner_present=is_banner,
        device_serial=device_serial,
        export_user=export_user,
        export_timestamp=export_timestamp,
        log_entry_count=log_entry_count,
        raw_text=text,
    )


def is_hikvision_export_log(path: Path) -> bool:
    """Whether `path` is a Hikvision device export log (`.txt`/`.docx` carrying the
    "Copyright Hikvision Digital Technology" banner) -- a supporting document that accompanies
    an exported clip, not a recording. Bounded (`_MAX_SIDECAR_BYTES`), never raises."""
    if path.suffix.lower() not in (".txt", ".docx"):
        return False
    text = _read_sidecar_text(path)
    return text is not None and _COPYRIGHT_RE.search(text) is not None


def _find_sidecar(evidence_path: Path, original_stem: str) -> HikvisionExportLogSidecar | None:
    """Look for a `.txt`/`.docx` export-log sidecar next to `evidence_path`.

    A non-recursive look at the evidence file's own directory (never an
    unbounded search). Candidates, in order (`.txt` before `.docx`; the two
    have been observed to carry identical text):

      1. a file with the stored clip's own stem (`<stored stem>.txt`),
      2. a file with the ORIGINAL export stem (`A01_20260829100000.txt`),
      3. a file whose name ends in `_<original stem>` -- i.e. the same
         sidecar uploaded as its own evidence item, which the upload route
         also prefixes with its `<evidence_id>_`.

    The link between clip and sidecar is by filename only (the sidecar text
    never names the clip) -- the caller reports that honestly.

    Returns:
        The parsed sidecar, or `None` if none exists or could be read.
    """
    parent = evidence_path.parent
    stems = [evidence_path.stem]
    if original_stem != evidence_path.stem:
        stems.append(original_stem)
    for suffix in (".txt", ".docx"):
        candidates = [parent / f"{stem}{suffix}" for stem in stems]
        try:
            candidates += sorted(parent.glob(f"*_{original_stem}{suffix}"))
        except OSError:
            pass
        for candidate in candidates:
            if candidate.is_file():
                text = _read_sidecar_text(candidate)
                if text is not None:
                    return _parse_sidecar_text(candidate, text)
    return None


def identify_exported_clip(reader: EvidenceStorageReader) -> HikvisionClipIdentificationResult:
    """Identify whether `reader`'s evidence is a genuine Hikvision-exported clip.

    Args:
        reader: An already-open `EvidenceStorageReader`. Not closed here. The
            file header is read through the reader; the filename and sidecar
            are found via `reader.metadata()["source_path"]` when present (a
            reader without one can still be identified by its header).

    Returns:
        A `HikvisionClipIdentificationResult`. Always structured, never raises.
    """
    media_header = read_hikvision_media_header(reader)
    header_confirmed = media_header is not None and media_header.ps_payload_offset is not None

    warnings: list[str] = []
    if media_header is not None and media_header.ps_payload_offset is None:
        warnings.append(
            "the file begins with the Hikvision 'IMKH' media header but no MPEG-PS pack start "
            f"code was found within the first {HIKVISION_PS_SEARCH_WINDOW} bytes -- this "
            "payload variant is not validated, so the header alone is not treated as "
            "identification"
        )

    source_path_str = reader.metadata().get("source_path")
    evidence_path = (
        Path(source_path_str) if isinstance(source_path_str, str) and source_path_str else None
    )
    filename_info = parse_hikvision_export_filename(evidence_path.name) if evidence_path else None

    sidecar: HikvisionExportLogSidecar | None = None
    if evidence_path is not None and filename_info is not None:
        match = _split_export_name(evidence_path.name)
        assert match is not None  # parse succeeded above
        original_stem = f"{match.group('channel')}_{match.group('start')}"
        sidecar = _find_sidecar(evidence_path, original_stem)
    sidecar_confirmed = sidecar is not None and sidecar.is_hikvision_copyright_banner_present

    if sidecar is not None and not sidecar.is_hikvision_copyright_banner_present:
        warnings.append(
            f"sidecar {Path(sidecar.source_path).name!r} was found but does not carry the "
            "Hikvision copyright banner, so it does not corroborate anything"
        )

    if sidecar_confirmed:
        assert sidecar is not None
        known_device = (
            lookup_known_hikvision_device(sidecar.device_serial)
            if sidecar.device_serial is not None
            else None
        )
        reason = (
            "filename matches the Hikvision export naming convention and sidecar "
            f"{Path(sidecar.source_path).name!r} confirms the Hikvision copyright banner"
            + (
                f" and device serial {sidecar.device_serial!r}"
                if sidecar.device_serial is not None
                else " (no device serial line found in the sidecar)"
            )
            + (
                f"; serial matches examiner-confirmed device {known_device.model!r}"
                if known_device is not None
                else ""
            )
            + (
                "; the file's own Hikvision media header is also present"
                if header_confirmed
                else ""
            )
            + ". The sidecar is linked by filename only (it never names the clip)."
        )
        return HikvisionClipIdentificationResult(
            status=HikvisionClipIdentificationStatus.CONFIRMED_BY_EXPORT_LOG,
            filename_info=filename_info,
            sidecar=sidecar,
            reason=reason,
            warnings=warnings,
            known_device=known_device,
            media_header=media_header,
        )

    if header_confirmed:
        assert media_header is not None
        return HikvisionClipIdentificationResult(
            status=HikvisionClipIdentificationStatus.CONFIRMED_BY_CONTAINER_HEADER,
            filename_info=filename_info,
            sidecar=sidecar,
            reason=(
                "the file begins with Hikvision's own 'IMKH' media header and wraps an MPEG-PS "
                f"payload (first pack start code at offset {media_header.ps_payload_offset}); "
                "vendor confirmed from the file itself. No export-log sidecar corroborates it, "
                "so recorder model/serial/firmware are NOT determined"
            ),
            warnings=warnings,
            media_header=media_header,
        )

    if filename_info is not None:
        return HikvisionClipIdentificationResult(
            status=HikvisionClipIdentificationStatus.FILENAME_PATTERN_ONLY,
            filename_info=filename_info,
            sidecar=sidecar,
            reason=(
                "only the filename matches the Hikvision export naming convention; the file has "
                "no Hikvision media header and no corroborating export-log sidecar -- NOT "
                "treated as a confirmed Hikvision identification"
            ),
            warnings=warnings,
            media_header=media_header,
        )

    return HikvisionClipIdentificationResult(
        status=HikvisionClipIdentificationStatus.UNSUPPORTED,
        filename_info=None,
        sidecar=sidecar,
        reason=(
            "no Hikvision media header ('IMKH') at offset 0, no export-log sidecar, and the "
            "filename does not match '<channel>_<YYYYMMDDHHMMSS>.mp4'"
        ),
        warnings=warnings,
        media_header=media_header,
    )


def _header_probe_consistency(
    header: HikvisionMediaHeader, probe: MediaProbeResult
) -> tuple[str, bool]:
    """Compare the decoded Hikvision header against ffprobe's independent reading.

    Only pairings observed on real evidence (`OBSERVED_HEADER_CODE_MEANINGS`)
    are asserted; any other code is reported as "not cross-checked".

    Returns:
        `(human-readable summary, any_contradiction)`.
    """
    raw = probe.raw if isinstance(probe.raw, dict) else {}
    raw_streams = raw.get("streams")
    streams: list[Any] = raw_streams if isinstance(raw_streams, list) else []
    video = next(
        (s for s in streams if isinstance(s, dict) and s.get("codec_type") == "video"), None
    )
    audio = next(
        (s for s in streams if isinstance(s, dict) and s.get("codec_type") == "audio"), None
    )

    parts: list[str] = []
    contradiction = False

    def check(field: str, code: int, actual: str | None) -> None:
        nonlocal contradiction
        expected = OBSERVED_HEADER_CODE_MEANINGS[field].get(code)
        if expected is None:
            parts.append(
                f"{field}={code:#06x}: not cross-checked (code not observed on real evidence)"
            )
        elif actual is None:
            contradiction = True
            parts.append(f"{field}={code:#06x}: header implies {expected!r} but ffprobe found none")
        elif actual == expected:
            parts.append(f"{field}={code:#06x}: agrees with ffprobe ({actual!r})")
        else:
            contradiction = True
            parts.append(
                f"{field}={code:#06x}: header implies {expected!r} but ffprobe says {actual!r}"
            )

    check("system_format", header.system_format, probe.format_name)
    check("video_format", header.video_format, video.get("codec_name") if video else None)
    check("audio_format", header.audio_format, audio.get("codec_name") if audio else None)
    if audio is not None:
        channels = audio.get("channels")
        try:
            rate: int | None = int(str(audio.get("sample_rate")))
        except ValueError:
            rate = None
        for label, header_value, actual in (
            ("audio_channels", header.audio_channels, channels),
            ("audio_sample_rate", header.audio_sample_rate, rate),
        ):
            if actual is None:
                parts.append(f"{label}={header_value}: ffprobe reported none")
            elif header_value == actual:
                parts.append(f"{label}={header_value}: agrees with ffprobe")
            else:
                contradiction = True
                parts.append(f"{label}={header_value}: ffprobe says {actual}")
    return "; ".join(parts), contradiction


class HikvisionParser:
    """Parses Hikvision exported-media evidence through the common
    `EvidenceStorageReader` abstraction.

    VALIDATED SCOPE: `.mp4` exports with the Hikvision `IMKH` header wrapping an
    MPEG-PS payload (HEVC + G.711 mu-law), from one confirmed recorder. Anything
    else honestly reports `FILENAME_PATTERN_ONLY`/`UNSUPPORTED` rather than
    guessing. Does not decode video frames itself -- that is FFmpeg's job
    (`app.media.decoder.remux_container_to_mp4`), consistent with Master
    Specification Section 19.
    """

    def __init__(
        self, reader: EvidenceStorageReader, *, source_evidence_id: str | None = None
    ) -> None:
        """
        Args:
            reader: An already-open `EvidenceStorageReader` for the evidence to
                parse. Not closed by this class -- the caller owns its lifecycle.
            source_evidence_id: The evidence item's business ID. Used to make the
                recording id evidence-scoped (the same clip registered in two
                cases must not collide) and attached to any records produced.
        """
        self._reader = reader
        self._source_evidence_id = source_evidence_id

    def identify(self) -> HikvisionClipIdentificationResult:
        """Answer "is this evidence a genuine Hikvision-exported clip?"."""
        return identify_exported_clip(self._reader)

    def enumerate_recordings(self) -> HikvisionEnumerationResult:
        """Enumerate recordings discoverable from this Hikvision export file.

        Returns:
            A `HikvisionEnumerationResult`. When identification finds no
            Hikvision signal at all, an empty recording list carrying that
            status/reason. Otherwise exactly one `HikvisionRecordingRecord`
            (one exported clip is one recording -- no multi-recording index
            exists in an exported file).
        """
        identification = self.identify()
        if identification.status == HikvisionClipIdentificationStatus.UNSUPPORTED:
            return HikvisionEnumerationResult(
                status=identification.status,
                recordings=[],
                warnings=list(identification.warnings),
                parser_version=PARSER_VERSION,
                reason=identification.reason,
            )

        source_path_str = self._reader.metadata().get("source_path")
        evidence_path = Path(source_path_str) if isinstance(source_path_str, str) else None

        warnings = list(identification.warnings)
        probe: MediaProbeResult | None = None
        if evidence_path is not None:
            probe = probe_media(
                evidence_path, count_packets=True, timeout=_COUNT_PACKETS_TIMEOUT_SECONDS
            )
            if not probe.available:
                warnings.append(
                    "packet-counting ffprobe pass failed ("
                    + "; ".join(probe.warnings)
                    + "); retrying without a measured frame rate"
                )
                probe = probe_media(evidence_path)
        else:
            warnings.append("no source_path available to probe media")

        codec = container = None
        width = height = None
        duration_ms: int | None = None
        has_audio: bool | None = None
        audio_codec: str | None = None
        declared_avg = declared_r = measured = None
        packet_count: int | None = None
        header_consistency: str | None = None
        contradiction = False

        if probe is not None and probe.available:
            warnings.extend(probe.warnings)
            codec, container = probe.codec, probe.format_name
            width, height = probe.width, probe.height
            declared_avg, declared_r = probe.fps, probe.r_frame_rate
            measured, packet_count = probe.measured_fps, probe.video_packet_count
            if probe.duration_seconds is not None:
                duration_ms = int(round(probe.duration_seconds * 1000))
            raw_streams = probe.raw.get("streams") if isinstance(probe.raw, dict) else None
            if isinstance(raw_streams, list):
                audio_streams = [
                    s for s in raw_streams if isinstance(s, dict) and s.get("codec_type") == "audio"
                ]
                has_audio = len(audio_streams) > 0
                if audio_streams and isinstance(audio_streams[0].get("codec_name"), str):
                    audio_codec = audio_streams[0]["codec_name"]
            if identification.media_header is not None:
                header_consistency, contradiction = _header_probe_consistency(
                    identification.media_header, probe
                )
                if contradiction:
                    warnings.append(
                        "the decoded Hikvision header contradicts ffprobe's reading of the "
                        f"payload ({header_consistency}); identification confidence reduced"
                    )
        elif probe is not None:
            warnings.extend(probe.warnings)

        # Recording.fps: the MEASURED rate when available, else the declared
        # average (flagged) -- never the device's configured 15, never 25/30.
        fps: float | None
        if measured is not None:
            fps = round(measured, 4)
            declared = [v for v in (declared_avg, declared_r) if v]
            if any(abs(v - measured) / measured > _FPS_DISCREPANCY_TOLERANCE for v in declared):
                warnings.append(
                    f"container declares avg_frame_rate={declared_avg} / r_frame_rate="
                    f"{declared_r} fps, but {packet_count} video packets over the stream "
                    f"duration measure {measured:.3f} fps; the measured value is used for "
                    "Recording.fps and the declared values are preserved as metadata"
                )
        else:
            fps = declared_avg
            if fps is not None:
                warnings.append(
                    "a measured frame rate could not be obtained; Recording.fps is the "
                    "container's DECLARED avg_frame_rate and may be inaccurate"
                )

        filename_info = identification.filename_info
        start_original = filename_info.start_original if filename_info else None
        channel_label = filename_info.channel_label if filename_info else None
        channel_number = filename_info.channel_number if filename_info else None
        if filename_info is None:
            warnings.append(
                "the export filename did not match '<channel>_<YYYYMMDDHHMMSS>.mp4': camera, "
                "channel and recording start are Not Determined (the file's own header and "
                "payload carry no wall-clock time)"
            )
        end_original: datetime | None = None
        if start_original is not None and duration_ms is not None:
            end_original = start_original + timedelta(milliseconds=duration_ms)

        status = identification.status
        if status == HikvisionClipIdentificationStatus.CONFIRMED_BY_EXPORT_LOG:
            confidence = CONFIDENCE_EXPORT_LOG
        elif status == HikvisionClipIdentificationStatus.CONFIRMED_BY_CONTAINER_HEADER:
            confidence = (
                CONFIDENCE_CONTAINER_HEADER_CONTRADICTED
                if contradiction
                else CONFIDENCE_CONTAINER_HEADER
            )
        else:
            confidence = CONFIDENCE_FILENAME_ONLY

        # Evidence-scoped (like CP Plus's `CPPLUS-ADIT-V1-<evidence_id>`): recordings are
        # looked up by this id, so the same clip in two cases must not share one.
        if self._source_evidence_id:
            recording_id = f"HIKVISION-EXPORT-{self._source_evidence_id}"
        elif evidence_path is not None:
            recording_id = evidence_path.stem
        else:
            recording_id = "HIKVISION-EXPORT-UNKNOWN"

        record = HikvisionRecordingRecord(
            recording_id=recording_id,
            camera_id=channel_label,
            channel=channel_number,
            start_original=start_original,
            end_original=end_original,
            duration_ms=duration_ms,
            codec=codec,
            container=container,
            width=width,
            height=height,
            fps=fps,
            has_audio=has_audio,
            audio_codec=audio_codec,
            source_evidence_id=self._source_evidence_id,
            identification=identification,
            parser_version=PARSER_VERSION,
            confidence=confidence,
            warnings=warnings,
            timestamp_source=(
                HikvisionClipTimestampSource.FILENAME_DERIVED
                if start_original is not None
                else HikvisionClipTimestampSource.UNKNOWN
            ),
            source_container=container,
            declared_avg_frame_rate=declared_avg,
            declared_r_frame_rate=declared_r,
            video_packet_count=packet_count,
            measured_fps=round(measured, 4) if measured is not None else None,
            header_probe_consistency=header_consistency,
        )
        return HikvisionEnumerationResult(
            status=status,
            recordings=[record],
            warnings=warnings,
            parser_version=PARSER_VERSION,
            reason=identification.reason,
        )

"""
Hikvision exported-media parser (Phase 26, "Hikvision Integration").

VALIDATION STATUS: identifies an already-exported Hikvision `.mp4` clip
(Master Specification Section 9, acquisition Path 1, "native export") by
cross-checking two independent, real-evidence-backed signals -- never an
in-container magic byte (see `app.adapters.hikvision.models`'s Phase 26
module-level comment for why no such signature is used):

  1. The export filename convention observed on all three real evidence
     files (`~/Documents/24fps-evidence/Hikvision/`):
     `<channel>_<YYYYMMDDHHMMSS>.mp4`, e.g. `A01_20260829100000.mp4`.
  2. A same-stem `.txt`/`.docx` device export-log sidecar placed alongside
     the clip by the DVR's own export feature, containing a "Copyright
     Hikvision Digital Technology Co., Ltd." banner and a line of the form
     `User: admin Date:DD/MM/YYYY Time: HH:MM:SS made video export from
     device <serial>` -- the DVR's own generated export receipt, read
     verbatim, never inferred (real evidence set: all three `.mp4` files
     have a matching same-stem `.txt` sidecar; `A02_20260831080000` also
     has a same-stem `.docx` carrying identical export-log text).

Both signals corroborating -> `HikvisionClipIdentificationStatus.
CONFIRMED_BY_EXPORT_LOG` (task Phase 26 scope, section 7: distinguish
"evidence actually associated with a confirmed Hikvision device" from "a
generic media file that merely looks compatible"). Filename alone, with no
sidecar found/readable, or a sidecar that does not carry the Hikvision
banner -> `FILENAME_PATTERN_ONLY`, never treated as a positive
identification. Neither signal -> `UNSUPPORTED`.

Once identified, technical metadata (codec/container/width/height/fps/
duration/audio) is read from a real, read-only `ffprobe` pass over the
source evidence file itself via `app.media.media_probe.probe_media` --
unlike CP Plus's proprietary container, an exported Hikvision clip is
already a standard container `ffprobe` reads directly, so no vendor-
specific elementary-stream reconstruction happens in this module. The
device's configured recording frame rate (15 fps, per the validated
DS-7A04HQHI-K1 fact sheet) is never substituted for whatever `ffprobe`
actually measures on a given file (task Phase 26 scope, section 19).

Distinct from `app.adapters.hikvision.detector.detect_hikvision_structure`
(Phase 19, raw DVR filesystem "Master Sector" detection): this module
parses the *exported clip*, not the DVR's internal proprietary filesystem.
A raw HDD/disk image would not match this parser at all, and an exported
clip does not exercise the Phase 19 filesystem detector.

Mirrors `app.adapters.cp_plus.parser.CPPlusParser`'s shape/contract as
closely as this genuinely different evidence class allows.
"""

from __future__ import annotations

import re
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree.ElementTree import Element  # noqa: S405 -- typing only, never used to parse untrusted XML

from defusedxml import ElementTree as defused_et

from app.acquisition.storage_reader import EvidenceStorageReader
from app.adapters.hikvision.models import (
    HikvisionClipFilenameInfo,
    HikvisionClipIdentificationResult,
    HikvisionClipIdentificationStatus,
    HikvisionClipTimestampSource,
    HikvisionEnumerationResult,
    HikvisionExportLogSidecar,
    HikvisionRecordingRecord,
    lookup_known_hikvision_device,
)
from app.media.media_probe import probe_media

#: Version of this parser implementation (Master Specification Section 59,
#: "store parser version"). Validated against exactly one device/firmware
#: (DS-7A04HQHI-K1, V4.30.220 Build 220216) and three real export files --
#: never treated as universal Hikvision support (Section 17).
PARSER_VERSION = "0.2.0"

# Matches the naming convention observed on all three real evidence files:
# an uppercase-letter-prefixed channel label (e.g. "A01", "A1", "A02"),
# an underscore, then a 14-digit YYYYMMDDHHMMSS export-start timestamp.
# The trailing digits after the letter(s) are the channel number; observed
# values are 2-digit ("A01"/"A02") but the pattern accepts 1+ digits since
# no second export has been observed to confirm digit-width is fixed.
_FILENAME_RE = re.compile(r"^(?P<channel>[A-Za-z]+\d+)_(?P<start>\d{14})$")

_COPYRIGHT_RE = re.compile(r"Copyright\s+Hikvision\s+Digital\s+Technology", re.IGNORECASE)

# Matches the real sidecar log line observed on all five real `.txt`/`.docx`
# sidecar files, e.g.:
#   "User: admin Date:30/08/2026 Time: 19:04:47 made video export from
#    device 0420220517CCWRJ98043179WCVU"
_EXPORT_LINE_RE = re.compile(
    r"User:\s*(?P<user>\S+)\s+Date:\s*(?P<date>\d{2}/\d{2}/\d{4})\s+"
    r"Time:\s*(?P<time>\d{2}:\d{2}:\d{2})\s+made\s+video\s+export\s+from\s+device\s+(?P<serial>\S+)"
)

# Matches the real sidecar's own "N logs output" line (observed: "0 logs
# output" / "2 logs output").
_LOG_COUNT_RE = re.compile(r"(?P<count>\d+)\s+logs?\s+output", re.IGNORECASE)

_DOCX_TEXT_TAG = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"

_PROBE_FIELD_DEFAULTS: dict[str, object] = {
    "duration_ms": None,
    "codec": None,
    "container": None,
    "width": None,
    "height": None,
    "fps": None,
    "has_audio": None,
    "audio_codec": None,
}


def parse_hikvision_export_filename(name: str) -> HikvisionClipFilenameInfo | None:
    """Best-effort parse of a Hikvision export filename's channel/start.

    Args:
        name: A filename (not a full path).

    Returns:
        A `HikvisionClipFilenameInfo`, or `None` if `name` does not match
        the expected `<channel>_<YYYYMMDDHHMMSS>.mp4` convention at all
        (never a partially-guessed result).
    """
    path = Path(name)
    if path.suffix.lower() != ".mp4":
        return None
    match = _FILENAME_RE.match(path.stem)
    if match is None:
        return None
    try:
        # Deliberately naive: the filename encodes no timezone. The
        # device's own configured timezone (GMT+05:30, confirmed from its
        # system-settings screen) is known external, examiner-supplied
        # context, not something this filename itself asserts -- attaching
        # a timezone here would fabricate precision the filename does not
        # contain. An examiner supplies it explicitly via
        # `app.core.timestamp_manager.TimestampManager.normalize_recording`.
        start = datetime.strptime(match.group("start"), "%Y%m%d%H%M%S")  # noqa: DTZ007
    except ValueError:
        return None
    channel_label = match.group("channel")
    digits = re.sub(r"^[A-Za-z]+", "", channel_label)
    channel_number = int(digits) if digits.isdigit() else None
    return HikvisionClipFilenameInfo(
        channel_label=channel_label, channel_number=channel_number, start_original=start
    )


def _read_docx_text(path: Path) -> str | None:
    """Extract plain text from a `.docx`'s `word/document.xml` part.

    Uses `defusedxml` (never the stdlib `xml.etree` directly) since this
    parses a file supplied as evidence, not code this project authored --
    Master Specification's forensic-safety posture treats every evidence
    file as untrusted input.

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
    except Exception:  # noqa: BLE001 -- any malformed-XML failure mode is equally "unreadable" here
        return None
    return "".join(node.text or "" for node in root.iter(_DOCX_TEXT_TAG))


def _read_sidecar_text(path: Path) -> str | None:
    """Read a `.txt`/`.docx` sidecar's text content. Never raises."""
    if path.suffix.lower() == ".docx":
        return _read_docx_text(path)
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _parse_sidecar_text(source_path: Path, text: str) -> HikvisionExportLogSidecar:
    """Extract the fields this project can actually read from a Hikvision
    export-log sidecar's own text. Every field stays `None` when its
    expected line is not found -- never guessed (module docstring)."""
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


def _find_sidecar(evidence_path: Path) -> HikvisionExportLogSidecar | None:
    """Look for a same-stem `.txt`/`.docx` sidecar next to `evidence_path`.

    A single, non-recursive listing of the evidence file's own parent
    directory (never an unbounded/recursive search) -- the sidecar
    convention observed in real evidence is a same-stem file placed
    alongside the exported clip by the DVR's own export feature at export
    time. `.txt` is preferred when both exist (observed identical content
    in the one real case where both are present).

    Returns:
        The parsed sidecar, or `None` if neither a `.txt` nor a `.docx`
        same-stem sidecar exists or could be read.
    """
    stem = evidence_path.stem
    parent = evidence_path.parent
    for suffix in (".txt", ".docx"):
        candidate = parent / f"{stem}{suffix}"
        if candidate.is_file():
            text = _read_sidecar_text(candidate)
            if text is not None:
                return _parse_sidecar_text(candidate, text)
    return None


def identify_exported_clip(reader: EvidenceStorageReader) -> HikvisionClipIdentificationResult:
    """Identify whether `reader`'s evidence is a genuine Hikvision-exported clip.

    Args:
        reader: An already-open `EvidenceStorageReader`. Not closed here
            -- the caller owns its lifecycle. Must expose a real
            filesystem `source_path` via `reader.metadata()` -- both
            signals this function checks are filesystem-based (a
            same-stem sidecar lookup is not expressible over a bounded
            byte-range read).

    Returns:
        A `HikvisionClipIdentificationResult`. Always structured, never
        raises.
    """
    source_path_str = reader.metadata().get("source_path")
    if not isinstance(source_path_str, str) or not source_path_str:
        return HikvisionClipIdentificationResult(
            status=HikvisionClipIdentificationStatus.UNSUPPORTED,
            filename_info=None,
            sidecar=None,
            reason=(
                "this evidence reader exposes no source_path; Hikvision export identification "
                "requires a real filesystem path (both the filename convention and the sidecar "
                "export-log lookup are filesystem-based)"
            ),
        )
    evidence_path = Path(source_path_str)
    filename_info = parse_hikvision_export_filename(evidence_path.name)
    if filename_info is None:
        return HikvisionClipIdentificationResult(
            status=HikvisionClipIdentificationStatus.UNSUPPORTED,
            filename_info=None,
            sidecar=None,
            reason=(
                f"filename {evidence_path.name!r} does not match the Hikvision export naming "
                "convention '<channel>_<YYYYMMDDHHMMSS>.mp4'"
            ),
        )

    sidecar = _find_sidecar(evidence_path)
    if sidecar is None:
        return HikvisionClipIdentificationResult(
            status=HikvisionClipIdentificationStatus.FILENAME_PATTERN_ONLY,
            filename_info=filename_info,
            sidecar=None,
            reason=(
                "filename matches the Hikvision export naming convention, but no same-stem "
                "'.txt'/'.docx' export-log sidecar could be found or read next to this evidence "
                "file -- this is NOT treated as a confirmed Hikvision identification"
            ),
        )
    if not sidecar.is_hikvision_copyright_banner_present:
        return HikvisionClipIdentificationResult(
            status=HikvisionClipIdentificationStatus.FILENAME_PATTERN_ONLY,
            filename_info=filename_info,
            sidecar=sidecar,
            reason=(
                "filename matches the Hikvision export naming convention and a same-stem "
                "sidecar was found, but its content does not carry the expected Hikvision "
                "copyright banner -- this is NOT treated as a confirmed Hikvision identification"
            ),
        )

    known_device = (
        lookup_known_hikvision_device(sidecar.device_serial)
        if sidecar.device_serial is not None
        else None
    )
    return HikvisionClipIdentificationResult(
        status=HikvisionClipIdentificationStatus.CONFIRMED_BY_EXPORT_LOG,
        filename_info=filename_info,
        sidecar=sidecar,
        reason=(
            f"filename matches the Hikvision export naming convention and sidecar "
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
        ),
        known_device=known_device,
    )


def _probe_recording(evidence_path: Path) -> tuple[dict[str, object], list[str]]:
    """Read-only `ffprobe` pass over the source evidence file itself.

    Returns:
        `(fields, warnings)`. `fields` always carries every key in
        `_PROBE_FIELD_DEFAULTS`, `None` for whatever `ffprobe` could not
        determine -- never guessed.
    """
    probe = probe_media(evidence_path)
    if not probe.available:
        return dict(_PROBE_FIELD_DEFAULTS), list(
            probe.warnings or ["ffprobe could not read this evidence file"]
        )

    has_audio: bool | None = None
    audio_codec: str | None = None
    if isinstance(probe.raw, dict):
        streams = probe.raw.get("streams")
        if isinstance(streams, list):
            audio_streams = [
                stream
                for stream in streams
                if isinstance(stream, dict) and stream.get("codec_type") == "audio"
            ]
            has_audio = len(audio_streams) > 0
            if audio_streams:
                codec_name = audio_streams[0].get("codec_name")
                audio_codec = codec_name if isinstance(codec_name, str) else None

    duration_ms = (
        int(round(probe.duration_seconds * 1000)) if probe.duration_seconds is not None else None
    )
    fields: dict[str, object] = {
        "duration_ms": duration_ms,
        "codec": probe.codec,
        "container": probe.format_name,
        "width": probe.width,
        "height": probe.height,
        "fps": probe.fps,
        "has_audio": has_audio,
        "audio_codec": audio_codec,
    }
    return fields, list(probe.warnings)


class HikvisionParser:
    """Parses Hikvision exported-media evidence through the common
    `EvidenceStorageReader` abstraction.

    VALIDATED SCOPE: the export-log-sidecar-confirmed `.mp4` pathway (see
    this module's own docstring). `identify()`/`enumerate_recordings()`
    perform real, evidence-backed identification and `ffprobe`-backed
    technical parsing; anything unconfirmed still honestly reports
    `FILENAME_PATTERN_ONLY`/`UNSUPPORTED` rather than guessing. Does not
    read/decode video frames itself -- actual media decoding is FFmpeg's
    job (`app.media.decoder.remux_container_to_mp4`), consistent with
    Master Specification Section 19.
    """

    def __init__(
        self, reader: EvidenceStorageReader, *, source_evidence_id: str | None = None
    ) -> None:
        """
        Args:
            reader: An already-open `EvidenceStorageReader` for the evidence
                to parse. Not closed by this class -- the caller owns its
                lifecycle.
            source_evidence_id: The evidence item's ID, attached to any
                recording records produced.
        """
        self._reader = reader
        self._source_evidence_id = source_evidence_id

    def identify(self) -> HikvisionClipIdentificationResult:
        """Answer "is this evidence a genuine Hikvision-exported clip?"."""
        return identify_exported_clip(self._reader)

    def enumerate_recordings(self) -> HikvisionEnumerationResult:
        """Enumerate recordings discoverable from this Hikvision export file.

        Returns:
            A `HikvisionEnumerationResult`. When identification does not
            find even a filename match, this returns an empty recording
            list carrying that status/reason forward. Otherwise it
            returns exactly one `HikvisionRecordingRecord` for this file
            (one exported clip is one recording -- no multi-recording
            index exists in an exported file).
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

        if evidence_path is not None:
            probed_fields, probe_warnings = _probe_recording(evidence_path)
        else:
            probed_fields, probe_warnings = (
                dict(_PROBE_FIELD_DEFAULTS),
                ["no source_path available to probe media"],
            )

        filename_info = identification.filename_info
        start_original = filename_info.start_original if filename_info else None
        channel_label = filename_info.channel_label if filename_info else None
        channel_number = filename_info.channel_number if filename_info else None

        duration_ms = probed_fields["duration_ms"]
        end_original: datetime | None = None
        if start_original is not None and isinstance(duration_ms, int):
            end_original = start_original + timedelta(milliseconds=duration_ms)

        warnings = [*identification.warnings, *probe_warnings]
        if end_original is None and start_original is not None:
            warnings.append(
                "end_original could not be computed: measured stream duration is unavailable"
            )

        confidence = (
            1.0
            if identification.status == HikvisionClipIdentificationStatus.CONFIRMED_BY_EXPORT_LOG
            else 0.4
        )
        recording_id = (
            evidence_path.stem
            if evidence_path is not None
            else f"HIKVISION-EXPORT-{self._source_evidence_id or 'UNKNOWN'}"
        )

        record = HikvisionRecordingRecord(
            recording_id=recording_id,
            camera_id=channel_label,
            channel=channel_number,
            start_original=start_original,
            end_original=end_original,
            duration_ms=duration_ms if isinstance(duration_ms, int) else None,
            codec=probed_fields["codec"] if isinstance(probed_fields["codec"], str) else None,
            container=(
                probed_fields["container"] if isinstance(probed_fields["container"], str) else None
            ),
            width=probed_fields["width"] if isinstance(probed_fields["width"], int) else None,
            height=probed_fields["height"] if isinstance(probed_fields["height"], int) else None,
            fps=probed_fields["fps"] if isinstance(probed_fields["fps"], (int, float)) else None,
            has_audio=(
                probed_fields["has_audio"] if isinstance(probed_fields["has_audio"], bool) else None
            ),
            audio_codec=(
                probed_fields["audio_codec"]
                if isinstance(probed_fields["audio_codec"], str)
                else None
            ),
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
        )

        return HikvisionEnumerationResult(
            status=identification.status,
            recordings=[record],
            warnings=warnings,
            parser_version=PARSER_VERSION,
            reason=identification.reason,
        )

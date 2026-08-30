
SIH 26150 — MULTI-VENDOR DVR/NVR FORENSIC ANALYSIS PLATFORM
BACKEND MASTER SPECIFICATION
====================================================================

Document purpose
----------------
This document is the backend engineering master specification for SIH Problem
Statement 26150:

"Development of a Multi-Vendor DVR/NVR Forensic Analysis Tool for Standardized
Acquisition, Recovery, and Analysis of Surveillance Evidence."

Organization:
National Technical Research Organisation (NTRO)

Category:
Software

Theme:
Blockchain & Cybersecurity

This document is intended to be used as the backend development reference for
the project. It describes what the backend must do, how its components fit
together, the proposed technology stack, the evidence model, processing
pipeline, API responsibilities, vendor-adapter architecture, recovery,
timeline, AI, integrity, provenance, reporting, testing, and deployment
strategy.

IMPORTANT PROJECT RULE
-----------------------
The project target is the COMPLETE SIH/NTRO scope. Features are not removed
just because some are harder than others.

The system must ultimately cover:
1. Evidence acquisition
2. Device/model/firmware identification
3. Proprietary filesystem and format parsing
4. Video and metadata extraction
5. Deleted/damaged/fragmented recording recovery
6. Timestamp normalization
7. Cross-camera event correlation
8. Hashing and integrity validation
9. Chain of custody and provenance
10. Standardized forensic reporting
11. AI-based face, object, and motion analysis
12. Multi-vendor/OEM support
13. Blockchain-backed evidence/audit anchoring
14. SOPs, validation reports, user documentation, and final documentation

The implementation order may be staged, but the final target is the complete
system.

====================================================================
1. PROJECT BACKEND GOAL
====================================================================

The backend is the forensic processing engine of the product.

The frontend/desktop UI will be the investigator's control surface, but the
backend is responsible for the actual processing of evidence.

The backend must be able to:

- create and manage forensic cases
- register evidence
- maintain device and storage information
- perform or orchestrate evidence acquisition
- create/read forensic images
- calculate MD5 and SHA-256
- identify vendors/models/firmware/storage structures
- select the appropriate vendor adapter
- parse proprietary DVR/NVR storage structures
- extract recordings and metadata
- recover deleted/damaged/fragmented recordings
- reconstruct recording fragments
- decode recovered streams through FFmpeg
- run OpenCV-based video processing
- run object detection, tracking, face detection, and motion detection
- normalize timestamps without destroying originals
- construct a canonical timeline
- correlate events across cameras
- validate recovery using controlled ground truth
- record provenance and processing history
- maintain chain of custody
- maintain a hash-linked audit log
- anchor important/periodic evidence fingerprints to a blockchain
- produce structured normalized evidence
- produce JSON/CSV/manifest outputs
- generate standardized forensic PDF reports
- expose all important operations to the frontend through a controlled API
- operate on Linux during development and support Windows as a primary target

The backend must be designed as a forensic system, not as a generic CCTV
analytics application.

====================================================================
2. CORE MENTAL MODEL
====================================================================

The backend should treat the investigation as an evidence pipeline.

Primary pipeline:

DVR/NVR
  ->
Acquisition
  ->
Evidence registration
  ->
Integrity/hash
  ->
Device identification
  ->
Filesystem/format identification
  ->
Vendor adapter
  ->
Parsing
  ->
Recording/metadata extraction
  ->
Recovery/reconstruction
  ->
Video decoding
  ->
Timestamp normalization
  ->
Cross-camera correlation
  ->
AI analysis
  ->
Validation
  ->
Provenance/chain of custody
  ->
Hash-linked audit log
  ->
Blockchain anchor
  ->
Standardized report

The backend must preserve the distinction between:
- source evidence
- acquired image/copy
- extracted evidence
- recovered evidence
- analytical results
- forensic findings
- reporting artifacts

Do not collapse all of these into one generic "file" object.

====================================================================
3. BACKEND TECHNOLOGY STACK
====================================================================

PRIMARY LANGUAGE
----------------
Python

Why:
- forensic orchestration is Python-friendly
- binary analysis can start in Python
- AI ecosystem is Python-friendly
- FFmpeg integration is straightforward
- OpenCV is Python-friendly
- database libraries are mature
- FastAPI is Python
- rapid experimentation is important when reverse-engineering proprietary
  storage structures

C/C++ may be introduced later for genuinely performance-critical or
low-level functionality. Do not implement the entire parser stack in C++ from
day one.

API FRAMEWORK
------------
FastAPI

Responsibilities:
- REST API
- request validation
- job control
- case/evidence operations
- analysis orchestration
- frontend/backend communication
- health/status endpoints
- API documentation
- background processing integration

DATABASE
--------
Initial/local forensic workstation:
SQLite

Scaled multi-user platform:
PostgreSQL

Reason:
A local forensic workstation does not need a database server just to store
case metadata. SQLite is simpler for the initial system.

Important:
The evidence media itself must NOT be treated as a normal database blob by
default. Large evidence files/images should be referenced by path/URI/asset
metadata, not indiscriminately loaded into database rows.

FORENSIC IMAGE SUPPORT
----------------------
RAW/DD:
- primary candidate for the internal DVR-analysis path
- direct byte-for-byte storage representation

E01:
- supported import/interchange format
- use libewf for EWF/E01 handling
- do NOT implement E01 ourselves

HASHING
-------
SHA-256:
- primary modern integrity hash

MD5:
- additionally calculated because NTRO explicitly requests it
- do not describe MD5 as the modern secure hash

VIDEO
-----
FFmpeg:
- demuxing
- decoding
- conversion
- media inspection

OpenCV:
- frame extraction/processing
- image/video computer vision
- classical motion analysis
- supporting AI preprocessing and postprocessing

AI
--
YOLO:
- initial object detection

Tracking:
- ByteTrack and/or BoT-SORT
- benchmark using the actual CCTV datasets before permanently selecting one

Face:
- face detection is the core requirement
- face recognition is optional/future capability and must not be assumed by
  default

Motion:
- classical computer-vision motion detection initially
- frame difference/background subtraction/optical flow can be evaluated

REPORTING
---------
Structured JSON:
- machine-readable normalized result

PDF:
- human-readable standardized forensic report

Optional:
- CSV evidence table
- HTML report
- evidence manifest
- hash manifest
- chain-of-custody export

BLOCKCHAIN / AUDIT
------------------
Primary local audit:
- hash-linked audit log

Blockchain:
- evidence/provenance anchoring layer
- store cryptographic fingerprints/anchors
- DO NOT store the actual CCTV evidence on-chain

DESKTOP INTEGRATION
-------------------
Frontend will be React + TypeScript inside a desktop shell such as Tauri.
The backend remains a Python/FastAPI service.

During development:
- Python backend runs locally
- React frontend runs locally
- Tauri desktop shell connects to the backend

Final deployment:
- package the application so the investigator launches one desktop product
- Windows is a primary deployment target
- Linux development remains supported
- the core forensic logic should remain platform-independent
- low-level disk/device access must be abstracted behind platform-specific
  interfaces

====================================================================
4. BACKEND ARCHITECTURE
====================================================================

Recommended high-level structure:

backend/
    app/
        main.py
        config.py
        dependencies.py

        api/
            routes/
                cases.py
                evidence.py
                acquisition.py
                devices.py
                recordings.py
                recovery.py
                timeline.py
                correlation.py
                ai.py
                validation.py
                integrity.py
                audit.py
                blockchain.py
                reports.py
                jobs.py
                system.py

        core/
            case_manager.py
            evidence_manager.py
            processing_orchestrator.py
            job_manager.py
            provenance_manager.py
            capability_registry.py

        models/
            case.py
            evidence.py
            device.py
            storage.py
            recording.py
            metadata.py
            timeline.py
            recovery.py
            ai_result.py
            validation.py
            audit.py
            report.py

        schemas/
            case.py
            evidence.py
            device.py
            acquisition.py
            recording.py
            recovery.py
            timeline.py
            ai.py
            validation.py
            report.py

        acquisition/
            interface.py
            native_export.py
            physical_storage.py
            raw_imager.py
            e01_handler.py
            windows_storage.py
            linux_storage.py

        hashing/
            md5.py
            sha256.py
            verifier.py

        detection/
            device_identifier.py
            filesystem_detector.py
            signature_engine.py

        adapters/
            base.py
            registry.py
            cp_plus/
            hikvision/
            dahua/
            honeywell/
            tp_link/
            godrej/
            uniview/
            matrix/

        parsing/
            binary_reader.py
            sector_reader.py
            filesystem.py
            metadata.py
            index.py
            recording_index.py

        recovery/
            recovery_engine.py
            filesystem_recovery.py
            vendor_recovery.py
            carving.py
            fragment_reconstruction.py
            continuity.py
            confidence.py

        media/
            ffmpeg.py
            demux.py
            decoder.py
            media_probe.py

        vision/
            frame_reader.py
            motion.py
            objects.py
            faces.py
            tracking.py

        timeline/
            timestamp_parser.py
            timezone.py
            offset.py
            normalization.py
            canonical.py
            correlation.py

        validation/
            ground_truth.py
            recovery_metrics.py
            timestamp_metrics.py
            frame_metrics.py
            benchmark.py

        integrity/
            manifest.py
            hash_verification.py
            evidence_fingerprint.py

        audit/
            events.py
            hash_chain.py
            chain_of_custody.py

        blockchain/
            anchor.py
            provider.py
            verification.py

        reporting/
            evidence_report.py
            json_report.py
            pdf_report.py
            templates/

        storage/
            evidence_store.py
            artifact_store.py
            job_store.py
            db.py

        logging/
            forensic_logger.py
            processing_log.py

        utils/
            paths.py
            time.py
            errors.py
            subprocess.py

    tests/
        unit/
        integration/
        fixtures/
        ground_truth/

    scripts/
    migrations/
    requirements.txt
    pyproject.toml
    README.md

This structure is a proposed implementation layout. The exact folder names
can change, but the separation of responsibilities should remain.

====================================================================
5. MOST IMPORTANT ARCHITECTURAL RULE
====================================================================

DO NOT BUILD ONE GIANT PARSER.

Use a vendor-adapter/plugin architecture.

Conceptually:

                         COMMON FORENSIC CORE
                                  |
              +-------------------+-------------------+
              |                   |                   |
              v                   v                   v
          CP Plus            Hikvision             Dahua
           Adapter             Adapter              Adapter
              |                   |                   |
              +-------------------+-------------------+
                                  |
                                  v
                         NORMALIZED EVIDENCE
                                  |
          +-------------------+---+--------------------+
          |                   |                        |
          v                   v                        v
       Recovery            Timeline                    AI
          |                   |                        |
          +-------------------+------------------------+
                                  |
                                  v
                             Reporting

Each vendor may have different:
- filesystem
- partitions
- metadata
- storage layout
- recording structure
- firmware behavior
- encoding
- indexing
- deletion behavior
- camera/channel mapping

The vendor adapter knows the vendor-specific details.

The common engine works on normalized evidence.

====================================================================
6. NORMALIZED EVIDENCE MODEL
====================================================================

Every adapter must eventually translate vendor-specific information into the
same conceptual evidence representation.

Core object:

Evidence
  - case_id
  - evidence_id
  - source_type
  - source_path/reference
  - acquisition_method
  - device
  - storage
  - recordings
  - metadata
  - timeline
  - hashes
  - provenance
  - recovery information
  - confidence
  - processing history

Device:
  - vendor
  - model
  - firmware
  - serial_number
  - device_type
  - channel_count
  - camera_count
  - network_information where relevant

Storage:
  - manufacturer
  - model
  - serial
  - capacity
  - sector_size
  - interface
  - image_format
  - image_path
  - acquisition status

Recording:
  - recording_id
  - camera_id
  - channel
  - original_start
  - original_end
  - normalized_start
  - normalized_end
  - duration
  - codec
  - container/stream information
  - resolution
  - frame_rate
  - source_location
  - recovery_status
  - recovery_method
  - recovery_confidence
  - hash
  - provenance_id

Metadata:
  - camera_id
  - channel
  - timestamp
  - frame_rate
  - resolution
  - codec
  - duration
  - file/stream size
  - recording mode
  - motion event
  - audio presence
  - vendor-specific metadata where available

Timeline:
  - original timestamp
  - normalized timestamp
  - timezone
  - clock offset
  - offset confidence
  - normalization method
  - source evidence

Hashes:
  - md5
  - sha256
  - hash status
  - algorithm
  - calculation time
  - artifact reference

Provenance:
  - acquisition information
  - examiner
  - software version
  - parser version
  - processing steps
  - parent artifact
  - child artifact

Confidence:
  - confidence value
  - level
  - basis/reason
  - contributing evidence

CRITICAL RULE:
If a value cannot be reliably determined, record "Not determined" or another
explicit unavailable state. Do not guess.

====================================================================
7. FORENSIC CASE MODEL
====================================================================

A Case is the top-level investigation container.

Suggested fields:

case_id
case_number
case_name
description
examiner
organization
created_at
updated_at
reference_time
status
software_version
schema_version

Possible status values:
- draft
- active
- processing
- review
- completed
- archived

A case can contain multiple evidence items.

Example:

Case NTRO-2026-001
  |
  +-- Evidence E001 CP Plus HDD
  +-- Evidence E002 Hikvision export
  +-- Evidence E003 Dahua E01
  |
  +-- Timeline
  +-- AI findings
  +-- Reports
  +-- Audit history

====================================================================
8. EVIDENCE MODEL
====================================================================

Evidence is the object being examined.

Required concepts:

Evidence ID:
Unique identifier.

Evidence type:
Examples:
- native_export
- direct_storage
- forensic_image
- raw_dd
- e01
- video_file
- directory_export
- other documented source type

Source:
Where evidence originated.

Original source:
The original DVR/NVR/storage information.

Acquisition:
How it was acquired.

Integrity:
Hashes and verification.

Lifecycle:
Received -> registered -> acquired -> analyzed -> processed -> reported.

Evidence records must preserve the distinction between original source and
derived artifacts.

====================================================================
9. ACQUISITION BACKEND
====================================================================

Acquisition is a separate backend subsystem.

The acquisition architecture is multi-path.

Path 1: Native export
- use when the DVR is functioning and the required evidence is accessible
- capture the exported data plus available vendor metadata/player/logs
- register the export as evidence

Path 2: Direct storage acquisition
- used when storage-level evidence is necessary
- requires read-only/protected acquisition workflow
- write-blocking is part of the real-world forensic workflow
- create RAW/DD image or otherwise documented image

Path 3: Existing forensic image
- import RAW/DD
- import E01 through libewf

Path 4: Controlled non-standard acquisition
- for failed/unknown/unsupported devices
- preserve original source
- identify hardware/storage
- develop acquisition approach
- test on duplicate/sample device
- document effects
- validate
- only then use the method on the case evidence

The backend must never silently modify original evidence.

====================================================================
10. ACQUISITION JOB
====================================================================

Acquisition should run as a managed job.

Job fields:

job_id
case_id
evidence_id
job_type
source
destination
start_time
end_time
progress
status
bytes_read
bytes_total
read_errors
warnings
hash_progress
sha256
md5
operator
platform
software_version

Possible statuses:

queued
running
paused
completed
completed_with_warnings
failed
cancelled

For large acquisitions, the API must not block for hours waiting on one HTTP
request.

Use asynchronous/background job execution.

Frontend pattern:

POST /api/v1/acquisition/jobs
        ->
job_id

GET /api/v1/jobs/{job_id}
        ->
progress/status

GET /api/v1/jobs/{job_id}/events
        ->
processing events/log stream

====================================================================
11. PLATFORM STORAGE ACCESS
====================================================================

Because the project is developed on Arch Linux and must also support Windows,
low-level storage access must be abstracted.

Do not spread OS-specific code throughout the application.

Use:

StorageAccess interface

Linux implementation:
- device paths such as /dev/*
- Linux-specific safe read mechanisms

Windows implementation:
- Windows physical-drive APIs
- Windows-specific device paths
- required permission handling

The common acquisition engine calls the interface.

Concept:

StorageAccess
   |
   +-- LinuxStorageAccess
   |
   +-- WindowsStorageAccess

The forensic core does not need to know the low-level OS details.

====================================================================
12. FORENSIC IMAGE HANDLING
====================================================================

RAW/DD:
- treat as exact source representation
- support sector-oriented reading
- allow random access to sectors
- calculate hashes
- preserve acquisition metadata separately

E01:
- use libewf
- import/read the image
- expose a common storage reader interface to the parsing engine

Common reader abstraction:

EvidenceStorageReader
  - read(offset, length)
  - read_sector(sector_number)
  - size()
  - metadata()
  - hash()
  - close()

This means the parser does not care whether it is reading:
- physical HDD
- RAW/DD
- E01

It sees a common read-only abstraction.

====================================================================
13. DEVICE IDENTIFICATION
====================================================================

The detector should identify:

- vendor
- model
- firmware where obtainable
- device type
- serial
- channel count
- camera count
- storage characteristics
- filesystem/format hints

Detection must use signatures and structural analysis.

Do not rely only on file extensions.

Possible detection signals:
- known byte signatures
- partition layout
- filesystem/superblock signatures
- known strings
- metadata structures
- vendor-specific headers
- recording index patterns
- storage layout
- firmware-specific information

Detection output:

DeviceIdentificationResult
  vendor
  model
  firmware
  confidence
  evidence
  detected_storage_format
  adapter_candidate

If identification is uncertain:
- preserve uncertainty
- expose multiple candidate adapters
- do not guess silently

====================================================================
14. FILESYSTEM DETECTION
====================================================================

Filesystem/format detection should be separate from video decoding.

Why:
A video codec tells us how frames are encoded.
It does not tell us where the recordings are stored on the DVR HDD.

Detection process:

RAW storage
  ->
partition/layout analysis
  ->
signature scan
  ->
filesystem/format candidate
  ->
vendor/model/firmware correlation
  ->
adapter selection
  ->
parser

If unsupported:
status = unknown_or_unsupported

The system should flag unsupported formats instead of inventing a structure.

====================================================================
15. BINARY ANALYSIS
====================================================================

Binary analysis means inspecting raw machine-readable bytes.

Tools/approaches:
- Python
- structured binary readers
- hex editors during research
- Kaitai Struct where useful
- custom parsers
- C/C++ only where necessary

Research loop:

Raw bytes
   ->
identify patterns
   ->
hypothesis
   ->
implement parser
   ->
test
   ->
compare against known recording
   ->
validate
   ->
document structure

Parser research must be evidence-driven.

Do not assume a byte pattern is a timestamp, sector pointer, or camera ID merely
because it looks plausible.

====================================================================
16. VENDOR ADAPTER INTERFACE
====================================================================

Every vendor adapter should implement a common interface.

Conceptual methods:

identify()
detect_capabilities()
inspect_storage()
parse_filesystem()
parse_metadata()
enumerate_recordings()
extract_recording()
find_deleted_recordings()
recover_recording()
reconstruct_fragments()
decode_metadata()
validate_recording()
normalize_evidence()

Possible adapter result:

AdapterResult
  vendor
  model
  firmware
  detected_format
  capability_set
  recordings
  metadata
  recovery_candidates
  warnings
  parser_version
  confidence

The adapter should not own the entire application.

Its job is:
Vendor-specific storage understanding.

The common engine should own:
- evidence objects
- timeline
- validation
- provenance
- reporting
- common recovery logic
- AI
- correlation

====================================================================
17. TARGET OEM ADAPTERS
====================================================================

NTRO explicitly names:

1. Dahua Technology
2. CP Plus
3. Honeywell Security
4. HIKVISION / Hikvision
5. TP-Link
6. Godrej
7. Uniview
8. Matrix

The problem statement expects support for at least five to six major OEMs.

Project architecture must nevertheless be designed so all named vendors can be
represented by adapters.

Important:
Vendor support is not just a brand checkbox.

Real support may depend on:
- exact model
- exact firmware
- storage architecture
- recording mode
- filesystem generation
- format variant

Therefore capability reporting should be model/firmware aware.

Example:

CP Plus
  Model A
    Firmware 1 -> supported
    Firmware 2 -> unknown

Never report "CP Plus fully supported" if only one model is tested.

====================================================================
18. RECORDING INDEX PARSING
====================================================================

Many DVR systems maintain an index of recordings.

Index parsing should discover:
- camera/channel
- start time
- end time
- storage location
- block/segment references
- recording mode
- event type where available
- flags indicating deletion/recovery state

The index may point to actual data blocks.

Backend flow:

index
  ->
recording reference
  ->
storage blocks
  ->
recording fragments
  ->
stream extraction
  ->
decoded video

====================================================================
19. VIDEO EXTRACTION
====================================================================

After vendor parsing, the backend should produce a recoverable media artifact
or stream.

Then:

vendor parser
  ->
raw stream / container
  ->
FFmpeg
  ->
decoded frames/media

FFmpeg responsibilities:
- media probe
- container/stream identification
- demuxing
- decoding
- conversion
- extraction

FFmpeg must NOT be treated as the proprietary filesystem parser.

====================================================================
20. MEDIA ARTIFACT MODEL
====================================================================

A derived media artifact should have:

artifact_id
parent_evidence_id
parent_recording_id
source_offsets
file_path
format
codec
duration
resolution
frame_rate
creation_time
generated_by
tool_version
sha256
md5
status

Every derived artifact should point back to its parent evidence.

This makes the output traceable.

====================================================================
21. RECOVERY ENGINE
====================================================================

Recovery must be layered.

Layer 1:
Filesystem/index recovery

Recover recordings whose references/index information still exists.

Layer 2:
Vendor-specific recovery

Use knowledge of vendor storage organization and deletion behavior.

Layer 3:
File/frame carving

Search raw storage for recognizable recoverable media structures.

Layer 4:
Fragment reconstruction

Determine relationships between fragments and reconstruct recordings.

Recovery must produce a status, not just success/failure.

Possible statuses:
- original
- recovered
- partial
- reconstructed
- corrupted
- unrecoverable
- candidate
- not_verified

====================================================================
22. RECOVERY CONFIDENCE
====================================================================

Each recovered recording should contain confidence.

Confidence should be based on actual evidence, not a fabricated number.

Potential factors:
- metadata/index consistency
- valid video headers
- frame continuity
- timestamp continuity
- expected segment order
- camera/channel consistency
- codec consistency
- fragment adjacency evidence
- checksum/hash where available
- known ground truth

Example:

Recovery:
RECONSTRUCTED

Confidence:
0.92

Basis:
- recording index reference exists
- 98% expected frames reconstructed
- timestamp continuity preserved
- codec consistent
- 2 fragment gaps detected

====================================================================
23. FILE CARVING
====================================================================

File carving is recovering data from raw storage without relying completely on
filesystem metadata.

It is useful when:
- files were deleted
- filesystem indexes are damaged
- metadata is missing

Problem:
Carving can find data without knowing its original logical context.

Therefore:
- carving results are candidates
- context must be reconstructed if possible
- camera/timestamp/segment association should be inferred only from evidence
- confidence should reflect uncertainty

Never present a carved candidate as an unquestionable original recording.

====================================================================
24. FRAGMENT RECONSTRUCTION
====================================================================

Fragments may be scattered across storage.

Reconstruction must determine:
- fragment belongs to recording
- fragment order
- camera/channel
- timestamp sequence
- codec/stream continuity
- gaps/corruption

Outputs:
- reconstructed recording
- reconstructed fragment map
- missing intervals
- reconstruction confidence
- warnings

Example:

REC-017
  Fragment 01
  Fragment 02
  Fragment 03
  GAP
  Fragment 05

Status:
PARTIAL

Reason:
Fragment 04 not found or unreadable.

====================================================================
25. VIDEO METADATA EXTRACTION
====================================================================

Metadata can include:
- camera ID
- channel
- timestamp
- start/end
- duration
- frame rate
- resolution
- codec
- file/stream size
- recording mode
- motion event
- audio presence
- vendor-specific fields

Important:
Only report information actually extracted.

If not available:
"Not available"

If uncertain:
"Not determined"

Do not fabricate values.

====================================================================
26. TIMESTAMP NORMALIZATION
====================================================================

The system must preserve original timestamps.

Inputs may include:
- DVR timestamp
- file metadata timestamp
- filesystem timestamp
- camera timestamp
- system time
- reference/actual time
- timezone information
- external known event time

Canonical model:

Original timestamp
   ->
timezone interpretation
   ->
clock offset estimation
   ->
normalized timestamp
   ->
confidence
   ->
canonical timeline

Example:

Original:
2026-08-25 19:10:03

Normalized:
2026-08-25 19:17:41

Offset:
+7m38s

Confidence:
High

Method:
Reference-clock comparison

Never overwrite the original timestamp.

====================================================================
27. TIMESTAMP DATA MODEL
====================================================================

TimestampRecord:

timestamp_id
source_timestamp
source_timezone
reference_timestamp
reference_timezone
offset_seconds
normalized_timestamp
normalization_method
confidence
source_evidence_id
notes

Possible normalization methods:
- explicit DVR clock comparison
- known external event
- system/reference time
- timezone conversion
- cross-camera correlation
- manual examiner adjustment (must be documented)

Manual changes must never erase original values.

====================================================================
28. CANONICAL TIMELINE
====================================================================

Canonical timeline is the common investigation timeline.

It allows:
Camera 1 event
Camera 2 event
Camera 3 event

to be compared even if their source clocks differ.

Timeline event:

event_id
case_id
camera_id
source_recording_id
event_type
original_timestamp
normalized_timestamp
confidence
source
ai_reference
recovery_status

Event types may include:
- recording_start
- recording_end
- motion
- face
- object
- recovered_segment
- camera_event
- examiner_marker
- correlated_event

====================================================================
29. CROSS-CAMERA CORRELATION
====================================================================

Correlation engine takes normalized events from multiple cameras.

Example:

18:30:02
Camera 01 -> person enters

18:30:09
Camera 02 -> person appears

18:30:17
Camera 03 -> person appears

The backend can group them as an investigation sequence.

Correlation may use:
- timestamp proximity
- object/track identity
- direction of movement
- camera topology
- manually configured camera relationships
- shared event markers

Do not overclaim identity.

Cross-camera correlation is an analytical relation, not automatically proof
that two detections are the same real-world person.

====================================================================
30. AI BACKEND
====================================================================

AI is an analytical assistive layer.

It does not replace forensic evidence or the examiner.

Required AI capabilities:
1. Object detection
2. Face detection
3. Motion detection

Additional:
4. Object tracking

The forensic core establishes:
- source
- timestamp
- camera
- evidence provenance

AI adds:
- faster search
- detections
- tracks
- motion events
- analytical metadata

====================================================================
31. OBJECT DETECTION
====================================================================

Initial technology:
YOLO

Responsibilities:
- detect objects in selected video frames
- return class
- confidence
- bounding box
- frame timestamp
- recording ID
- camera ID
- model version

AI result:

ai_result_id
case_id
recording_id
timestamp
frame_number
analysis_type
class_name
confidence
bbox
model_name
model_version
source_artifact
created_at

Never store an AI result without a source artifact/frame reference.

====================================================================
32. OBJECT TRACKING
====================================================================

Candidate trackers:
- ByteTrack
- BoT-SORT

Tracking result:

track_id
recording_id
camera_id
class
first_seen
last_seen
trajectory
frame_count
average_confidence
model_version
tracker_version

Tracking can support:
- movement analysis
- event correlation
- camera-to-camera candidate matching

Tracking does not automatically prove identity.

====================================================================
33. FACE DETECTION
====================================================================

Core requirement:
Face detection.

Result should include:
- recording ID
- timestamp/frame
- bounding box
- confidence
- model/version
- source frame/artifact

Face recognition is not part of the required core.

If face recognition is later introduced:
- it needs a separate explicit subsystem
- confidence/threshold handling must be documented
- identity matches must be treated as analytical candidates
- privacy/legal implications must be considered

====================================================================
34. MOTION DETECTION
====================================================================

Initial direction:
Classical computer vision.

Possible methods:
- frame differencing
- background subtraction
- optical flow

Motion event:

motion_event_id
recording_id
camera_id
start_time
end_time
regions
confidence/score
method
parameters
source_artifact

The exact algorithm should be benchmarked against test footage.

====================================================================
35. AI PROCESSING JOBS
====================================================================

AI analysis can be long-running.

Use jobs:

POST /api/v1/ai/jobs
GET /api/v1/jobs/{job_id}

Job metadata:
job_id
case_id
recording_ids
analysis_types
model_versions
started_at
completed_at
status
progress
results_count
errors

Forensic rule:
Every AI job must be reproducible from:
- source artifact
- model name
- model version
- parameters
- software version
- processing timestamp
- output records

====================================================================
36. VALIDATION ENGINE
====================================================================

Validation is a first-class backend component.

Purpose:
Answer:
"How do we know the recovered result is correct?"

Use controlled ground-truth datasets.

Experiment:

Known recording
  ->
delete/damage/fragment
  ->
acquire storage
  ->
recover
  ->
compare to ground truth

Metrics:
- recovery rate
- false positives
- missing intervals
- timestamp accuracy
- frame continuity
- reconstruction confidence

Additional useful metrics:
- media decodability
- metadata consistency
- segment ordering
- duration error

Do not report benchmark numbers until they are actually measured.

====================================================================
37. GROUND-TRUTH DATASET MODEL
====================================================================

Ground truth should record:
- source device
- vendor
- model
- firmware
- camera/channel
- original recording
- intentional modification performed
- deletion/damage scenario
- expected recording properties
- expected timestamps
- expected frame count
- expected fragments

Test case:

ground_truth_id
device_id
recording_id
scenario
expected_start
expected_end
expected_duration
expected_frames
expected_fragments
expected_hash
notes

Then recovery output is compared against the expected result.

====================================================================
38. INTEGRITY ENGINE
====================================================================

Hash functions:
- SHA-256
- MD5

The integrity engine must support:

calculate_hash(path)
calculate_stream_hash(reader)
verify_hash(path, expected)
compare_hashes(a,b)
generate_manifest()
verify_manifest()

Hash manifest:

artifact_id
algorithm
hash
calculated_at
software_version
source_reference
verification_status

Typical lifecycle:

Original/acquired artifact
   ->
MD5 + SHA-256
   ->
store
   ->
analysis
   ->
recalculate
   ->
compare
   ->
pass/fail/warning

====================================================================
39. PROVENANCE ENGINE
====================================================================

Provenance records where evidence came from and what happened to it.

Required fields:
- case ID
- evidence ID
- source device
- vendor
- model
- firmware
- acquisition time
- examiner
- image hash
- analysis software version
- parser version
- processing steps
- output hashes

Every derived artifact should have a parent reference.

Example:

EVD-001
  |
  +-- forensic_image.dd
       |
       +-- REC-00421
            |
            +-- recovered_video.mp4
                 |
                 +-- AI analysis result
                 |
                 +-- report reference

====================================================================
40. CHAIN OF CUSTODY
====================================================================

Chain of custody is the chronological evidence-handling record.

Event:

custody_event_id
case_id
evidence_id
event_type
actor
timestamp
location/reference
description
previous_event_hash
current_event_hash
signature/reference if applicable

Events might include:
- evidence_received
- evidence_registered
- image_created
- hash_calculated
- evidence_mounted
- parser_started
- parser_completed
- recovery_started
- recovery_completed
- AI_started
- AI_completed
- report_generated
- evidence_exported

The system should not allow silent deletion/editing of forensic history.

====================================================================
41. HASH-LINKED AUDIT LOG
====================================================================

Preferred audit design:

Evidence event
  ->
hash event contents
  ->
store previous event hash
  ->
hash chain

For record N:

current_hash =
SHA-256(
    canonicalized_event_data
    + previous_record_hash
)

The chain provides tamper-evidence.

The database remains the operational store.

The hash chain provides an integrity structure.

====================================================================
42. BLOCKCHAIN ANCHORING
====================================================================

Blockchain is an evidence/provenance anchoring layer.

The backend may periodically or for important cases compute:

anchor_hash =
SHA-256(latest_audit_chain_state)

Then record:
- chain identifier
- anchor hash
- timestamp
- blockchain/network
- transaction reference
- status

The actual CCTV footage remains off-chain.

The blockchain stores the fingerprint/anchor, not the evidence itself.

Provider abstraction:

BlockchainProvider
  - create_anchor()
  - verify_anchor()
  - get_anchor()
  - provider_status()

The project must remain usable if blockchain infrastructure is unavailable.
Local hash-chain integrity must still operate.

====================================================================
43. REPORTING ENGINE
====================================================================

Backend reporting receives:

Evidence information
Acquisition information
Device information
Filesystem findings
Recovered recordings
Metadata
Timeline
Cross-camera events
AI results
Hashes
Chain of custody
Processing logs
Validation results
Limitations

and produces:

1. standardized JSON
2. human-readable PDF

Potential optional outputs:
- HTML
- CSV
- evidence manifest
- hash manifest
- custody export

====================================================================
44. FORENSIC REPORT CONTENT
====================================================================

Recommended sections:

1. Case information
2. Purpose/scope
3. Evidence inventory
4. Device information
5. Acquisition
6. Forensic image information
7. Hashes
8. Processing history
9. Filesystem/format findings
10. Recording inventory
11. Recovered recordings
12. Metadata
13. Timestamp normalization
14. Timeline
15. Cross-camera correlation
16. AI analysis
17. Validation
18. Chain of custody
19. Limitations
20. Findings
21. Evidence disposition
22. Software versions
23. Parser versions
24. Hash manifest

Report must distinguish:
- observed evidence
- automated analysis
- examiner interpretation
- limitations

Do NOT claim that the report itself guarantees legal admissibility.

====================================================================
45. REPORT DATA REQUIREMENTS
====================================================================

Evidence inventory example:

Evidence ID
Type
Vendor
Model
Serial
Storage
Hash

Device section:
Vendor
Model
Serial number
Firmware
Storage capacity
Camera count
Channels
Network information where relevant
Detected filesystem
Detected recording format

Acquisition section:
What
How
When
By whom
Method
Completion status
Errors
Unreadable sectors
Image format

Processing history:
time
operation
tool
version
parameters
result
warnings

Recovered recording:
Recording ID
Camera
Original timestamp
Normalized timestamp
Duration
Recovery method
Recovery confidence
SHA-256

Metadata:
Camera ID
Channel
Timestamp
FPS
Resolution
Codec
Duration
File size
Recording mode
Motion event
Audio presence

Timeline:
time
camera
event
source
confidence

====================================================================
46. API DESIGN
====================================================================

The API is a proposed implementation interface, not a fixed NTRO requirement.
Exact routes can evolve.

Base path:
 /api/v1

HEALTH
------
GET /api/v1/health

SYSTEM INFO
-----------
GET /api/v1/system/info
GET /api/v1/system/capabilities

CASES
-----
POST /api/v1/cases
GET /api/v1/cases
GET /api/v1/cases/{case_id}
PATCH /api/v1/cases/{case_id}

EVIDENCE
--------
POST /api/v1/cases/{case_id}/evidence
GET /api/v1/cases/{case_id}/evidence
GET /api/v1/evidence/{evidence_id}

ACQUISITION
-----------
POST /api/v1/evidence/{evidence_id}/acquisition/jobs
GET /api/v1/acquisition/jobs/{job_id}
POST /api/v1/acquisition/jobs/{job_id}/cancel

IDENTIFICATION
--------------
POST /api/v1/evidence/{evidence_id}/identify-device
GET /api/v1/evidence/{evidence_id}/device

FILESYSTEM
----------
POST /api/v1/evidence/{evidence_id}/detect-format
POST /api/v1/evidence/{evidence_id}/parse

RECORDINGS
----------
GET /api/v1/evidence/{evidence_id}/recordings
GET /api/v1/recordings/{recording_id}
POST /api/v1/recordings/{recording_id}/extract

RECOVERY
--------
POST /api/v1/evidence/{evidence_id}/recovery/jobs
GET /api/v1/recovery/jobs/{job_id}
GET /api/v1/evidence/{evidence_id}/recovery-results

TIMELINE
--------
POST /api/v1/cases/{case_id}/timeline/build
GET /api/v1/cases/{case_id}/timeline
POST /api/v1/timestamps/normalize

CORRELATION
-----------
POST /api/v1/cases/{case_id}/correlation/run
GET /api/v1/cases/{case_id}/correlation/events

AI
--
POST /api/v1/ai/jobs
GET /api/v1/ai/jobs/{job_id}
GET /api/v1/cases/{case_id}/ai-results

VALIDATION
----------
POST /api/v1/validation/jobs
GET /api/v1/validation/jobs/{job_id}
GET /api/v1/cases/{case_id}/validation

INTEGRITY
---------
POST /api/v1/evidence/{evidence_id}/hash
POST /api/v1/evidence/{evidence_id}/verify
GET /api/v1/evidence/{evidence_id}/hashes

AUDIT/CUSTODY
-------------
GET /api/v1/cases/{case_id}/audit
GET /api/v1/evidence/{evidence_id}/custody
POST /api/v1/cases/{case_id}/audit/anchor

BLOCKCHAIN
----------
POST /api/v1/cases/{case_id}/blockchain/anchor
GET /api/v1/cases/{case_id}/blockchain/anchors
POST /api/v1/blockchain/verify

REPORTS
-------
POST /api/v1/cases/{case_id}/reports
GET /api/v1/reports/{report_id}
GET /api/v1/reports/{report_id}/download

JOBS
----
GET /api/v1/jobs/{job_id}
GET /api/v1/jobs/{job_id}/logs

The backend should expose OpenAPI documentation through FastAPI.

====================================================================
47. API SECURITY / FORENSIC SAFETY
====================================================================

Even though the application is primarily local, the backend must still follow
safe principles.

Rules:
- never accept arbitrary shell commands from frontend input
- never concatenate untrusted paths into shell commands
- validate paths
- validate file types
- isolate subprocess execution
- restrict operations to registered evidence
- require case/evidence IDs for processing operations
- prevent accidental overwrite of source evidence
- treat original evidence paths as read-only
- use explicit derived-artifact directories
- record every significant processing operation
- use deterministic serialization for hashes
- avoid silent mutation of case history

Subprocesses:
- FFmpeg
- media tools
- optional low-level utilities

All subprocess calls must use safe argument arrays rather than shell strings
where possible.

====================================================================
48. JOB SYSTEM
====================================================================

Large forensic operations are asynchronous.

Examples:
- imaging a 4 TB HDD
- filesystem scan
- recovery scan
- carving
- fragment reconstruction
- AI inference across thousands of frames
- validation benchmark
- PDF report generation

Job model:

job_id
case_id
evidence_id
job_type
status
progress
created_at
started_at
completed_at
worker
input_artifacts
output_artifacts
error
warnings

Job types:
- acquisition
- identification
- filesystem_scan
- parse
- extraction
- recovery
- reconstruction
- decode
- ai
- timeline
- correlation
- validation
- report
- hash
- blockchain_anchor

====================================================================
49. PROCESSING EVENT LOG
====================================================================

Every job should emit structured events.

Example:

2026-08-25T10:40:12
DEVICE_IDENTIFICATION_STARTED

2026-08-25T10:40:21
DEVICE_IDENTIFIED
vendor=CP Plus

2026-08-25T10:45:10
FILESYSTEM_ANALYSIS_STARTED

2026-08-25T11:12:32
RECORDING_INDEX_RECONSTRUCTED

2026-08-25T11:37:05
DELETED_CANDIDATES_FOUND

2026-08-25T12:01:17
FRAGMENT_RECONSTRUCTION_COMPLETED

2026-08-25T12:14:03
TIMESTAMP_NORMALIZATION_COMPLETED

2026-08-25T12:31:12
CROSS_CAMERA_CORRELATION_COMPLETED

Each event:
- timestamp
- job ID
- case ID
- evidence ID
- operation
- details
- software version
- component version
- previous audit hash
- current audit hash

====================================================================
50. DATABASE MODEL
====================================================================

Initial SQLite relational design.

TABLE: cases
------------
id
case_id
case_number
name
description
examiner
reference_time
status
created_at
updated_at
software_version
schema_version

TABLE: evidence
---------------
id
evidence_id
case_id
source_type
source_path
source_description
status
created_at
updated_at

TABLE: devices
--------------
id
evidence_id
vendor
model
firmware
serial_number
device_type
channel_count
camera_count
network_info
confidence
identification_method

TABLE: storage_devices
----------------------
id
evidence_id
manufacturer
model
serial_number
capacity_bytes
sector_size
interface
image_format
image_path
read_only
status

TABLE: acquisitions
-------------------
id
evidence_id
job_id
method
operator
started_at
completed_at
status
bytes_total
bytes_read
read_errors
warnings

TABLE: hashes
-------------
id
artifact_id
algorithm
hash_value
calculated_at
verification_status

TABLE: artifacts
---------------
id
evidence_id
parent_artifact_id
artifact_type
path
size_bytes
sha256
md5
created_at
created_by
tool_version
status

TABLE: recordings
-----------------
id
evidence_id
recording_id
camera_id
channel
start_original
end_original
start_normalized
end_normalized
duration_ms
codec
container
width
height
fps
source_location
recovery_status
recovery_method
confidence
artifact_id

TABLE: metadata
---------------
id
recording_id
key
value
source
confidence

If frequently queried fields become stable, promote them into typed columns
rather than putting everything into a key/value table.

TABLE: recovery_results
----------------------
id
recording_id
method
status
fragments_found
fragments_used
fragments_missing
frames_expected
frames_recovered
recovery_rate
timestamp_error
frame_continuity
confidence
notes

TABLE: timeline_events
----------------------
id
case_id
recording_id
camera_id
event_type
original_timestamp
normalized_timestamp
confidence
source
description

TABLE: ai_results
-----------------
id
case_id
recording_id
analysis_type
model
model_version
frame_number
timestamp
class_name
confidence
bbox
track_id
source_artifact

TABLE: validation_runs
---------------------
id
case_id
ground_truth_id
job_id
started_at
completed_at
status
recovery_rate
false_positive_rate
missing_intervals
timestamp_accuracy
frame_continuity
confidence_score
notes

TABLE: provenance_events
------------------------
id
case_id
evidence_id
artifact_id
event_type
actor
timestamp
details
software_version
component_version
previous_hash
current_hash

TABLE: custody_events
---------------------
id
case_id
evidence_id
event_type
actor
timestamp
details
previous_event_hash
current_event_hash

TABLE: blockchain_anchors
-------------------------
id
case_id
audit_state_hash
network
transaction_reference
created_at
status
verified_at

TABLE: reports
-------------
id
case_id
report_type
path
created_at
software_version
report_hash
status

====================================================================
51. DATABASE RULES
====================================================================

1. Case IDs must be unique.
2. Evidence IDs must be unique.
3. Derived artifacts must point to a parent where applicable.
4. Original evidence records must not be overwritten.
5. Audit/custody events must be append-oriented.
6. Hash values must have explicit algorithms.
7. AI results must reference the source artifact/recording.
8. Recovery results must reference the source evidence and recording.
9. Validation must reference the ground truth.
10. Reports must reference the case and generated inputs.
11. Unknown values must be explicit, not fabricated.
12. Schema versions must be tracked.

====================================================================
52. STORAGE LAYOUT
====================================================================

Recommended local application data structure:

cases/
  NTRO-2026-001/
    case.json
    evidence/
      E001/
        manifest.json
        acquisition/
          source_metadata.json
          image.dd
        analysis/
          filesystem/
          recordings/
          metadata/
        recovery/
          candidates/
          fragments/
          reconstructed/
        ai/
          results/
        reports/
        audit/
          audit.jsonl
          custody.jsonl
        hashes/
          manifest.json

For very large evidence images, the application should permit configurable
storage roots.

Important:
- evidence root
- analysis root
- artifact root
- report root
should be configurable.

Do not mix temporary files into the preserved evidence image directory.

====================================================================
53. TEMPORARY VS PRESERVED DATA
====================================================================

Use separate locations:

PRESERVED:
- acquired image
- source manifests
- source hashes

WORKING:
- parsed indexes
- temporary extracted fragments
- decoded frames
- AI caches
- intermediate files

DERIVED:
- recovered recordings
- normalized metadata
- AI results
- timeline exports

REPORT:
- JSON
- PDF
- HTML
- CSV

This separation prevents accidental mutation and makes cleanup safer.

====================================================================
54. ERROR HANDLING
====================================================================

Forensic applications must not fail silently.

Error classes should include:

AcquisitionError
ReadError
HashError
IdentificationError
UnsupportedFormatError
ParserError
RecoveryError
ReconstructionError
DecodeError
TimestampError
AIError
ValidationError
ReportError
BlockchainError

Every error should record:
- timestamp
- case/evidence/job context
- component
- error type
- human-readable message
- technical details
- recovery action if any

An unsupported vendor format should become:
UNSUPPORTED / UNKNOWN

It must not be interpreted incorrectly just to make the demo look successful.

====================================================================
55. UNKNOWN / UNSUPPORTED FORMAT BEHAVIOR
====================================================================

This is critical.

If a storage structure cannot be recognized:

Do:
- preserve source
- hash it
- record device information
- record storage characteristics
- classify format as unknown
- store detection signatures
- expose parser capability status
- allow future adapter development

Do NOT:
- make up a parser interpretation
- claim recovery
- show fabricated recordings
- silently map to a wrong vendor

UI/backend status example:

format_status = "UNKNOWN"
adapter_status = "NOT_SUPPORTED"
analysis_status = "PENDING"
reason = "No registered parser matches detected storage structure"

====================================================================
56. CAPABILITY REGISTRY
====================================================================

The backend should maintain a capability registry.

Example:

CP Plus / model family / firmware range:
- device identification: yes
- filesystem parsing: yes
- recording extraction: yes
- deleted recovery: partial
- fragment reconstruction: yes
- timeline normalization: yes

Unknown model:
- identification: partial
- parser: unknown

This lets the frontend show actual capability status instead of falsely saying
every vendor is fully supported.

====================================================================
57. FORENSIC WORKFLOW ORCHESTRATOR
====================================================================

The orchestrator coordinates the modules.

Pseudo-flow:

create_case()
register_evidence()
validate_source()
calculate_hashes()
acquire_if_needed()
identify_device()
detect_storage_format()
select_adapter()
parse_storage()
enumerate_recordings()
extract_metadata()
run_recovery()
reconstruct_fragments()
decode_media()
normalize_timestamps()
build_timeline()
correlate_cameras()
run_ai()
validate_results()
finalize_provenance()
update_custody()
hash_artifacts()
anchor_audit_if_required()
generate_report()

The orchestrator should track dependencies.

Example:
AI analysis should not run before a decodable media artifact exists.
Timeline analysis should not run before usable timestamps exist.
Correlation should operate on normalized timeline data.
Reporting should collect completed results.

====================================================================
58. PROCESSING GRAPH
====================================================================

Use an explicit processing graph.

Example:

EVIDENCE E001
  |
  v
ACQUISITION A001
  |
  v
IMAGE ARTIFACT IMG001
  |
  +--> HASH H001
  |
  v
IDENTIFICATION D001
  |
  v
FILESYSTEM PARSE P001
  |
  +--> RECORDING INDEX RI001
  |
  +--> DELETED CANDIDATES RC001
  |
  v
RECOVERY R001
  |
  +--> RECOVERED ARTIFACT RA001
          |
          +--> FFmpeg decode
          |
          +--> AI results
          |
          +--> timeline
          |
          +--> validation
  |
  v
REPORT REP001

This creates traceability.

====================================================================
59. DETERMINISTIC / REPRODUCIBLE PROCESSING
====================================================================

Where possible:
- pin dependency versions
- store parser version
- store AI model version
- store tracker version
- store configuration
- store parameters
- store source hash
- store output hash

For nondeterministic AI components:
- store model version
- store environment/version
- store parameters
- document nondeterminism if relevant
- preserve source frames/artifacts

A second examiner should be able to understand what happened and why.

====================================================================
60. PERFORMANCE STRATEGY
====================================================================

Do not load a multi-terabyte image entirely into RAM.

Use:
- random-access readers
- sector/block reads
- buffered I/O
- streaming hashes
- chunked scans
- indexing
- multiprocessing only where safe
- worker processes for heavy tasks

Potential performance-sensitive areas:
- carving
- checksum/hash calculation
- filesystem scans
- frame extraction
- AI inference

C/C++ may be introduced only after profiling demonstrates a bottleneck.

Do not prematurely rewrite everything in C++.

====================================================================
61. LARGE EVIDENCE HANDLING
====================================================================

For multi-terabyte evidence:

Use:
- chunked reads
- progress tracking
- resumable jobs where practical
- error maps
- acquisition manifests
- sector-level error recording
- incremental processing

Acquisition must record unreadable sectors.

Example:

status:
PARTIAL

read_errors:
12 sectors

reason:
Unreadable source sectors during acquisition

This is better than reporting "successful" when the acquisition had missing data.

====================================================================
62. SECURITY MODEL
====================================================================

The backend should be treated as a security-sensitive local system.

Security goals:
- preserve evidence
- prevent unauthorized mutation
- prevent arbitrary code execution through crafted evidence
- isolate subprocesses
- validate file paths
- prevent path traversal
- minimize network exposure
- avoid sending evidence externally by default
- document any external/cloud AI dependency if ever introduced

Prefer:
- local processing
- offline-compatible operation
- no upload of evidence to third-party services unless explicitly configured

====================================================================
63. NETWORK ARCHITECTURE
====================================================================

The forensic backend is primarily local.

Development:

React/Tauri
    ->
localhost FastAPI
    ->
local SQLite
    ->
local evidence storage

Potential multi-user future:

Frontend
    ->
FastAPI
    ->
PostgreSQL
    ->
central evidence/workflow services

But the initial forensic workstation should remain usable without a remote
database server.

====================================================================
64. LOCALHOST API
====================================================================

Development ports can be configurable.

Example:
FastAPI:
127.0.0.1:8000

React/Vite:
127.0.0.1:5173

The desktop shell can load the frontend and communicate with the local
backend.

Final packaging should hide this complexity from the investigator.

====================================================================
65. WINDOWS + LINUX STRATEGY
====================================================================

Development platform:
Arch Linux

Primary deployment target:
Windows

Secondary:
Linux

Cross-platform code:
- Python business logic
- FastAPI
- React/TypeScript
- SQLite
- FFmpeg integration
- OpenCV
- most AI logic
- data models
- parsing logic

Platform-specific code:
- physical disk access
- native device enumeration
- low-level permissions
- system service integration
- packaging
- native path/device conventions

Architecture:

Common interface
     |
     +-- Linux implementation
     |
     +-- Windows implementation

Do not copy the Linux .venv to Windows.

Do not copy Linux node_modules to Windows.

Development dependency files are the source of truth:
- Python dependency specification
- package.json/package lock

The final Windows product should package the required runtime/dependencies so
the investigator does not manually run Python/npm commands.

====================================================================
66. BACKEND DEVELOPMENT ENVIRONMENT
====================================================================

Linux development:

python -m venv .venv
source .venv/bin/activate

Install dependencies from the project dependency specification.

Node frontend is separate and will be documented in the frontend specification.

Backend commands should eventually include:

run API
run worker
run tests
run lint
run type checks
run migration
run benchmark
run parser research tools

Do not commit:
- .venv/
- __pycache__/
- temporary evidence
- generated reports
- massive test images
- model cache files
- node_modules/

====================================================================
67. CONFIGURATION
====================================================================

Central configuration should include:

APP_ENV
APP_VERSION
DATABASE_URL
EVIDENCE_ROOT
ARTIFACT_ROOT
REPORT_ROOT
TEMP_ROOT
LOG_ROOT
FFMPEG_PATH
LIBEWF_PATH if needed
AI_MODEL_ROOT
BLOCKCHAIN_PROVIDER
BLOCKCHAIN_NETWORK
MAX_WORKERS
LOG_LEVEL

Configuration should be environment-aware.

Never hardcode a user's evidence location.

====================================================================
68. LOGGING
====================================================================

Two categories:

Technical application logs:
- server errors
- startup
- exceptions
- API operations

Forensic processing logs:
- acquisition events
- parser events
- recovery events
- AI jobs
- validation
- report generation

Forensic logs should be structured and traceable to:
- case
- evidence
- job
- artifact

Avoid using only free-form print statements.

====================================================================
69. TESTING STRATEGY
====================================================================

The project needs several test layers.

UNIT TESTS
----------
Test:
- hash calculations
- timestamp conversions
- evidence schema
- parser primitives
- fragment ordering
- confidence calculation
- audit hashing
- path validation

INTEGRATION TESTS
-----------------
Test:
- FastAPI + DB
- evidence registration
- acquisition metadata
- parser + storage reader
- recovery + artifact generation
- report generation

VENDOR TESTS
------------
Separate fixtures per vendor.

RECOVERY TESTS
--------------
Known original
  ->
modified/deleted
  ->
recovered
  ->
expected result

AI TESTS
--------
Known labelled frames
  ->
model
  ->
measure outputs

FORENSIC REGRESSION TESTS
-------------------------
Once a parser successfully handles a model/firmware fixture, keep the fixture
and expected output permanently so future changes do not break it.

====================================================================
70. VENDOR FIXTURE STRATEGY
====================================================================

Each adapter should have:

adapters/
  cp_plus/
    detector.py
    parser.py
    recovery.py
    models.py
    tests/
      fixtures/
      expected/
      test_parser.py

Same pattern for each vendor.

Fixtures should contain:
- sanitized test image or representative byte ranges
- known metadata
- expected recording index
- expected timestamps
- expected recovered artifacts where legally/ethically appropriate

Do not distribute real case evidence in the repository.

====================================================================
71. ACCEPTANCE TESTS
====================================================================

Example full-path acceptance test:

Input:
controlled CP Plus storage/test image

Expected:

1. evidence registered
2. SHA-256 computed
3. MD5 computed
4. device identified
5. format detected
6. correct adapter selected
7. recordings enumerated
8. metadata extracted
9. recovery candidates identified
10. recoverable recording reconstructed
11. media decoded by FFmpeg
12. normalized timestamp generated
13. timeline event generated
14. AI analysis executed
15. chain-of-custody updated
16. audit hash chain updated
17. report generated
18. output hashes generated
19. validation metrics generated

This should become a flagship automated regression test.

====================================================================
72. WHAT MUST BE BUILT VS WHAT MUST BE INTEGRATED
====================================================================

DO NOT BUILD OURSELVES:
- E01 specification
- H.264 decoder
- H.265 decoder
- cryptographic algorithms
- PDF rendering engine
- neural network architecture from scratch
- database engine
- blockchain protocol

USE ESTABLISHED TECHNOLOGY FOR THESE.

BUILD:
- vendor adapters
- proprietary filesystem parsing
- normalized evidence model
- recovery/reconstruction logic
- forensic workflow orchestration
- timeline normalization
- cross-camera correlation
- provenance/audit layer
- validation framework
- standardized investigation workflow

====================================================================
73. WHAT IS NOT THE CORE NOVELTY
====================================================================

Do not claim novelty for:
- RAW imaging
- E01
- MD5
- SHA-256
- FFmpeg
- OpenCV
- YOLO
- ByteTrack
- face detection
- motion detection
- timestamp correction
- file carving
- deleted video recovery
- chain of custody
- PDF reports
- blockchain
- individual vendor parsers

These are established technologies/capabilities.

Potential differentiation:
- broad and experimentally validated vendor coverage
- transparent vendor-adapter architecture
- standardized evidence representation
- unified recovery/analysis/validation workflow
- confidence reporting
- reproducibility
- evidence-linked reporting
- integration of all layers into one platform

Do not claim "nobody has done this" without a completed literature/product comparison.

====================================================================
74. IMPORTANT REALITY ABOUT EXISTING PRODUCTS
====================================================================

Commercial DVR forensic platforms already exist.

Examples found in the project research:
- Magnet WITNESS
- Amped products
- Indian DRISHTI CCTV forensic suite
- open-source vendor-specific parsers/research tools

Therefore the project positioning must NOT be:
"Nobody has a DVR forensic tool."

Correct positioning:
"Existing commercial/research tools provide substantial capabilities, but
proprietary recorder ecosystems continue to require vendor-specific support,
reverse engineering, ongoing format expansion, validation, and evidence
normalization. SIH asks for a unified workflow across the named OEM ecosystem."

The backend must prove its engineering rather than relying on novelty claims.

====================================================================
75. CAPABILITY / SUPPORT REPORTING
====================================================================

Every adapter should expose:

vendor
supported_models
supported_firmware_ranges
filesystem_formats
supported_acquisition_types
extraction_capabilities
recovery_capabilities
validation_level
limitations

Example:

CP Plus:
  parser:
    status=supported
  deleted_recovery:
    status=partial
  fragment_reconstruction:
    status=supported
  model_scope:
    model-X
  firmware_scope:
    firmware-Y

This is more honest and technically useful than a single "supported" boolean.

====================================================================
76. FORENSIC SAFETY RULES
====================================================================

Rules the backend must enforce:

1. Original evidence must be treated as immutable/read-only.
2. Derived artifacts are stored separately.
3. Every major processing step is logged.
4. Every important artifact gets a hash.
5. Original timestamps are never overwritten.
6. Unknown information is not guessed.
7. Partial recovery is reported as partial.
8. Unreadable storage is reported.
9. AI results are marked as automated analytical output.
10. Recovery confidence is explicit.
11. Software/parser/model versions are recorded.
12. Reports contain limitations.
13. Audit records are append-oriented.
14. Blockchain is used for anchors, not raw CCTV.
15. The system must not claim legal admissibility by software output alone.

====================================================================
77. BACKEND USER FLOW
====================================================================

Although this is a backend document, the API should support this investigator
workflow:

CREATE CASE
  ->
REGISTER EVIDENCE
  ->
CHOOSE/EXECUTE ACQUISITION
  ->
HASH
  ->
IDENTIFY DEVICE
  ->
DETECT FORMAT
  ->
SELECT ADAPTER
  ->
PARSE
  ->
ENUMERATE RECORDINGS
  ->
EXTRACT MEDIA/METADATA
  ->
RECOVER
  ->
RECONSTRUCT
  ->
NORMALIZE TIMELINE
  ->
CORRELATE CAMERAS
  ->
RUN AI
  ->
VALIDATE
  ->
REVIEW
  ->
CHAIN OF CUSTODY
  ->
AUDIT HASH
  ->
BLOCKCHAIN ANCHOR
  ->
GENERATE REPORT

====================================================================
78. EXAMPLE CASE
====================================================================

Example controlled case:

Case:
NTRO-2026-001

Evidence:
E001

Device:
CP Plus NVR

Storage:
2 TB HDD

Acquisition:
RAW/DD

Integrity:
SHA-256 + MD5

Identification:
CP Plus / Model-X

Filesystem:
CP Plus proprietary structure

Parser:
CPPlusAdapter v0.1

Recording:
CAM03
18:32:14 -> 18:34:45

Recovery:
Deleted candidate
Fragment reconstruction

Recovered:
2m31s

Missing:
3.2 seconds

Recovery confidence:
Medium

Timestamp normalization:
-16 seconds

Timeline:
18:31:58 normalized start

AI:
Person detected at 18:32:21
Vehicle detected at 18:33:02
Motion event at 18:32:11

Validation:
Frame continuity = measured
Timestamp error = measured
Recovery completeness = measured

Hashes:
SHA-256 = ...
MD5 = ...

Audit:
events 001...n

Blockchain:
audit anchor = ...

Report:
NTRO-2026-001.pdf

This example is illustrative. The actual values must come from real tests.

====================================================================
79. BACKEND MODULE OWNERSHIP
====================================================================

Module: Case Manager
Owns:
- cases
- status
- investigator metadata

Module: Evidence Manager
Owns:
- evidence registration
- artifact relationships

Module: Acquisition
Owns:
- acquisition paths
- image creation
- read-only workflow
- acquisition manifest

Module: Identification
Owns:
- device/model/firmware detection
- storage signature detection

Module: Adapter Registry
Owns:
- choosing vendor adapter
- capability declaration

Module: Parser
Owns:
- proprietary structures
- indexes
- metadata

Module: Recovery
Owns:
- deleted recovery
- carving
- fragment reconstruction

Module: Media
Owns:
- FFmpeg
- demux/decode
- media artifacts

Module: Timeline
Owns:
- timestamp conversion
- normalized timeline

Module: Correlation
Owns:
- cross-camera event links

Module: AI
Owns:
- object detection
- tracking
- face detection
- motion detection

Module: Validation
Owns:
- ground truth
- metrics

Module: Integrity
Owns:
- MD5
- SHA-256
- manifest verification

Module: Provenance
Owns:
- processing history
- parent-child artifacts

Module: Audit
Owns:
- hash-linked event chain
- custody

Module: Blockchain
Owns:
- anchoring
- verification

Module: Reporting
Owns:
- JSON
- PDF
- supporting report outputs

====================================================================
80. BACKEND DEPENDENCY PRINCIPLE
====================================================================

Dependency direction should generally be:

API
  ->
Application/Orchestration
  ->
Domain/Forensic logic
  ->
Infrastructure

Do not make vendor parsers depend directly on FastAPI route code.

Bad:
Parser -> FastAPI -> DB -> UI

Better:
Parser -> normalized domain result
Orchestrator -> stores result
API -> exposes result

This makes parsers testable without starting the full application.

====================================================================
81. DOMAIN / INFRASTRUCTURE SEPARATION
====================================================================

Domain:
- evidence models
- recording models
- timeline
- recovery result
- confidence
- validation metrics

Infrastructure:
- SQLite
- file storage
- libewf
- FFmpeg
- OS disk APIs
- blockchain provider

API:
- HTTP routes
- request/response schemas

AI:
- model runners
- inference workers

This separation lets us replace infrastructure components without rewriting
the forensic domain model.

====================================================================
82. BACKGROUND WORKERS
====================================================================

A worker is a process that executes long forensic operations.

Possible first implementation:
- FastAPI + Python background tasks for simpler jobs
- multiprocessing/subprocess workers for CPU-heavy or isolation-sensitive work

Later:
- dedicated task queue/worker system if needed

Do not introduce a complex distributed queue before the local workflow works.

====================================================================
83. OFFLINE-FIRST PRINCIPLE
====================================================================

A forensic workstation should be able to operate offline.

Core features must not depend on:
- internet
- cloud AI
- remote database
- external analytics API

Optional:
- blockchain anchoring needs a network path when used
- online updates can be separate
- threat/intelligence integrations can be future scope

The main forensic examination pipeline should remain local.

====================================================================
84. FILE PATH AND EVIDENCE SAFETY
====================================================================

Never allow:
- ../ traversal
- arbitrary source overwrite
- derived output written into source image directory
- uncontrolled temporary file generation beside source evidence

Use:
safe path resolver
registered evidence roots
artifact IDs

Internal functions should accept typed artifact references rather than arbitrary
frontend-provided paths wherever possible.

====================================================================
85. API RESPONSE DESIGN
====================================================================

Responses should return:
- stable IDs
- status
- timestamps
- references
- warnings
- errors
- capabilities

Example:

{
  "evidence_id": "E001",
  "status": "processing",
  "job_id": "JOB-1002",
  "warnings": []
}

Error example:

{
  "error": {
    "code": "UNSUPPORTED_FORMAT",
    "message": "No registered parser matches the detected storage structure.",
    "evidence_id": "E001"
  }
}

====================================================================
86. API VERSIONING
====================================================================

Use:
 /api/v1

When breaking changes become necessary:
 /api/v2

Also maintain:
- schema_version for persisted evidence records
- parser_version
- software_version

====================================================================
87. OBSERVABILITY
====================================================================

For development/debugging:
- structured logs
- job status
- processing counters
- memory/time measurements
- parser statistics
- recovery metrics
- FFmpeg failures
- AI inference throughput

For SIH validation:
capture measurable performance:
- acquisition throughput
- parse time
- recovery time
- AI processing time
- memory use
- storage use
- success/failure rates

====================================================================
88. BACKEND ACCEPTANCE CRITERIA
====================================================================

The backend is considered functionally credible when it can demonstrate:

A. CASE
- create case
- register evidence

B. ACQUISITION
- import native export
- import RAW/DD
- import E01
- record acquisition metadata
- calculate MD5/SHA-256

C. IDENTIFICATION
- identify test devices
- identify storage format
- select adapter

D. PARSING
- parse at least the validated vendor fixtures
- enumerate recordings
- extract metadata

E. RECOVERY
- find controlled deleted data
- reconstruct controlled fragments
- label partial/recovered states

F. TIMELINE
- preserve original timestamps
- compute normalized timestamps
- create canonical timeline

G. CORRELATION
- link events across at least a controlled multi-camera scenario

H. AI
- object detection
- tracking
- face detection
- motion detection

I. VALIDATION
- ground-truth comparison
- measured metrics

J. INTEGRITY
- hash verification
- manifest

K. PROVENANCE
- processing history
- artifact relationships

L. CHAIN
- custody log
- hash-linked audit chain

M. BLOCKCHAIN
- create/verify a case anchor

N. REPORT
- generate standardized JSON
- generate standardized PDF

====================================================================
89. DEVELOPMENT ORDER
====================================================================

Even though no feature is removed, implementation should follow dependency
order.

PHASE 1:
Backend repository + environment
- Python
- FastAPI
- SQLite
- config
- logging
- tests

PHASE 2:
Core domain models
- cases
- evidence
- artifacts
- devices
- recordings
- provenance

PHASE 3:
Hashing
- SHA-256
- MD5
- manifests

PHASE 4:
Evidence registration
- evidence roots
- artifact storage
- read-only discipline

PHASE 5:
Acquisition abstraction
- storage reader
- RAW/DD
- E01/libewf
- native export registration
- platform abstraction

PHASE 6:
Device/format identification

PHASE 7:
Vendor-adapter framework

PHASE 8:
First real vendor parser

PHASE 9:
Recording extraction + FFmpeg

PHASE 10:
Recovery engine

PHASE 11:
Timestamp normalization + timeline

PHASE 12:
Cross-camera correlation

PHASE 13:
AI
- motion
- object
- tracking
- face

PHASE 14:
Validation / ground truth

PHASE 15:
Provenance / chain of custody

PHASE 16:
Hash-linked audit

PHASE 17:
Blockchain anchoring

PHASE 18:
Standardized reporting

PHASE 19:
Additional OEM adapters

PHASE 20:
Cross-platform packaging and Windows validation

This is sequencing, not feature removal.

====================================================================
90. FIRST BACKEND MILESTONE
====================================================================

Before working on proprietary DVR parsing, create a fully traceable dummy
evidence path.

Example:

Create Case
  ->
Register test video/evidence file
  ->
Hash it
  ->
Create artifact
  ->
Store metadata
  ->
Create processing event
  ->
Build audit hash chain
  ->
Generate JSON report

Why:
This establishes the core infrastructure every later parser/recovery module
will use.

Then the same evidence model can accept a real CP Plus image.

====================================================================
91. SECOND BACKEND MILESTONE
====================================================================

Add generic forensic storage abstraction:

Input:
- a normal file
- a RAW/DD image

Interface:
read(offset, length)
size()
metadata()

Then implement:
- file-backed reader
- raw-image reader

After that, E01 can be added through the same interface.

The parser should not need separate code for each storage container.

====================================================================
92. THIRD BACKEND MILESTONE
====================================================================

Build the vendor adapter skeleton.

Base class:
DVRAdapter

Registry:
AdapterRegistry

Capabilities:
AdapterCapability

Example:

register_adapter(
    vendor="CP Plus",
    model_pattern="...",
    firmware_pattern="..."
)

Then:
select_adapter(device_identification_result)

At this stage, the parser can return "unsupported" cleanly.

====================================================================
93. FOURTH BACKEND MILESTONE
====================================================================

Implement the first real parser using controlled test evidence.

Recommended first target:
CP Plus, because project research indicates controlled equipment/data access.

Workflow:
- acquire/create controlled test image
- inspect binary structure
- identify partition/format
- identify recording structures
- document fields
- implement parser
- extract recordings
- validate against known source recordings

Do not begin eight parser implementations at the same time.

Implement the architecture once, then replicate the adapter pattern.

====================================================================
94. FIFTH BACKEND MILESTONE
====================================================================

Turn extracted recordings into normalized EvidenceRecord objects.

At this point:
CP Plus
   ->
CP Plus adapter
   ->
NormalizedEvidence

Then everything downstream is vendor-independent.

This is one of the most important architectural checkpoints.

====================================================================
95. SIXTH BACKEND MILESTONE
====================================================================

Add recovery.

Test scenarios:
- existing recording
- deleted recording
- fragmented recording
- partially corrupted recording
- unreadable sector simulation where safe

Compare:
expected vs recovered

Produce:
recovery status
metrics
confidence

====================================================================
96. SEVENTH BACKEND MILESTONE
====================================================================

Add timeline and correlation.

Create:
- original timestamp
- normalized timestamp
- offset
- confidence
- canonical event

Then test:
two cameras with deliberately different recorder clocks.

====================================================================
97. EIGHTH BACKEND MILESTONE
====================================================================

Add AI analysis.

Flow:

Normalized recording
  ->
frame extraction
  ->
YOLO
  ->
tracking
  ->
face detection
  ->
motion
  ->
AI result records
  ->
timeline events

Every AI result stays linked to:
- evidence
- recording
- frame
- timestamp
- model version

====================================================================
98. NINTH BACKEND MILESTONE
====================================================================

Add validation.

Ground truth:
original recording

Test:
recovery result

Metrics:
- recovery rate
- false positive rate
- missing intervals
- timestamp accuracy
- frame continuity
- confidence

Store the result in the database and expose it through the API.

====================================================================
99. TENTH BACKEND MILESTONE
====================================================================

Add final provenance and reporting.

Report must show:
- case
- evidence
- device
- acquisition
- hashes
- parser
- recordings
- recovery
- timeline
- AI
- validation
- chain of custody
- limitations

Then add blockchain anchoring.

====================================================================
100. BACKEND OUTPUT CONTRACT
====================================================================

For every investigation, the backend should ultimately be capable of producing:

CASE:
case.json

EVIDENCE:
evidence_manifest.json

HASH:
hash_manifest.json

DEVICE:
device.json

RECORDINGS:
recordings.json

METADATA:
metadata.json

RECOVERY:
recovery_results.json

TIMELINE:
timeline.json

CORRELATION:
correlation.json

AI:
ai_results.json

VALIDATION:
validation_results.json

AUDIT:
audit_log.jsonl

CUSTODY:
chain_of_custody.jsonl

BLOCKCHAIN:
anchors.json

REPORT:
forensic_report.pdf
forensic_report.json

MEDIA:
recovered/*.mp4 or the applicable reconstructed media format

====================================================================
101. WHAT THE BACKEND SHOULD NEVER DO
====================================================================

Never:
- overwrite original evidence
- modify original timestamps
- fabricate metadata
- claim unsupported vendor support
- claim complete recovery when recovery is partial
- treat AI inference as fact
- expose arbitrary shell execution through the API
- store evidence without provenance
- silently ignore acquisition errors
- hide unreadable sectors
- use blockchain as a CCTV storage system
- assume one filesystem parser fits every DVR
- assume FFmpeg can parse proprietary DVR storage
- copy a Linux virtual environment into Windows deployment
- rely on a browser for low-level evidence acquisition

====================================================================
102. KEY TECHNICAL TERMS
====================================================================

DVR:
Digital Video Recorder.

NVR:
Network Video Recorder.

Evidence:
Information/data preserved for forensic examination.

Acquisition:
Obtaining evidence from the source.

Forensic image:
Data-level representation of storage used for analysis and preservation.

RAW/DD:
Direct byte-for-byte storage image.

E01:
Expert Witness forensic image container.

Write blocker:
Hardware/software mechanism that prevents writing to source evidence.

Filesystem:
Data structure that organizes storage.

Proprietary format:
Vendor-specific storage/data format.

Parser:
Program that interprets a structured data format.

Binary analysis:
Inspection of raw machine-readable bytes.

Adapter:
Vendor-specific module translating vendor data into the common evidence model.

Metadata:
Information describing other data.

Codec:
Technology for encoding/decoding video.

Demuxer:
Component that separates streams from a multiplexed container/source.

Recovery:
Obtaining recordings/data that are deleted, damaged, inaccessible, or
fragmented.

Carving:
Searching raw storage for recognizable data structures.

Fragment:
Piece of a larger recording.

Reconstruction:
Reassembling fragments into a recording.

Timestamp normalization:
Converting differing source clocks/timestamps into a common timeline while
preserving originals.

Canonical timeline:
Unified investigation timeline.

Correlation:
Linking related events across cameras/evidence.

Provenance:
History/source/processing lineage of evidence.

Chain of custody:
Chronological record of evidence handling.

Ground truth:
Known correct dataset/result used to measure the system.

False positive:
System reports something that is not actually present.

Confidence:
How strongly a result is supported by available evidence.

Object detection:
Finding/classifying objects in video frames.

Face detection:
Locating faces in video frames.

Face recognition:
Attempting to identify a person's identity from facial features.

Tracking:
Following an object across frames.

Motion detection:
Detecting image/scene changes consistent with movement.

Inference:
Running an AI model on data.

Normalization:
Converting different vendor representations into one common model.

Audit log:
Record of system/evidence operations.

Hash chain:
Audit records linked through hashes.

Blockchain anchor:
Recording a cryptographic fingerprint externally so later changes can be
detected.

Reproducibility:
Ability for another trained examiner to understand/repeat the workflow.

Validation:
Testing whether a result is correct.

====================================================================
103. JUDGE-DEFENSIBILITY PRINCIPLES FOR THE BACKEND
====================================================================

Question:
"Why not just export the CCTV?"

Backend answer:
Normal export may be sufficient when evidence is accessible, but forensic
requirements can require storage-level acquisition, deleted-data recovery,
metadata, and preservation of source evidence.

Question:
"Why do you need the HDD?"

Because the underlying storage may contain proprietary structures, metadata,
and inaccessible/deleted information not exposed through normal export.

Question:
"Why use vendor adapters?"

Because vendors can organize storage, metadata, indexes, deletion behavior,
and recording structures differently. Adapters isolate these differences.

Question:
"Why not FFmpeg?"

FFmpeg decodes media. It does not replace proprietary DVR filesystem parsing.

Question:
"Why do you use blockchain?"

To anchor evidence/audit fingerprints so later alteration can be detected.
The CCTV content remains off-chain.

Question:
"Does AI prove the person is the suspect?"

No. AI provides an automated analytical result linked to source evidence,
model/version/confidence, which remains subject to examiner review.

Question:
"What if recovery is incomplete?"

Report it explicitly as PARTIAL, including missing intervals and reason.

Question:
"Can another examiner reproduce the processing?"

The backend records evidence IDs, acquisition data, software/parser/model
versions, parameters, processing steps, hashes, and validation results.

====================================================================
104. FINAL BACKEND STACK SUMMARY
====================================================================

Language:
Python

API:
FastAPI

Database:
SQLite initially
PostgreSQL at scale

Forensic images:
RAW/DD
E01 via libewf

Hashing:
SHA-256
MD5

Binary analysis:
Python + structured binary tooling
C/C++ only where genuinely necessary

Video:
FFmpeg

Computer vision:
OpenCV

Object detection:
YOLO

Tracking:
ByteTrack / BoT-SORT

Face:
Face detection

Motion:
Classical computer vision initially

Architecture:
Vendor adapters
Normalized evidence model

Recovery:
Filesystem/index
Vendor-specific
Carving
Fragment reconstruction

Timeline:
Canonical normalized timeline

Integrity:
SHA-256 + MD5
Hash manifests

Provenance:
Processing history
Artifact lineage

Audit:
Hash-linked audit log

Blockchain:
Evidence/provenance anchoring

Reporting:
JSON + PDF
Optional HTML/CSV/manifests

Deployment:
Arch Linux development
Windows primary target
Cross-platform core
OS-specific storage abstraction

Desktop integration:
React + TypeScript frontend
Tauri desktop shell
Python/FastAPI backend

====================================================================
105. FINAL ARCHITECTURAL STATEMENT
====================================================================

The backend is not "an API that reads CCTV videos."

It is a forensic evidence-processing engine.

Its central architectural idea is:

HETEROGENEOUS DVR/NVR EVIDENCE
          ->
VENDOR-SPECIFIC ADAPTERS
          ->
NORMALIZED FORENSIC EVIDENCE
          ->
COMMON RECOVERY / TIMELINE / AI / VALIDATION ENGINE
          ->
INTEGRITY + PROVENANCE + CHAIN OF CUSTODY
          ->
BLOCKCHAIN ANCHOR
          ->
STANDARDIZED FORENSIC REPORT

The central engineering priority is:

WORKING IMPLEMENTATION
        ->
MEASURABLE VALIDATION
        ->
TECHNICAL DEFENSIBILITY
        ->
DIFFERENTIATION
        ->
NOVELTY

Novelty is not a substitute for implementation.

====================================================================
106. SOURCE BASIS
====================================================================

This backend specification was assembled from the project materials provided
for SIH 26150:

1. "SIH Tech Stack.txt"
2. "SIH NTRO Requirements.txt"

Important source-derived decisions include:
- RAW/DD + E01 support
- libewf for E01 handling
- SHA-256 + MD5
- vendor-specific adapter architecture
- common normalized evidence model
- FFmpeg + OpenCV
- YOLO object detection
- ByteTrack / BoT-SORT
- face detection
- classical motion detection initially
- canonical timeline
- layered recovery
- ground-truth validation
- provenance
- hash-linked audit log + blockchain anchoring
- SQLite initially and PostgreSQL at scale
- FastAPI/Python backend
- React + TypeScript frontend
- JSON + PDF reporting

The project materials explicitly emphasize implementation over unsupported
novelty claims and identify reliable multi-vendor normalization/validation as
a major engineering challenge.

END OF BACKEND MASTER SPECIFICATION
====================================================================

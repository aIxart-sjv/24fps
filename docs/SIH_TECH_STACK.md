SIH Tech Stack

The goal is not to pick the "best technology in the world."

It is to pick the **best defensible technology for SIH26150**, given:

* SIH/NTRO requirements
* forensic requirements
* our available hardware/data
* development time
* team capability
* implementation feasibility
* judge defensibility

> **For SIH, Implementation > Novelty.**

A technically impressive novelty claim means very little if we cannot implement it, demonstrate it, validate it, and explain it under questioning.

Our priority is:

**Working implementation → measurable validation → technical defensibility → differentiation/novelty.**

Novelty should strengthen the project, not replace implementation.

---

# 1. Forensic Acquisition

**Purpose:** Make a trustworthy copy of the DVR/NVR storage before analysis.

### Options

| Approach            | What it does                | Advantages                                                | Disadvantages                                              | Decision                |
| ------------------- | --------------------------- | --------------------------------------------------------- | ---------------------------------------------------------- | ----------------------- |
| **RAW/DD**          | Bit-for-bit copy of storage | Simple, open, tool-independent, exact representation      | Large; acquisition metadata stored separately              | **KEEP**                |
| **E01/EWF**         | Forensic image container    | Metadata, segmentation, compression, verification support | More complex; tooling dependency                           | **PRIMARY / SUPPORTED** |
| Vendor export       | Export selected recordings  | Easy; fast                                                | May omit deleted data, proprietary structures and metadata | **NOT primary**         |
| Logical acquisition | Copy selected files/data    | Fast and selective                                        | Does not preserve complete physical storage                | **Secondary only**      |

### Decision

**Support RAW/DD and E01 rather than pretending one is universally superior.**

Conceptually:

```text
DVR/NVR storage
       ↓
write-protected acquisition
       ↓
RAW/DD or E01
       ↓
hash
       ↓
forensic analysis copy
```

E01 is a **forensic image container** (a structured container for forensic evidence images).

RAW/DD is a **bit-for-bit image** (a direct representation of the source storage).

We should not claim E01 is inherently more "forensically correct" than RAW.

### Technology

**libewf** for EWF/E01 handling.

We should not implement E01 ourselves.

### SIH relevance

**Directly required by NTRO.**

NTRO asks for forensic acquisition and a DVR/NVR forensic image.

### Novelty

❌ **Not novel.**

Forensic imaging is established technology.

Our differentiation must come from **what happens after acquisition**, especially heterogeneous proprietary DVR processing, recovery, normalization, validation and unified analysis.

---

# 2. E01 Implementation

### Options

* Proprietary forensic software
* libewf
* Custom E01 implementation

### Decision

**libewf**

It is an established open-source library for accessing EWF/E01 formats.

We absolutely should **not implement E01 ourselves**.

### SIH relevance

Supports the forensic-image requirement.

### Novelty

❌ **Not novel.**

Using E01 is an implementation decision, not our innovation.

### Links

[https://github.com/libyal/libewf](https://github.com/libyal/libewf)

[https://github.com/libyal/libewf/blob/main/documentation/Expert%20Witness%20Compression%20Format%20%28EWF%29.asciidoc](https://github.com/libyal/libewf/blob/main/documentation/Expert%20Witness%20Compression%20Format%20%28EWF%29.asciidoc)

---

# 3. Evidence Hashing

**Hash (a mathematical fingerprint used to detect whether data has changed).**

NTRO explicitly asks for:

* MD5
* SHA-256

### Decision

**Use both.**

```text
Original acquisition
        ↓
   MD5 + SHA-256
        ↓
 Store evidence hashes
        ↓
Analysis
        ↓
Recalculate
        ↓
Compare
```

### Why both?

Because **NTRO explicitly asks for both**.

Use:

**SHA-256 = primary integrity hash**

**MD5 = additional identifier / NTRO-required hash**

Do not claim MD5 is secure against modern cryptographic attacks.

### SIH relevance

**Explicitly required.**

### Novelty

❌ **Not novel.**

Hashing is standard forensic practice.

---

# 4. Proprietary Filesystem / Format Parsing

This is one of the **core technical challenges**.

**Filesystem (the structure used to organize data on storage).**

### Options

| Approach                    | Advantages                    | Problems                                                 | Decision                 |
| --------------------------- | ----------------------------- | -------------------------------------------------------- | ------------------------ |
| Vendor SDK                  | Potentially easier            | Vendor dependency; may not expose raw/deleted structures | Secondary                |
| Existing open-source parser | Fast starting point           | Limited vendors/models                                   | **Use where available**  |
| Filesystem libraries        | Good for standard filesystems | DVR formats may be proprietary                           | Supporting layer         |
| Custom parser               | Full control                  | Extremely difficult                                      | **Core where necessary** |
| Generic file carving        | Can recover fragments         | Loses filesystem context; false positives                | Recovery fallback        |

### Decision

**Hybrid vendor-adapter architecture.**

```text
Known standard filesystem
        ↓
Existing filesystem library

Known proprietary format
        ↓
Existing parser
        ↓
Adapt / extend

Unknown proprietary format
        ↓
Binary analysis
        ↓
Custom vendor adapter
```

### Why?

There is no realistic single parser that understands every proprietary DVR/NVR storage format.

Instead, each vendor/model family gets an **adapter** (a module that translates vendor-specific structures into our common format).

### SIH relevance

**Directly required.**

NTRO explicitly asks us to parse proprietary filesystems and formats.

### Novelty

❌ **Filesystem parsing itself is not novel.**

⚠️ **Potential differentiation:**

The **standardized adapter architecture + common evidence representation + unified downstream processing** may provide differentiation, but this must not be claimed as proven novelty without further comparison against existing platforms.

### Evidence

[https://www.mdpi.com/2078-2489/16/11/983](https://www.mdpi.com/2078-2489/16/11/983)

[https://github.com/akira7799/hikvision-dvr-parser](https://github.com/akira7799/hikvision-dvr-parser)

[https://github.com/vishwajitsarnobat/HIKVISION-DVR-Tool](https://github.com/vishwajitsarnobat/HIKVISION-DVR-Tool)

[https://github.com/DmytroMoisiuk/DVR_Dahua](https://github.com/DmytroMoisiuk/DVR_Dahua)

[https://github.com/haliner/dvr-recover](https://github.com/haliner/dvr-recover)

---

# 5. Binary Analysis

**Binary analysis (examining raw machine-readable bytes to understand how information is structured).**

### Tools / approaches

* Python
* C/C++
* Hex editor
* Kaitai Struct
* Custom parser
* Existing forensic libraries

### Decision

**Python for initial research/prototyping + existing binary-analysis tools/libraries + C/C++ only where performance or low-level access genuinely requires it.**

Do not build the entire parser in C++ from day one.

### Why?

We need rapid experimentation because proprietary formats are usually discovered through repeated analysis:

```text
Raw bytes
 ↓
Identify patterns
 ↓
Hypothesize structure
 ↓
Test
 ↓
Parse
 ↓
Validate against known recording
```

### SIH relevance

Supports the proprietary filesystem/format parsing requirement.

### Novelty

❌ Binary analysis itself is not novel.

The potential contribution is applying it systematically across the target vendor ecosystem and feeding the result into a standardized forensic workflow.

---

# 6. Video Decoding

### Options

| Technology | Strength                                       | Weakness                                           | Decision             |
| ---------- | ---------------------------------------------- | -------------------------------------------------- | -------------------- |
| **FFmpeg** | Broad codec/container support; CLI + libraries | Doesn't understand arbitrary proprietary DVR files | **PRIMARY**          |
| OpenCV     | Excellent video-processing interface           | Not a forensic container/parser                    | **Use above FFmpeg** |
| GStreamer  | Powerful pipeline architecture                 | More complexity than needed initially              | Alternative          |
| VLC/libVLC | Excellent playback                             | Not ideal as core forensic processing engine       | No                   |

### Decision

**FFmpeg**

But remember:

> **FFmpeg does NOT solve proprietary DVR filesystem parsing.**

Architecture:

```text
DVR storage
 ↓
Vendor parser
 ↓
Recovered video stream
 ↓
FFmpeg
 ↓
Decoded frames
```

### SIH relevance

Supports video extraction and decoding.

### Novelty

❌ **FFmpeg is not novel.**

The innovation is not the decoder.

It is the **forensic pipeline around it**.

### Links

[https://ffmpeg.org/documentation.html](https://ffmpeg.org/documentation.html)

[https://ffmpeg.org/general.html](https://ffmpeg.org/general.html)

---

# 7. Video Processing

### Decision

**FFmpeg + OpenCV**

```text
FFmpeg
= demux / decode / convert

OpenCV
= frames / image processing / computer vision
```

### Why?

Use the right tool for the right layer.

Don't make OpenCV responsible for proprietary DVR parsing.

### SIH relevance

Supports extraction, decoding and subsequent video analysis.

### Novelty

❌ Not novel.

### Link

[https://docs.opencv.org/](https://docs.opencv.org/)

---

# 8. Object Detection

NTRO explicitly asks for:

* face detection
* object detection
* motion detection

### Options

* YOLO
* Faster R-CNN
* RT-DETR
* SSD
* custom model

### Decision

**YOLO for the initial object-detection implementation.**

Why?

* mature ecosystem
* pretrained models
* real-time focus
* Python support
* tracking support
* custom training
* deployment options

### Important

Do **not** claim:

> "YOLO is the most accurate detector."

Instead:

> **"YOLO is our initial choice because it provides a strong development-speed, accuracy and inference-performance trade-off. We will benchmark it against alternatives if required."**

### SIH relevance

**Explicitly required.**

### Novelty

❌ Object detection is not novel.

Using YOLO is not novel.

The value comes from connecting AI results to **forensic evidence, timestamps, cameras and investigation workflows**.

### Link

[https://docs.ultralytics.com/](https://docs.ultralytics.com/)

---

# 9. Object Tracking

**Tracking (following the same detected object across multiple video frames).**

### Options

* ByteTrack
* BoT-SORT
* DeepSORT
* Custom tracking

### Decision

**ByteTrack / BoT-SORT.**

Start with whichever performs better on our CCTV footage.

Do not permanently lock the tracker before testing.

### Architecture

```text
Frame
 ↓
YOLO detection
 ↓
Tracker
 ↓
Object ID
 ↓
Position over time
 ↓
Camera timeline
```

### SIH relevance

Supports intelligent video analysis and cross-camera investigation.

### Novelty

❌ Tracking itself is not novel.

The potential contribution is **forensic integration**, not the tracker.

### Link

[https://docs.ultralytics.com/modes/track/](https://docs.ultralytics.com/modes/track/)

---

# 10. Face Detection vs Face Recognition

This distinction is important.

NTRO asks for:

> **Face detection**

It does not explicitly require identifying the person's name.

### Decision

**Round 1 / core: Face detection**

```text
Frame
 ↓
Face detector
 ↓
Bounding box
 ↓
Timestamp
 ↓
Camera
```

### Optional future capability

**Face recognition**

```text
Face
 ↓
Embedding
 ↓
Comparison
 ↓
Possible identity
```

### Why not make recognition core?

It introduces:

* privacy concerns
* additional datasets
* false matches
* threshold selection
* identity database requirements
* greater legal/forensic complexity

### Novelty

❌ Face detection/recognition is not novel.

Again, the useful contribution is integrating detection results with **forensic evidence and timeline analysis**.

---

# 11. Motion Detection

### Options

* Frame differencing
* Background subtraction
* Optical flow
* Deep-learning models

### Decision

**Classical computer vision first.**

Example:

```text
Frame N
 ↓
Frame N+1
 ↓
Difference
 ↓
Threshold
 ↓
Motion region
```

### Why?

Motion detection does not automatically require AI.

Use the simplest method that works.

### SIH relevance

**Explicitly requested by NTRO.**

### Novelty

❌ Motion detection is not novel.

---

# 12. Timestamp Normalization

**Timestamp normalization (converting different or incorrect time representations into a common investigation timeline while preserving the original values).**

### Inputs

* DVR timestamp
* File metadata timestamp
* Filesystem timestamp
* Camera timestamp
* System clock
* Timezone
* Known external event

### Decision

Create a **canonical timeline**.

```text
Original timestamp
       ↓
Timezone interpretation
       ↓
Clock-offset estimation
       ↓
Normalized timestamp
       ↓
Confidence
       ↓
Canonical timeline
```

### Critical rule

**Never overwrite the original timestamp.**

Store:

```text
Original:
2026-08-25 19:10:03

Normalized:
2026-08-25 19:17:41

Offset:
+7m38s

Confidence:
High

Method:
DVR clock comparison
```

### SIH relevance

**Explicitly requested.**

### Novelty

❌ Timestamp correction/normalization itself is not novel.

Potential differentiation lies in applying it consistently across heterogeneous vendors and preserving the original evidence/provenance.

---

# 13. Deleted / Damaged / Fragmented Video Recovery

This is one of our most difficult modules.

### Methods

**A. Filesystem/index recovery**

Recover recordings whose metadata/index structures still exist.

**B. File carving**

Search raw storage for recognizable data structures.

**C. Fragment reconstruction**

Determine which fragments belong together.

**D. Vendor-specific reconstruction**

Use knowledge of the recorder's storage architecture.

### Decision

**Layered recovery system**

```text
Level 1
Filesystem/index recovery
        ↓
Level 2
Vendor-specific recovery
        ↓
Level 3
File/frame carving
        ↓
Level 4
Fragment reconstruction
```

### Important limitation

We cannot promise:

> "We recover every deleted recording."

If storage blocks have been overwritten, recovery may be impossible.

### SIH relevance

**Explicitly required.**

NTRO specifically asks for deleted and damaged recording recovery.

### Novelty

❌ Deleted-video recovery itself is **not novel**.

Existing research and commercial systems already perform it.

Potential differentiation is in:

* broader vendor coverage
* standardized recovery workflow
* validation
* confidence reporting
* reproducibility

Those are **potential contributions**, not automatically proven novelty.

### Evidence

[https://www.mdpi.com/2078-2489/16/11/983](https://www.mdpi.com/2078-2489/16/11/983)

[https://github.com/DmytroMoisiuk/DVR_Dahua](https://github.com/DmytroMoisiuk/DVR_Dahua)

[https://github.com/haliner/dvr-recover](https://github.com/haliner/dvr-recover)

---

# 14. Recovery Validation

This should be treated as a **first-class engineering component**.

Question:

> "How do we know the recovered video is correct?"

### Decision

Use controlled **ground-truth datasets**.

```text
Known recording
      ↓
Delete / damage / fragment
      ↓
Acquire storage
      ↓
Recover
      ↓
Compare with ground truth
```

Measure:

* recovery rate
* false positives
* missing intervals
* timestamp accuracy
* frame continuity
* reconstruction confidence

### Our actual testing advantage

We have access to:

* CP Plus NVR/cameras
* TP-Link cameras
* Hikvision access through college
* Xiaomi data from a friend
* potential additional vendor data

This means we can eventually generate controlled test cases rather than relying only on downloaded videos.

### SIH relevance

Supports the requirement for reliable recovery, validation and legally defensible evidence.

### Novelty

**Validation methodology may be a stronger differentiation area than recovery itself.**

But:

> Do not claim it is novel until we complete the literature/product comparison.

This is a place where **implementation + measurable results** matter more than claiming novelty.

---

# 15. Evidence Provenance

**Provenance (the recorded history of where evidence came from and what happened to it).**

### Decision

Create structured case records:

```text
Case ID
Evidence ID
Source device
Vendor
Model
Firmware
Acquisition time
Examiner
Image hash
Analysis software version
Parser version
Processing steps
Output hashes
```

### SIH relevance

Supports evidence integrity, chain of custody and standardized reporting.

### Novelty

❌ Provenance tracking itself is not novel.

Our contribution would be integrating it throughout the **multi-vendor forensic pipeline**.

---

# 16. Blockchain vs Hash-Linked Audit Log

SIH26150 belongs to:

**Blockchain & Cybersecurity**

But we should not force blockchain into every part of the system.

### Options

| Approach              | Advantages                   | Disadvantages                   | Decision                     |
| --------------------- | ---------------------------- | ------------------------------- | ---------------------------- |
| Database audit log    | Simple, fast                 | Central authority can modify it | Supporting layer             |
| Hash-linked audit log | Tamper-evident               | Still locally controlled        | **PRIMARY**                  |
| Blockchain            | Distributed/tamper-resistant | Complexity and overhead         | **Evidence anchoring layer** |
| Private blockchain    | Controlled participants      | More infrastructure             | Future                       |

### Updated Decision

**Hash-linked audit log + blockchain anchoring.**

```text
Evidence event
      ↓
Hash
      ↓
Audit record
      ↓
Previous-record hash
      ↓
Hash chain
      ↓
Periodic / important-case
blockchain anchor
```

**Blockchain anchoring (recording a cryptographic fingerprint on a blockchain so later alteration can be detected).**

This gives us a genuine cybersecurity/blockchain component without pretending that a blockchain should store the actual CCTV evidence.

### SIH relevance

Supports the **Blockchain & Cybersecurity theme** and evidence-integrity requirements.

### Novelty

❌ Blockchain itself is not novel.

❌ Hash-linked logs are not novel.

Potential differentiation is **how evidence provenance is integrated with the forensic workflow**, not the cryptographic primitive.

---

# 17. Database

### Options

* SQLite
* PostgreSQL
* MongoDB

### Decision

### Round 1 / local forensic workstation

**SQLite**

### Scaled multi-user platform

**PostgreSQL**

```text
Prototype
Python + SQLite

        ↓

Scaled platform
FastAPI + PostgreSQL
```

### Why?

A forensic workstation doesn't need a database server just because one exists.

Start simple.

### SIH relevance

Supporting infrastructure.

### Novelty

❌ Not novel.

---

# 18. Backend

### Options

* FastAPI
* Flask
* Django
* Node.js

### Decision

**Python + FastAPI**

Why?

The forensic/AI pipeline is already Python-friendly:

```text
Python
 ├── forensic orchestration
 ├── parsers
 ├── FFmpeg integration
 ├── OpenCV
 ├── AI
 ├── database
 └── API
```

FastAPI provides the API layer.

Performance-critical components can later move to C/C++.

### SIH relevance

Implementation infrastructure.

### Novelty

❌ Not novel.

---

# 19. Frontend

### Options

* React
* Vue
* Plain HTML
* Desktop GUI

### Decision

**React + TypeScript**

But:

> **Do not spend Round-1 time building a beautiful dashboard.**

The forensic workflow is the product.

UI should primarily expose:

```text
Evidence
Devices
Recordings
Timeline
Recovered files
Camera correlation
AI results
Hashes
Chain of custody
Report
```

### SIH relevance

User interface for the forensic platform.

### Novelty

❌ React is not novel.

❌ Dashboard UI is not novel.

---

# 20. Reporting

### Options

* HTML
* PDF
* JSON
* DOCX

### Decision

**Structured JSON + human-readable PDF**

JSON:

**Machine-readable evidence representation.**

PDF:

**Human-readable investigation report.**

Report should contain:

```text
Case information
Evidence source
Acquisition information
Hashes
Device information
Recovered recordings
Timeline
Processing methods
AI results
Limitations
Chain of custody
Software versions
```

### SIH relevance

**Explicitly required.**

NTRO asks for standardized forensic reporting.

### Novelty

❌ PDF reporting itself is not novel.

Potential differentiation:

**A standardized report generated from the same normalized evidence model across different vendors.**

That is an architectural advantage, but not automatically a novel invention.

---

# 21. Vendor Architecture

This is one of the most important architectural choices.

### Options

**One giant parser**

❌ Reject.

**Separate standalone programs**

❌ Reject.

**Adapter/plugin architecture**

✅ **Choose.**

```text
                    Common Forensic Core
                            │
          ┌─────────────────┼─────────────────┐
          ↓                 ↓                 ↓
      CP Plus           Hikvision           Dahua
      Adapter             Adapter           Adapter
          ↓                 ↓                 ↓
          └─────────────────┼─────────────────┘
                            ↓
                  Normalized Evidence
```

### Why?

Each vendor can have different:

* filesystem
* metadata
* storage layout
* recording structure
* firmware
* encoding
* indexing

The common core should not need to understand every vendor's internals.

The adapter translates:

**Vendor-specific evidence → common evidence model**

### SIH relevance

**Central requirement.**

NTRO specifically asks for a **multi-vendor / vendor-agnostic platform**.

### Novelty

⚠️ **Adapter architecture itself is not automatically novel.**

The stronger potential contribution is the combination of:

> **heterogeneous proprietary DVR/NVR acquisition + vendor-specific adapters + normalized forensic evidence representation + common recovery/analysis/validation/reporting pipeline.**

We must still verify competing commercial/research systems before calling this a novel contribution.

---

# 22. Standardized Evidence Model

Every adapter should produce the same conceptual structure.

```text
Evidence
├── device
│   ├── vendor
│   ├── model
│   ├── firmware
│   └── serial
│
├── recording
│   ├── camera
│   ├── start
│   ├── end
│   ├── codec
│   ├── source
│   └── recovery_status
│
├── metadata
├── timeline
├── hashes
├── provenance
└── confidence
```

This lets the downstream engine work consistently regardless of vendor.

### SIH relevance

Supports the vendor-agnostic requirement.

### Novelty

⚠️ **Potential differentiation area.**

But we must not claim:

> "Nobody has done this."

until competing platforms and research are fully compared.

---

# 23. What We Should NOT Build Ourselves

This is critical for SIH.

### Don't implement:

❌ E01 specification
❌ H.264 decoder
❌ H.265 decoder
❌ Cryptographic algorithms
❌ PDF rendering engine
❌ Object-detection neural network from scratch
❌ Video codec
❌ Database engine
❌ Blockchain protocol

### Build:

✅ Vendor adapters
✅ Proprietary filesystem parsing
✅ Normalized evidence model
✅ Recovery/reconstruction logic
✅ Forensic workflow orchestration
✅ Timeline normalization
✅ Cross-camera correlation
✅ Provenance/audit layer
✅ Validation framework
✅ Standardized investigation workflow

### SIH principle

> **Use mature components where they already solve the problem. Build the parts that are specific to NTRO's problem.**

This is where **Implementation > Novelty** matters most.

---

# 24. FINAL TECHNOLOGY STACK

This is the stack we can use for the PPT.

```text
┌──────────────────────────────────────────────┐
│                  FRONTEND                    │
│              React + TypeScript              │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│                    API                       │
│                  FastAPI                     │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│               FORENSIC CORE                  │
│                   Python                     │
│                                              │
│  Device Identification                      │
│  Evidence Management                        │
│  Vendor Adapters                            │
│  Timeline Engine                            │
│  Recovery Engine                            │
│  Correlation Engine                         │
└─────────────┬─────────────────┬──────────────┘
              │                 │
              ▼                 ▼
       Vendor Adapters      Filesystem /
       CP Plus              Binary Analysis
       Hikvision
       Dahua
       TP-Link
       etc.
              │
              ▼
       NORMALIZED EVIDENCE
              │
       ┌──────┴──────┐
       ▼             ▼
    FFmpeg         OpenCV
       │             │
       │        Computer Vision
       │             │
       └──────┬──────┘
              ▼
        AI ANALYTICS
        YOLO + Tracking
        Face Detection
        Motion Detection
              │
              ▼
       TIMELINE / CORRELATION
              │
              ▼
       INTEGRITY LAYER
       SHA-256 + MD5
              │
              ▼
       HASH-LINKED AUDIT LOG
              │
              ▼
       BLOCKCHAIN ANCHOR
              │
              ▼
          REPORTING
         JSON + PDF
              │
              ▼
            SQLite
              │
              ▼
      PostgreSQL at scale
```

---

# 25. What Is Actually Novel?

This needs to be extremely clear.

## ❌ NOT our novelty

We should **not** claim novelty for:

* E01
* RAW imaging
* MD5
* SHA-256
* FFmpeg
* OpenCV
* YOLO
* ByteTrack
* face detection
* motion detection
* timestamp correction
* file carving
* deleted-video recovery
* chain of custody
* PDF reports
* blockchain
* individual Hikvision/Dahua parsers

These already exist.

---

## ⚠️ Potential contribution / differentiation

Our strongest direction is the **combination and implementation**:

### 1. Vendor-adapter architecture

A common forensic engine with vendor-specific modules.

```text
CP Plus ─┐
Hikvision ─┤
Dahua ─────┤
TP-Link ───┤ → Common forensic representation
Uniview ───┤
Matrix ────┘
```

### 2. Normalized evidence representation

Different proprietary structures become a common evidence model.

### 3. One forensic workflow

```text
Acquisition
 ↓
Identification
 ↓
Parsing
 ↓
Recovery
 ↓
Timeline
 ↓
Correlation
 ↓
AI
 ↓
Validation
 ↓
Provenance
 ↓
Report
```

rather than investigators manually moving between unrelated tools.

### 4. Recovery + validation

Not simply:

> "We recovered a video."

But:

> **"We recovered it, reconstructed it, measured the recovery quality, retained provenance, and report confidence/limitations."**

### 5. Cross-vendor investigation

The eventual goal is:

```text
CP Plus camera
       +
Hikvision camera
       +
Dahua camera
       ↓
Common timeline
       ↓
Correlated event
       ↓
Investigation
```

### 6. Evidence-linked AI

The AI result isn't just:

> "Person detected."

It becomes:

```text
Person detected
Camera: CP Plus CH-03
Original timestamp: ...
Normalized timestamp: ...
Evidence source: ...
Frame range: ...
Recovery status: ...
Evidence hash: ...
```

That is much more appropriate for a forensic system.

---

# 26. The SIH Strategy

This is the principle I want us to follow throughout the project:

## **Implementation > Novelty**

Not:

> "We need an unprecedented algorithm."

Instead:

> **"We need a working system that solves the NTRO problem better, more consistently, or more practically than existing workflows."**

A judge asking:

> **"What's novel?"**

should get a measured answer.

But a judge asking:

> **"Show me how it works."**

should get a working demonstration.

Therefore:

```text
                 SIH PRIORITY

              ┌───────────────┐
              │ IMPLEMENTATION│
              └───────┬───────┘
                      ↓
              ┌───────────────┐
              │ VALIDATION    │
              └───────┬───────┘
                      ↓
              ┌───────────────┐
              │ TECHNICAL     │
              │ DEFENSIBILITY │
              └───────┬───────┘
                      ↓
              ┌───────────────┐
              │ DIFFERENTIATION│
              └───────┬────────┘
                      ↓
              ┌───────────────┐
              │   NOVELTY     │
              └───────────────┘
```

**Novelty is a bonus. A functioning, validated solution to NTRO's actual problem is the foundation.**

---

# 27. What We Have Now

We can treat this as our **PPT technology baseline**:

| Area                         | Decision                                       |
| ---------------------------- | ---------------------------------------------- |
| Acquisition                  | RAW/DD + E01                                   |
| E01                          | libewf                                         |
| Integrity                    | SHA-256 + MD5                                  |
| Parsing                      | Vendor-specific adapters + hybrid parser       |
| Binary analysis              | Python + low-level tools; C/C++ where needed   |
| Video decoding               | FFmpeg                                         |
| Video processing             | OpenCV                                         |
| Object detection             | YOLO                                           |
| Tracking                     | ByteTrack / BoT-SORT                           |
| Face                         | Detection first                                |
| Motion                       | Classical CV initially                         |
| Timeline                     | Canonical normalized timeline                  |
| Recovery                     | Filesystem → vendor → carving → reconstruction |
| Validation                   | Ground-truth benchmark                         |
| Provenance                   | Hash-linked audit log                          |
| Blockchain                   | Evidence/provenance anchoring                  |
| Backend                      | FastAPI                                        |
| Database                     | SQLite initially                               |
| Scaled DB                    | PostgreSQL                                     |
| Frontend                     | React + TypeScript                             |
| Reporting                    | JSON + PDF                                     |
| Architecture                 | Vendor adapters + normalized evidence model    |
| **Primary project priority** | **Implementation > Novelty**                   |

The uploaded document already establishes most of this baseline; the important updates here are the **more cautious RAW/E01 wording, flexible tracker choice, and blockchain anchoring rather than treating blockchain as an unrelated future feature**. 

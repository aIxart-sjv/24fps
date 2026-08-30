SIH NTRO Requirements

# Requirement 1 — Non-standard forensic acquisition methods

This is the **first NTRO requirement** we should understand.

The uploaded project document breaks it into six practical areas: acquisition through the recorder, direct storage acquisition, forensic imaging, evidence protection, device information capture, and a method for unusual/non-standard acquisition when normal methods fail. 

The key idea:

> **We are not simply copying CCTV footage. We are acquiring the original evidence in a way that lets us prove what we acquired, preserve it, and later reproduce our analysis.**

---

# 1. What NTRO actually wants

### NTRO requirement

We need to understand how to acquire evidence when:

* The DVR/NVR is working normally.
* The recorder can export footage.
* The recorder's native/proprietary format is needed.
* The footage is too large to export normally.
* The required footage has been deleted.
* The DVR/NVR is damaged.
* The DVR/NVR does not boot.
* The recorder's normal export mechanism fails.
* We need the underlying HDD/storage.
* We need a forensic image of that storage.
* We need to preserve the original evidence.
* We need to document exactly what happened during acquisition.
* We encounter a recorder for which no standard acquisition procedure exists.

This is exactly why NTRO includes **"non-standard forensic acquisition methods"** rather than simply "export CCTV video." 

---

# 2. First understand the three different things we can acquire

This distinction is **extremely important for our PPT**.

## A. Normal/native DVR export

Example:

```text
DVR/NVR
   ↓
Select camera
Select date/time
   ↓
Export
   ↓
USB drive
   ↓
Video + proprietary player/metadata
```

This is what a normal CCTV operator does.

Hikvision's own NVR documentation, for example, provides USB HDD/USB flash export by selecting cameras and time ranges. ([Hikvision][1])

CP Plus similarly provides recorder-side backup/export functionality. ([CP PLUS][2])

### Problem

This may not contain everything stored on the recorder.

It can miss:

* deleted footage
* overwritten material
* filesystem information
* storage-level metadata
* system logs
* information outside the selected time range
* data that the recorder's export interface cannot expose.

SWGDE explicitly warns that normal acquisition can lose metadata or multiple-camera information if done incorrectly. ([SWGDE - SWGDE][3])

---

# 3. B. Direct acquisition of the DVR/NVR storage

This is much more important for our project.

Suppose:

```text
DVR
 └── Internal HDD
      ├── recordings
      ├── metadata
      ├── filesystem structures
      ├── logs
      └── deleted/unused storage areas
```

Instead of asking the DVR:

> "Give me this video."

we remove/access the storage and acquire:

> **the storage itself.**

SWGDE says direct hard-drive acquisition becomes appropriate when, for example:

* too much data exists to download on scene;
* output ports do not work;
* logical access isn't sufficient;
* evidence needs protection;
* relevant footage cannot be found;
* footage is deleted/inaccessible;
* other export attempts fail. ([SWGDE - SWGDE][3])

This is exactly where **our forensic system becomes interesting**.

---

# 4. C. Forensic image

Once we have the HDD:

```text
Original DVR HDD
       ↓
Write blocker
       ↓
Forensic imaging system
       ↓
Bit-for-bit image
       ↓
Forensic analysis
```

A **forensic image** is a copy of the storage at the data level, intended to preserve the original evidence for later examination.

The important point:

> **We analyse the copy, not the original whenever practical.**

This prevents our analysis from accidentally changing the evidence.

---

# 5. Recent solution / current best practice

## The most important current source: SWGDE

The **Scientific Working Group on Digital Evidence (SWGDE)** published version **1.4** of its DVR acquisition best-practice document on **21 August 2025**; NIST's OSAC registry lists it as a published forensic standard. ([NIST][4])

[SWGDE — Best Practices for Data Acquisition from Digital Video Recorders](https://www.swgde.org/documents/published-complete-listing/17-v-002-1-4/?utm_source=chatgpt.com)

This is one of the **most important documents for our entire project**.

It says the acquisition objective is to obtain the best available evidence while maintaining integrity. It covers:

* native/proprietary export
* DVR/NVR acquisition
* documentation
* system information
* timestamps
* storage
* firmware
* system logs
* USB export
* network export
* removal of the DVR
* direct HDD acquisition
* chain of custody. ([SWGDE - SWGDE][3])

### Very important finding

SWGDE does **not** say:

> "Always remove the HDD."

Instead:

> **Use the least destructive / most appropriate acquisition method for the situation.**

That means our architecture should support **multiple acquisition paths**.

---

# 6. The acquisition decision tree we should use

Our system should conceptually do this:

```text
             DVR/NVR
                │
                ▼
       Is it functioning?
          /           \
        YES            NO
        │               │
        ▼               ▼
Can native export     Direct storage
be performed?         acquisition
   /       \
 YES        NO
 │           │
 ▼           ▼
Native      Direct HDD/
export      forensic image
 │           │
 └─────┬─────┘
       ▼
Evidence validation
       ↓
Forensic analysis
```

But there's another decision:

```text
Is the required evidence
available through normal export?
        /       \
      YES        NO
       │          │
       ▼          ▼
    Export      Storage-level
                acquisition
```

This is **much better than saying "we always image the HDD."**

---

# 7. How the industry handles this

## Best global industry solution: Magnet WITNESS

The strongest directly relevant commercial solution I found is:

[Magnet WITNESS — official product page](https://www.magnetforensics.com/products/magnet-witness/?utm_source=chatgpt.com)

Magnet WITNESS is the successor to DVR Examiner.

It can:

* acquire native/proprietary video;
* directly acquire data from surveillance/CCTV DVR hard drives;
* recover deleted or partially overwritten video;
* work from forensic images;
* review and analyze video;
* generate auditable reports. ([Magnet Forensics][5])

Magnet says WITNESS evolved from DVR Examiner and combines acquisition, review and analysis in one platform. ([Magnet Forensics][6])

### Why this matters to us

This isn't theoretical.

DME's DVR Examiner was used by **900+ public-safety organizations in more than 80 countries**, according to Magnet's acquisition announcement. ([Business Wire][7])

And there is actual government procurement evidence:

The U.S. government has procured DVR Examiner, including a Department of Justice-related contract record describing direct acquisition of CCTV DVR data. ([CLEATUS][8])

---

# 8. How Magnet actually acquires a DVR HDD

Their older DVR Examiner workflow is extremely useful for us to understand.

### Physical path

```text
DVR HDD
   ↓
Disconnect power/data
   ↓
Connect HDD to write blocker
   ↓
Write blocker → forensic PC
   ↓
DVR Examiner
   ↓
Detect filesystem
   ↓
Analyse
```

Their quick-start guide explicitly describes connecting the DVR hard drive through a write blocker and then selecting either the physical drive or a forensic image. ([Magnet Forensics][9])

[Magnet DVR Examiner Quick Start Guide](https://www.magnetforensics.com/wp-content/uploads/2022/04/DVRExaminer-Quick-Start-Guide-March-2022.pdf?utm_source=chatgpt.com)

---

# 9. What happens if the filesystem isn't recognised?

This is an important real-world detail.

Magnet's workflow doesn't magically support everything.

Its detection process can produce:

```text
Supported filesystem
```

or:

```text
Support pending
```

or:

```text
Unrecognized filesystem
```

The quick-start documentation explicitly describes these outcomes. ([Magnet Forensics][9])

That tells us something important for our architecture:

> **Vendor/filesystem identification must be a separate stage before parsing.**

Which is exactly why our architecture has:

```text
Acquisition
      ↓
Device / filesystem identification
      ↓
Vendor adapter
      ↓
Parsing
```

---

# 10. E01 vs RAW/DD

This is something a judge could easily ask.

### E01

**E01 (Expert Witness Format)** = a forensic image format designed to store a bit-for-bit image plus forensic metadata and optionally compression.

### RAW/DD

**RAW/DD** = a direct byte-for-byte representation of the storage contents without the E01 container's additional metadata structure.

Magnet has actually tested these specifically on DVR drives. ([Magnet Forensics][10])

Their experiment found:

|             |     E01 |  RAW/DD |
| ----------- | ------: | ------: |
| Image time  | ~1h 27m | ~1h 25m |
| Result size | ~434 GB | ~466 GB |
| Search time | ~1h 53m | ~1h 06m |

On that particular DVR HDD, RAW/DD searching was about **42% faster**, while E01 saved about **7% storage**. ([Magnet Forensics][10])

### Why?

DVR disks often contain already-compressed video.

So E01's compression doesn't necessarily save much space.

---

# 11. What should WE use?

### Current recommendation

I would currently design our system to support:

```text
PRIMARY:
RAW/DD
```

for the **internal DVR-analysis workflow**, because:

* it is a direct representation of the source;
* it avoids unnecessary compression/decompression;
* Magnet's DVR-specific experiment found faster searching;
* proprietary DVR filesystems can be searched directly at the sector level.

But:

```text
ALSO SUPPORT:
E01
```

because E01 is widely used in digital forensics and provides useful forensic metadata/interchange capability.

### Therefore:

```text
Original HDD
     ↓
Write blocker
     ↓
RAW/DD forensic image
     │
     ├── analysis
     ├── parsing
     └── recovery

E01
     │
     └── accepted/imported forensic image
```

This is our **current engineering decision**, not an NTRO mandate.

---

# 12. Why a write blocker?

This is one of the easiest judge questions.

### Problem

If you connect a DVR HDD directly to a normal computer:

```text
HDD
 ↓
Windows/Linux
```

the operating system may attempt to:

* mount it;
* write metadata;
* modify filesystem structures;
* create files;
* update timestamps;
* prompt to format an unknown filesystem.

That is dangerous.

### Write blocker

A **write blocker (hardware/software mechanism that allows reading but prevents writes to evidence media)** sits between the evidence HDD and forensic workstation.

```text
DVR HDD
   ↓
WRITE BLOCKER
   ↓
Forensic workstation
```

The workstation can read the drive but cannot intentionally write back to it.

SWGDE includes write blockers among recommended DVR acquisition equipment. ([SWGDE - SWGDE][3])

Magnet also recommends write blockers for DVR hard-drive analysis. ([Magnet Forensics][11])

---

# 13. Very important: cloning is not automatically safe

This is something I want you to remember.

You might think:

> "I'll clone the DVR HDD and put the clone back into the DVR."

That can be dangerous.

Magnet specifically discusses cases where connecting a clone to the DVR can cause the DVR to modify or even format the clone.

They therefore recommend creating a forensic image before experimenting with cloned drives. ([Magnet Forensics][11])

### Correct concept

```text
ORIGINAL
   │
   ├──► FORENSIC IMAGE
   │        │
   │        └──► Analysis
   │
   └──► PRESERVE
```

Not:

```text
Original
 ↓
Clone
 ↓
Experiment directly
 ↓
Hope nothing changed
```

---

# 14. What information should we record before acquisition?

This is **explicitly important in NTRO's requirement**.

SWGDE says to document things such as:

* DVR type
* manufacturer
* model
* serial number
* username/password where applicable
* number of cameras
* connected cameras
* DVR system time
* actual/reference time
* time offset
* earliest recording
* storage capacity
* overwrite settings
* image quality
* FPS
* resolution
* motion/alarm settings
* firmware version
* system logs. ([SWGDE - SWGDE][3])

This maps almost directly to NTRO's requested device information. 

### Therefore our acquisition record should look something like:

```text
CASE ID
Evidence ID
Manufacturer
Model
Serial Number
Firmware
DVR/NVR type
Number of channels
Connected cameras
Storage manufacturer
Storage capacity
System time
Reference time
Calculated clock offset
Earliest recording
Overwrite enabled?
Recording resolution
FPS
Codec
Motion recording?
System logs available?
Acquisition method
Operator
Date/time
Destination
Hash
```

---

# 15. What about the DVR's clock?

This is a subtle but important forensic issue.

Suppose:

```text
Actual time: 14:00:00
DVR time:    13:47:32
```

If we simply trust the DVR timestamp:

> Every event appears 12m 28s early.

SWGDE specifically says:

> **Do not change the DVR clock.**

Instead record the DVR time and calculate the offset against a known reference. ([SWGDE - SWGDE][3])

This will become important later when we reach:

**Timestamp normalization.**

So acquisition already feeds information into later layers.

---

# 16. What happens when normal acquisition fails?

This is the **"non-standard acquisition"** part.

Suppose:

```text
DVR doesn't boot
```

or:

```text
USB export doesn't work
```

or:

```text
Network interface doesn't work
```

or:

```text
Filesystem is unknown
```

or:

```text
HDD is damaged
```

Then we don't simply say:

> "Evidence unavailable."

We develop a controlled alternative acquisition method.

SWGDE's guidance for novel digital devices says to:

1. physically inspect the device;
2. identify hardware/storage;
3. investigate ports/interfaces;
4. identify storage architecture;
5. determine an acquisition technique;
6. test the technique on a duplicate device;
7. document any changes;
8. validate the method. ([SWGDE - SWGDE][12])

This is exactly the methodology we should understand.

---

# 17. Example of non-standard acquisition

Imagine we receive:

```text
Unknown DVR
No working GUI
No usable USB export
Unknown filesystem
```

We could investigate:

```text
Step 1
Photograph device

↓

Step 2
Record manufacturer/model/serial

↓

Step 3
Identify storage

↓

Step 4
Remove HDD safely

↓

Step 5
Write-block HDD

↓

Step 6
Create forensic image

↓

Step 7
Hash image

↓

Step 8
Inspect binary structure

↓

Step 9
Identify filesystem/storage format

↓

Step 10
Develop parser

↓

Step 11
Test parser on duplicate/sample device

↓

Step 12
Compare recovered data against known recordings
```

If the HDD itself is inaccessible, more advanced hardware-level methods could become relevant, but **we should not put JTAG/chip-off into our normal architecture unless testing proves it is necessary**.

---

# 18. Recent research relevant to this requirement

The 2025 Hikvision/Dahua study is important because it demonstrates the complete chain after acquisition:

**binary analysis → proprietary filesystem parsing → manufacturer identification → video reconstruction → validation.**

It tested 27 surveillance HDDs and reported:

* 91.8% recovery rate
* 96.7% temporal accuracy
* 2.4% false-positive rate. ([MDPI][13])

[2025 Hikvision/Dahua forensic recovery paper — MDPI](https://www.mdpi.com/2078-2489/16/11/983?utm_source=chatgpt.com)

This is not primarily an acquisition paper, but it is **very relevant because it demonstrates what happens after the storage has been forensically acquired**.

Then in 2026, research extended forensic recovery into **multi-channel analog DVRs**, where several camera streams are interleaved in storage. ([MDPI][14])

[2026 multi-channel analog DVR forensic recovery paper](https://www.mdpi.com/2078-2489/17/5/493?utm_source=chatgpt.com)

---

# 19. Indian solution — Government

There is strong evidence that India already uses this type of forensic capability.

### NIA

The National Investigation Agency has publicly tendered for **DVR Examiner** licenses.

[NIA tender archive — DVR Examiner procurement](https://nia.gov.in/tender-archive?page=9&utm_source=chatgpt.com)

There is also a Government of India e-procurement record for procurement of **four DVR Examiner units with three-year licenses**. ([Central Public Procurement Portal][15])

This is very useful evidence for our PPT because it proves:

> **Indian law-enforcement agencies already have a real requirement for specialized DVR forensic acquisition.**

### C-DAC

C-DAC has also implemented cyber-forensics laboratory projects where the toolset explicitly includes **DVR analysis**.

[C-DAC — Cyber Forensics Laboratory, Arunachal Pradesh](https://www.cdac.in/index.aspx?id=project_details&projectId=SettingupofCyberForensicsLaboratoryCumTrainingLab%2CStateofArunachalPradesh&utm_source=chatgpt.com)

C-DAC states that CCTV is among the evidence types handled and that the laboratory toolset includes DVR analysis. ([C-DAC][16])

### MHA / forensic laboratories

The Ministry of Home Affairs' forensic-equipment specification explicitly asks for systems capable of:

* processing DVR/analog video;
* decoding proprietary DVR security video;
* video analysis;
* extraction/comparison of frames;
* enhancement;
* demultiplexing;
* forensic processing. ([Ministry of Home Affairs][17])

[MHA — Standard Equipment List for Forensic Laboratories](https://www.mha.gov.in/web/sites/default/files/2022-11/FORENSICSStandardequipmentList_25102022%5B1%5D.pdf?utm_source=chatgpt.com)

---

# 20. Indian private solution

This is where we found something **very important**.

## DRISHTI

An Indian company, Field Forensic, markets **DRISHTI CCTV Forensic Analysis Suite**.

[Field Forensic — DRISHTI CCTV Forensic Analysis Suite](https://www.fieldforensic.com/drishti.html?utm_source=chatgpt.com)

It claims:

* multi-vendor DVR/NVR support
* E01
* Ex01
* DD/RAW
* AFF
* H.264/H.265
* acquisition
* filesystem-aware parsing
* recovery
* fragment analysis
* hash verification
* chain-of-custody documentation
* reporting. ([Field Forensic][18])

**This is extremely important for our project.**

It means we cannot say:

> "India doesn't have a DVR forensic solution."

That would be false.

---

# 21. Another Indian government procurement example

NIELIT's Cyber Forensics Data Center tender specifies DVR Examiner capabilities including:

* original evidence or E01/DD forensic clone
* direct access to recorded data
* password bypass
* recovery of inaccessible/overwritten video
* multiple DVR filesystem support
* automatic filesystem detection. ([NIELIT][19])

[NIELIT — Cyber Forensics Data Center tender specification](https://www.nielit.gov.in/sites/default/files/Kohima/Cyber%20Forensics%20Data%20Center.pdf?utm_source=chatgpt.com)

There is also a Delhi FSL case in which a DVR HDD was forensically imaged using a Logicube Falcon Neo and analysed using DVR Examiner. ([Indian Kanoon][20])

That is **real Indian forensic usage**, not marketing.

---

# 22. Indian private + government picture

So the landscape is:

```text
                 INDIA
                   │
        ┌──────────┼──────────┐
        │          │          │
     GOVERNMENT   PRIVATE   CONSUMER
        │          │          │
        ▼          ▼          ▼
       NIA       DRISHTI    CP Plus
       C-DAC     Field      Hikvision
       FSLs      Forensic   etc.
        │          │          │
        ▼          ▼          ▼
    DVR Examiner  DVR       Normal
                   forensic   export
                   suite
```

This is **exactly why we need to understand the market before claiming novelty.**

---

# 23. Consumer solution

For ordinary users, the acquisition process is much simpler.

### CP Plus

```text
DVR
 ↓
Search
 ↓
Select camera/time
 ↓
USB
 ↓
Export
```

### Hikvision

```text
NVR
 ↓
Search recordings
 ↓
Select camera/time
 ↓
USB HDD/flash
 ↓
Export
```

Hikvision's official manual documents USB backup of selected recordings. ([Hikvision][1])

This is perfectly reasonable for:

> "I need yesterday's footage."

But it is **not equivalent to forensic acquisition**.

---

# 24. Why consumer export is insufficient for NTRO

Imagine a criminal case.

The investigator asks:

> "Show me the footage from 11:30 PM."

Normal export gives:

```text
video.mp4
```

But the forensic investigator may need to answer:

* Was this the original recording?
* Was it exported from the DVR?
* Was it modified?
* What was the DVR clock?
* Was there another camera?
* Was the footage deleted previously?
* Were parts overwritten?
* What filesystem stored it?
* What metadata existed?
* Who acquired it?
* When?
* Was the HDD altered?
* Can the result be reproduced?

That's why NTRO asks for **forensic acquisition**, not just CCTV export.

---

# 25. Acquisition technologies — what each actually does

| Technology           | What it does                                       | Where it fits                      |
| -------------------- | -------------------------------------------------- | ---------------------------------- |
| Native DVR export    | Gets vendor's own exported evidence                | First/normal acquisition           |
| USB export           | Transfers selected recordings                      | Normal working DVR                 |
| Network acquisition  | Retrieves evidence over network                    | When appropriate                   |
| Write blocker        | Prevents writes to original storage                | Direct HDD acquisition             |
| RAW/DD               | Bit-for-bit storage image                          | DVR forensic analysis              |
| E01                  | Forensic image container with metadata/compression | Interoperability/forensic workflow |
| Imaging software     | Reads storage and creates image                    | Acquisition                        |
| Hashing              | Creates digital fingerprint                        | Integrity verification             |
| Hex/binary analysis  | Examines raw storage bytes                         | Unknown/proprietary formats        |
| Vendor parser        | Understands specific storage format                | Post-acquisition                   |
| Chain-of-custody log | Records evidence handling                          | Entire lifecycle                   |

---

# 26. What I would currently choose for OUR system

Based on the evidence so far:

### Acquisition architecture

```text
                 DVR / NVR
                     │
        ┌────────────┴────────────┐
        │                         │
 NORMAL WORKING              FORENSIC CASE
        │                         │
        ▼                         ▼
 Native export              Direct HDD access
        │                         │
        │                    Write blocker
        │                         │
        │                    RAW/DD image
        │                         │
        └────────────┬────────────┘
                     ▼
             Evidence Manifest
                     │
                     ▼
                SHA-256 hash
                     │
                     ▼
             Read-only analysis
```

### Why?

Because we don't want to force every case through the most expensive path.

If a functioning DVR can safely provide native evidence:

> **Acquire it.**

If the case requires storage-level evidence:

> **Image the storage.**

If normal methods fail:

> **Move to controlled non-standard acquisition.**

That matches the real forensic guidance much better than:

> "Always remove the HDD."

---

# 27. What our software should actually receive

I would design the acquisition layer around a common input object:

```text
Evidence Package
│
├── source_type
│   ├── native_export
│   ├── forensic_image
│   └── direct_storage
│
├── original_device
│   ├── manufacturer
│   ├── model
│   ├── serial
│   └── firmware
│
├── acquisition
│   ├── method
│   ├── examiner
│   ├── date/time
│   ├── reference clock
│   └── time offset
│
├── storage
│   ├── HDD model
│   ├── capacity
│   └── image format
│
└── integrity
    ├── SHA-256
    └── MD5
```

Then the next layer doesn't care whether the evidence came from:

```text
CP Plus
```

or:

```text
Hikvision
```

or:

```text
Dahua
```

It receives a **forensically documented evidence package**.

That is the architecture we want to build toward.

---

# 28. What we can actually test ourselves

This is where your hardware becomes useful.

### Experiment 1 — Normal acquisition

Use:

**CP Plus**

```text
Record known event
↓
Export normally
↓
Record:
camera
time
format
metadata
player
```

### Experiment 2 — Storage acquisition

If we can safely and appropriately access the recorder storage:

```text
CP Plus HDD
↓
write-blocked acquisition
↓
RAW/DD
↓
hash
↓
analyse copy
```

### Experiment 3 — Compare

```text
Native export
       VS
Forensic image
```

Ask:

* What information exists in each?
* What metadata is lost?
* Can we identify recordings?
* Can we recover information unavailable through export?

### Experiment 4 — Repeat with TP-Link/Hikvision where permitted

This lets us demonstrate:

> **Same acquisition architecture, different recorder.**

---

# 29. What we should NOT do yet

Do **not** start pulling HDDs out of your home NVR casually.

For learning, we can use controlled test equipment and copies.

For a real forensic workflow, acquisition must be done carefully.

SWGDE explicitly recommends documentation and appropriate preservation procedures, and novel acquisition methods should be tested on duplicate devices before being applied to evidence. ([SWGDE - SWGDE][12])

For our project, **your own equipment should be treated as a controlled laboratory test system**, not as "real evidence."

---

# 30. What is the actual technology choice?

### Current answer

**Acquisition method:**

> **Multi-path acquisition — native export when sufficient; direct storage acquisition when necessary; controlled non-standard acquisition when standard methods fail.**

**Protection:**

> **Hardware write blocker for direct storage acquisition.**

**Forensic image:**

> **RAW/DD as our primary DVR-analysis image candidate, with E01 support.**

**Integrity:**

> **SHA-256 as the primary modern integrity hash; MD5 can be retained because NTRO explicitly asks for both.**

**Analysis:**

> Work only on the acquired copy/image whenever practical.

**Documentation:**

> Capture device identity, storage details, system/reference time, acquisition method, operator and acquisition events.

These are **our current engineering choices**, supported by the standards and industry evidence above. They are not claims that NTRO mandates RAW over E01, for example.

---

# 31. Advantages and disadvantages

| Approach                 | Advantages                                                                   | Disadvantages                                                       |
| ------------------------ | ---------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Native export            | Fast, simple, vendor-supported, preserves native player/format               | May omit deleted/hidden/storage-level evidence                      |
| Network acquisition      | No HDD removal, convenient                                                   | Depends on recorder/network/software; may expose only logical data  |
| Direct HDD               | Full storage-level evidence, enables filesystem/recovery work                | Requires shutdown/removal, specialist equipment, larger data        |
| RAW/DD                   | Simple, exact representation, good DVR analysis performance in Magnet's test | Large storage requirement, little embedded metadata                 |
| E01                      | Forensic metadata, compression, widespread forensic support                  | Processing overhead; compression gains can be small on DVR data     |
| Write blocker            | Protects source from writes                                                  | Hardware cost; some unusual live workflows may not work through one |
| Non-standard acquisition | Can recover evidence when normal methods fail                                | Higher risk; must be validated/documented                           |

---

# 32. What is already solved?

This is important for our project positioning.

**Already mature:**

* Native DVR export
* Forensic imaging
* RAW/DD
* E01
* Write blockers
* Hashing
* DVR direct-drive acquisition
* Basic acquisition documentation

Magnet WITNESS and other commercial tools already implement much of this. ([Magnet Forensics][5])

**Therefore we must NOT say:**

> "Our innovation is forensic acquisition."

That would be weak.

Instead, acquisition is the **foundation that allows the rest of our system to operate correctly**.

---

# 33. What NTRO expects vs what WE should build

| NTRO asks                  | Our interpretation                  |
| -------------------------- | ----------------------------------- |
| Non-standard acquisition   | Multiple acquisition paths          |
| DVR/NVR acquisition        | Native export + direct storage      |
| Direct storage acquisition | Read HDD through write blocker      |
| Forensic image             | RAW/DD + E01 support                |
| Evidence protection        | Original preserved + write-blocking |
| Hashing                    | MD5 + SHA-256                       |
| Verification               | Recalculate/compare hashes          |
| Device information         | Structured acquisition manifest     |
| Non-standard method        | Controlled fallback + validation    |

The uploaded architecture already follows this logic. 

---

# 34. What we need to be able to answer tomorrow

If a judge asks:

### "Why can't you just export the CCTV footage?"

**Answer:**

> Normal export is useful when the recorder is functioning and the required footage is accessible. But it may not provide deleted, inaccessible or storage-level evidence and can lose metadata or other information. Forensic acquisition therefore preserves the native evidence and, when required, acquires the underlying storage. SWGDE specifically recommends direct acquisition when normal export is insufficient. ([SWGDE - SWGDE][3])

### "Why do you need the HDD?"

> Because the HDD can contain the recorder's proprietary storage structures, metadata and potentially deleted or inaccessible recordings that the normal export interface cannot expose.

### "Why a write blocker?"

> To prevent the forensic workstation from writing to the original evidence storage while we acquire it. SWGDE includes write blockers in its recommended DVR acquisition equipment. ([SWGDE - SWGDE][3])

### "Why E01?"

> E01 is a widely used forensic image format with embedded metadata and compression. We will support it for interoperability.

### "Why RAW?"

> DVR storage is often already heavily compressed. Magnet's DVR-specific testing found that RAW/DD produced faster searching in its test while E01 saved only about 7% storage. We therefore consider RAW/DD a strong candidate for our internal DVR analysis path, while retaining E01 compatibility. ([Magnet Forensics][10])

### "What happens if your normal acquisition method fails?"

> We preserve the original, identify the device and storage architecture, develop a controlled acquisition method, test it on a duplicate/sample device, document its effects, and validate the resulting acquisition before using it for forensic analysis. SWGDE provides this type of methodology for novel digital devices. ([SWGDE - SWGDE][12])

### "Does India already have this?"

> **Yes.** Indian agencies use specialized DVR forensic tools. NIA has procured DVR Examiner; C-DAC has established cyber-forensics labs with DVR-analysis capability; Indian forensic specifications explicitly include DVR analysis; and Indian private-sector DRISHTI provides a DVR/NVR forensic suite. ([Central Public Procurement Portal][15])

That last answer is particularly important because **we should never claim that India has no solution.**

---

# 35. The single thing you should remember

If you remember only one sentence for Requirement 1:

> **"We don't simply export CCTV footage; we choose the least invasive acquisition method that preserves the highest-value evidence, and when normal export is insufficient we acquire the underlying DVR/NVR storage through a protected forensic workflow, create a verified forensic image, document the device and acquisition conditions, and only then analyse the evidence."**

That is the **correct mental model** for Requirement 1.

---

## Clean source set — save these

**Recent / standards**

[SWGDE 17-V-002-1.4 — DVR acquisition best practices](https://www.swgde.org/documents/published-complete-listing/17-v-002-1-4/?utm_source=chatgpt.com)

[NIST OSAC — forensic standards registry](https://www.nist.gov/osac/standards-library?utm_source=chatgpt.com)

[SWGDE — Acquisition of novel digital devices](https://www.swgde.org/documents/published-complete-listing/16-f-003-swgde-best-practices-for-the-acquisition-of-data-from-novel-digital-devices/?utm_source=chatgpt.com)

[2025 DVR forensic recovery research — Hikvision/Dahua](https://www.mdpi.com/2078-2489/16/11/983?utm_source=chatgpt.com)

[2026 analog DVR forensic recovery research](https://www.mdpi.com/2078-2489/17/5/493?utm_source=chatgpt.com)

**Global industry**

[Magnet WITNESS](https://www.magnetforensics.com/products/magnet-witness/?utm_source=chatgpt.com)

[Magnet — DVR forensic images: E01 vs DD](https://www.magnetforensics.com/blog/dvr-examiner-forensic-images-for-dvr-analysis-e01-or-dd/?utm_source=chatgpt.com)

[Magnet — DVR Examiner Quick Start Guide](https://www.magnetforensics.com/wp-content/uploads/2022/04/DVRExaminer-Quick-Start-Guide-March-2022.pdf?utm_source=chatgpt.com)

[Magnet — problems with cloned DVR drives](https://www.magnetforensics.com/blog/common-issues-with-traditional-dvr-recovery-using-cloned-hard-drives/?utm_source=chatgpt.com)

**India**

[NIA — DVR Examiner procurement/tender archive](https://nia.gov.in/tender-archive?page=9&utm_source=chatgpt.com)

[Government e-procurement — NIA DVR Examiner procurement](https://eprocure.gov.in/epublish/app?component=%24DirectLink&page=FrontEndViewTender&service=direct&sp=SSowiNRhXJFVLBpUAZD7A%3D%3D&utm_source=chatgpt.com)

[C-DAC — Cyber Forensics Laboratory including DVR Analysis](https://www.cdac.in/index.aspx?id=project_details&projectId=SettingupofCyberForensicsLaboratoryCumTrainingLab%2CStateofArunachalPradesh&utm_source=chatgpt.com)

[MHA — forensic video-analysis equipment specification](https://www.mha.gov.in/web/sites/default/files/2022-11/FORENSICSStandardequipmentList_25102022%5B1%5D.pdf?utm_source=chatgpt.com)

[NIELIT — Cyber Forensics Data Center DVR Examiner specification](https://www.nielit.gov.in/sites/default/files/Kohima/Cyber%20Forensics%20Data%20Center.pdf?utm_source=chatgpt.com)

[Field Forensic — DRISHTI CCTV Forensic Analysis Suite](https://www.fieldforensic.com/drishti.html?utm_source=chatgpt.com)

**Consumer / vendor**

[Hikvision NVR user manual — recording backup/export](https://www.hikvision.com/content/dam/hikvision/products/S000000001/S000000002/S000000007/S000000032/OFR000061/M000000629/User_Manual/Baseline_User-Manual-of-Network-Video-Recorder_71-E-M_V3.4.90_20180124.pdf?utm_source=chatgpt.com)

---

### Requirement 1 verdict for our project

**Understanding:** ✅ Strong

**Existing solution:** ✅ Very mature

**Industry standard:** Native export + protected direct-storage acquisition + forensic imaging

**Best global reference:** Magnet WITNESS / DVR Examiner

**Indian ecosystem:** NIA/C-DAC/FSLs + DRISHTI

**Our current technical choice:** **Native export when sufficient → direct HDD acquisition when necessary → write blocker → RAW/DD primary + E01 compatibility → hash → immutable evidence record → analysis copy**

**What we still need to physically test:** **CP Plus HDD acquisition and imaging workflow**, because that is the point where our theoretical understanding becomes actual project knowledge.

**Novelty:** ❌ **Do not claim acquisition itself as novel.**

**PPT importance:** **VERY HIGH.** This is the foundation of the entire NTRO system.

And this requirement naturally leads into **Requirement 2: support for proprietary filesystems and video formats**, because once we have the forensic image, the next question is: **"Now that we have these raw bytes, how do we understand what the DVR actually stored?"**

[1]: https://www.hikvision.com/content/dam/hikvision/products/S000000001/S000000002/S000000007/S000000032/OFR000061/M000000629/User_Manual/Baseline_User-Manual-of-Network-Video-Recorder_71-E-M_V3.4.90_20180124.pdf?utm_source=chatgpt.com "Network Video Recorder User Manual"
[2]: https://cpplusworld.com/orange-series/img/User_Manual_DVR.pdf?utm_source=chatgpt.com "AI Digital Video Recorder"
[3]: https://www.swgde.org/documents/published-complete-listing/17-v-002-swgde-best-practices-for-data-acquisition-from-digital-video-recorders/ "SWGDE Best Practices for Data Acquisition from Digital Video Recorders - SWGDE"
[4]: https://www.nist.gov/osac/standards-library?utm_source=chatgpt.com "Forensic Science Standards Library | NIST"
[5]: https://www.magnetforensics.com/products/magnet-witness/?utm_source=chatgpt.com "Magnet Witness - Magnet Forensics"
[6]: https://www.magnetforensics.com/blog/introducting-magnet-witness/?utm_source=chatgpt.com "Introducing Magnet Witness - Magnet Forensics"
[7]: https://www.businesswire.com/news/home/20210913005606/en/Magnet-Forensics-Acquires-DME-Forensics-a-Leading-Video-and-Multimedia-Evidence-Solution-Company?utm_source=chatgpt.com "Magnet Forensics Acquires DME Forensics, a Leading Video and Multimedia Evidence Solution Company"
[8]: https://www.cleat.ai/government/contracts/dvr-examiner-syhs?utm_source=chatgpt.com "DVR Examiner - Department Of Justice | CLEATUS"
[9]: https://www.magnetforensics.com/wp-content/uploads/2022/04/DVRExaminer-Quick-Start-Guide-March-2022.pdf?utm_source=chatgpt.com "MAGNET DVR EXAMINER"
[10]: https://www.magnetforensics.com/blog/dvr-examiner-forensic-images-for-dvr-analysis-e01-or-dd/?utm_source=chatgpt.com "Forensic Images for DVR Analysis (E01 or DD) in Magnet Witness"
[11]: https://www.magnetforensics.com/blog/common-issues-with-traditional-dvr-recovery-using-cloned-hard-drives/?utm_source=chatgpt.com "Common Issues with Traditional DVR Recovery Using Cloned Hard Drives"
[12]: https://www.swgde.org/documents/published-complete-listing/16-f-003-swgde-best-practices-for-the-acquisition-of-data-from-novel-digital-devices/?utm_source=chatgpt.com "SWGDE Best Practices for the Acquisition of Data from Novel Digital Devices - SWGDE"
[13]: https://www.mdpi.com/2078-2489/16/11/983?utm_source=chatgpt.com "Automated Forensic Recovery Methodology for Video Evidence from Hikvision and Dahua DVR/NVR Systems"
[14]: https://www.mdpi.com/2078-2489/17/5/493?utm_source=chatgpt.com "Forensic Video Recovery from Multi-Channel Analog DVR Systems: Channel Demultiplexing and Temporal Reconstruction from Interleaved DHAV Streams | MDPI"
[15]: https://eprocure.gov.in/epublish/app?component=%24DirectLink&page=FrontEndViewTender&service=direct&sp=SSowiNRhXJFVLBpUAZctD7A%3D%3D&utm_source=chatgpt.com "ePublishing System, Government of India"
[16]: https://www.cdac.in/index.aspx?id=project_details&projectId=SettingupofCyberForensicsLaboratoryCumTrainingLab%2CStateofArunachalPradesh "
        
      "
[17]: https://www.mha.gov.in/web/sites/default/files/2022-11/FORENSICSStandardequipmentList_25102022%5B1%5D.pdf?utm_source=chatgpt.com "0"
[18]: https://www.fieldforensic.com/drishti.html?utm_source=chatgpt.com "DRISHTI — CCTV Forensic Analysis Suite | Field Forensic"
[19]: https://www.nielit.gov.in/sites/default/files/Kohima/Cyber%20Forensics%20Data%20Center.pdf?utm_source=chatgpt.com "Microsoft Word - TenderDocument"
[20]: https://indiankanoon.org/doc/53222833/?utm_source=chatgpt.com "State vs Nadeem @ Nailli on 22 May, 2025"

# Requirement 2 — Support proprietary file systems and video formats

This is arguably the **technical heart of SIH26150**.

Requirement 1 answered:

> **How do we safely obtain the DVR/NVR evidence?**

Requirement 2 asks:

> **Once we have the raw storage/evidence, how do we understand what is actually inside it?**

NTRO specifically expects the system to deal with **proprietary file systems, proprietary video formats, metadata structures, and different encoding mechanisms across vendors**. Your uploaded research already identifies Dahua and CP Plus as examples, including `.DAV`, proprietary recorder storage, metadata and H.264/H.265 variants. 

---

# 1. The fundamental problem

A normal computer expects something like:

```text
HDD
 ↓
NTFS / FAT32 / exFAT / ext4
 ↓
files
 ↓
MP4 / AVI / JPG
 ↓
video player
```

A DVR can instead look more like:

```text
DVR HDD
│
├── proprietary storage structures
│
├── proprietary indexes
│
├── recording metadata
│
├── video blocks
│
├── logs
│
└── overwritten/free/reused regions
```

There may be **no normal directory structure** that Windows Explorer can understand.

And even if you find video bytes, you may encounter:

```text
H.264
H.265
MJPEG
+
proprietary container
+
vendor metadata
+
custom headers
+
custom timestamps
+
fragmentation
```

NIST's DVR study demonstrates this problem directly: surveillance systems can use proprietary/encrypted formats requiring vendor-specific playback software rather than ordinary video players. ([NIST Publications][1])

---

# 2. The three layers we need to separate

This distinction is extremely important.

## Layer 1 — Storage filesystem

How the DVR organizes its HDD.

Examples:

```text
Hikvision → proprietary storage structures
Dahua → DHFS-family structures
Uniview → UBS
```

## Layer 2 — Recording/container format

How individual recordings are packaged.

Examples:

```text
.DAV
proprietary containers
MP4
raw H.264/H.265
```

## Layer 3 — Codec

How the actual video is compressed.

Examples:

```text
H.264 / AVC
H.265 / HEVC
MJPEG
```

These are **not the same thing**.

A judge asking:

> "Isn't `.DAV` just a codec?"

should be answered:

> **No. A container/storage format and a video codec are different layers. A proprietary DVR container may contain H.264 or H.265 video while also carrying vendor-specific metadata and indexing information.**

Your existing research already makes this distinction for Dahua and CP Plus. 

---

# 3. What actually happens inside a parser?

Let's take a simplified DVR HDD:

```text
Sector 0
Sector 1
Sector 2
...
Sector N
```

Our parser cannot just do:

```python
open("disk.img")
→ find mp4
```

Instead:

```text
RAW forensic image
       ↓
Detect storage structure
       ↓
Identify vendor/filesystem
       ↓
Locate metadata/index structures
       ↓
Locate recording blocks
       ↓
Interpret metadata
       ↓
Locate video
       ↓
Decode/reconstruct stream
       ↓
Associate:
    camera
    timestamp
    duration
    recording type
       ↓
Normalized evidence object
```

That distinction is **the entire reason proprietary filesystem parsing matters**.

---

# 4. Real example: Hikvision

Hikvision is probably the best system for us to study first because there is unusually strong public research.

A publicly available forensic parser documents structures including:

```text
Master Sector
     ↓
HIKBTREE
     ↓
Video data blocks
     ↓
SQLite metadata
     ↓
H.264 video
```

The parser detects the Hikvision filesystem signature:

```text
HIKVISION@HANGZHOU
```

and can parse HIKBTREE structures, system logs and an embedded SQLite database. ([GitHub][2])

[Hikvision DVR forensic parser — GitHub](https://github.com/akira7799/hikvision-dvr-parser?utm_source=chatgpt.com)

Another open-source project parses the proprietary filesystem, indexes video/logs and generates a chronological timeline. ([GitHub][3])

[HIKVISION-DVR-Tool — GitHub](https://github.com/vishwajitsarnobat/HIKVISION-DVR-Tool?utm_source=chatgpt.com)

---

# 5. What the Hikvision filesystem actually looks like

A simplified representation:

```text
Hikvision HDD
│
├── Master Sector
│     └── filesystem information
│
├── HIKBTREE
│     └── recording/block index
│
├── SQLite database
│     ├── file numbers
│     ├── timestamps
│     ├── channels
│     └── recording information
│
├── System Logs
│     ├── alarms
│     ├── operations
│     ├── exceptions
│     └── information
│
└── Video Blocks
      └── H.264 data
```

This is an excellent example of why simply "carving H.264" isn't enough.

If we carve video bytes but don't understand:

* channel
* timestamp
* recording boundaries
* block relationships
* index structures

we may recover video but **not necessarily reconstruct the evidence correctly**.

---

# 6. Firmware versions make this harder

This is one of the most important findings.

The public Hikvision parser says it was developed against a particular firmware/version structure and notes structural differences between versions, including different HIKBTREE entry sizes. ([GitHub][2])

So:

```text
Hikvision Model A
Firmware X
       ↓
Structure A
```

doesn't guarantee:

```text
Hikvision Model B
Firmware Y
       ↓
Structure A
```

This means **"Hikvision supported" is not necessarily a binary yes/no statement.**

Realistically:

```text
Vendor
  ↓
Model
  ↓
Firmware generation
  ↓
Filesystem variant
  ↓
Parser adapter/version
```

This is extremely important for our architecture.

---

# 7. This is where our adapter architecture becomes justified

We should NOT build:

```text
if Hikvision:
    giant Hikvision program

if Dahua:
    giant Dahua program

if CP Plus:
    giant CP Plus program
```

Instead:

```text
                 Common Evidence Engine
                         │
             ┌───────────┼───────────┐
             │           │           │
         Hikvision      Dahua      CP Plus
          Adapter       Adapter     Adapter
             │           │           │
          Parser       Parser      Parser
             │           │           │
             └───────────┼───────────┘
                         ▼
                Normalized Evidence
```

Each adapter knows:

> **How does this particular storage architecture represent evidence?**

The common engine knows:

> **What does our forensic system do with evidence after extraction?**

---

# 8. Dahua — a second major example

The 2025 peer-reviewed study is especially useful here.

It describes:

* Hikvision proprietary filesystem structures
* Dahua DHFS4.1
* binary analysis
* proprietary frame parsing
* manufacturer identification
* timestamp handling
* fragmented stream reconstruction
* validation. ([MDPI][4])

[2025 Hikvision/Dahua forensic recovery paper — MDPI](https://www.mdpi.com/2078-2489/16/11/983?utm_source=chatgpt.com)

The study tested **27 surveillance HDDs** and reported:

* **91.8% recovery**
* **96.7% temporal accuracy**
* **2.4% false positives**
* improved fragmented-stream recovery compared with the commercial tools tested. ([MDPI][4])

### This changes our project positioning.

We absolutely **cannot** say:

> "Nobody knows how to parse Hikvision/Dahua."

That is false.

This has already been demonstrated in both research and tools.

---

# 9. Dahua also demonstrates why container ≠ filesystem

Dahua can have:

```text
DVR HDD
 ↓
proprietary filesystem/storage
 ↓
DHAV/DAV structures
 ↓
H.264/H.265
```

The 2026 research on multi-channel analog DVRs goes even deeper, studying **interleaved DHAV streams**, channel demultiplexing and temporal reconstruction. ([MDPI][5])

[2026 multi-channel analog DVR forensic recovery research — MDPI](https://www.mdpi.com/2078-2489/17/5/493?utm_source=chatgpt.com)

So the actual problem isn't:

> "How do I convert `.DAV` to MP4?"

It's:

> **"How do I correctly reconstruct evidentiary recordings and metadata from a vendor-specific storage architecture?"**

That's a much harder problem.

---

# 10. CP Plus — especially important for us

Your own hardware makes this particularly relevant.

CP Plus documentation confirms that its recorders can export recordings as **DAV or MP4**, with recording parameters including:

* channel
* recording type
* stream type
* start time
* end time
* file size. ([CP PLUS][6])

[CP Plus DVR backup documentation](https://www.cpplusworld.com/orange-series/img/User_Manual_MDVR.pdf?utm_source=chatgpt.com)

But that does **not** mean we have a publicly documented CP Plus forensic filesystem parser.

And this distinction matters:

### Known

CP Plus uses proprietary/embedded recorder storage and supports `.DAV` exports. 

### Known

Indian recovery services claim CP Plus HDD recovery capability. ([Micronics India][7])

### Not established

A peer-reviewed, openly documented CP Plus filesystem reverse-engineering methodology comparable to the Hikvision/Dahua research.

**That remains an area we need to investigate experimentally.**

And because you have a CP Plus system available, this is potentially one of the most useful parts of our project.

---

# 11. Honeywell — very interesting new development

This one is important because **our earlier research has now been overtaken by a 2026 paper**.

A 2026 DFRWS paper specifically analyzes an **undocumented proprietary Honeywell surveillance filesystem**.

The researchers used binary diffing to investigate:

* formatting deletion
* data expiration
* overwrite
* filesystem metadata changes
* on-disk structures
* recovery feasibility. ([ScienceDirect][8])

[2026 Honeywell forensic filesystem research — DFRWS](https://dfrws.org/presentation/forensic-analysis-of-video-data-deletion-and-recovery-in-honeywell-surveillance-file-system/?utm_source=chatgpt.com)

[Honeywell filesystem paper — arXiv](https://arxiv.org/abs/2605.07430?utm_source=chatgpt.com)

This is significant because it demonstrates that **even major commercial DVR forensic ecosystems don't eliminate the need to reverse-engineer new proprietary filesystem variants**.

---

# 12. Uniview — particularly interesting

Uniview officially describes its **UBS (Uniview Block Storage)** technology.

Its documentation explicitly says UBS uses a proprietary algorithm for data mapping and prevents direct access to video data on the HDD. ([Uniview][9])

[Uniview 2025 Product Guide](https://www.uniview.com/res/202502/25/20250225_1940546_CCTV%20Product%20Guide%202025-%20read%20-%2020250224_1006124_168459_0.pdf?utm_source=chatgpt.com)

This is **excellent evidence for the underlying NTRO problem**.

Uniview itself describes:

```text
Traditional:
Application
 ↓
Virtual filesystem
 ↓
FAT/NTFS/EXT/UFS
 ↓
Block device
 ↓
HDD
```

versus its:

```text
Application
 ↓
Block device driver
 ↓
HDD

UBS proprietary mapping
```

So a standard desktop filesystem parser is not enough.

### Our status

**Uniview proprietary storage: VERIFIED.**

**Public forensic reverse-engineering coverage: not established by our search.**

That makes Uniview a particularly interesting candidate for later testing.

---

# 13. TP-Link

TP-Link's VIGI ecosystem has NVRs that store large amounts of continuous surveillance footage and provide searching by:

* date
* event
* channel
* tag

and support local NVR management. ([TP-Link][10])

[TP-Link VIGI surveillance solution documentation](https://static.tp-link.com/configuration-guides/2021/202107/20210713/vigi-surveillance-solution.pdf?utm_source=chatgpt.com)

But we have **not established a public forensic filesystem reverse-engineering study** comparable to Hikvision/Dahua.

This is why your physical TP-Link equipment is useful.

We can potentially investigate:

```text
TP-Link VIGI
      ↓
Acquire storage
      ↓
Binary analysis
      ↓
Identify storage structures
      ↓
Determine recording layout
      ↓
Determine metadata
```

But we should **not claim today that TP-Link has an entirely unknown filesystem** without testing the exact model.

---

# 14. Godrej

Godrej is particularly interesting for the Indian angle.

We have evidence of Godrej DVRs being involved in actual Indian criminal investigations. In one Delhi High Court case, technicians from Godrej removed two DVR hard disks, which were then sealed and seized for investigation. ([Indian Kanoon][11])

That proves:

> Godrej DVR storage can become actual forensic evidence in Indian cases.

But I have **not found a strong public, peer-reviewed Godrej filesystem reverse-engineering study**.

Therefore:

**Godrej filesystem research status: UNKNOWN / research gap.**

Not:

> "Godrej is definitely unsupported."

That distinction matters.

---

# 15. Matrix

For Matrix, we similarly do **not currently have enough evidence to claim a specific proprietary filesystem structure or published forensic parser**.

So:

```text
Matrix
 ├── Indian surveillance manufacturer → YES
 ├── DVR/NVR products → YES
 ├── forensic filesystem research found → NOT ESTABLISHED
 └── exact filesystem architecture → UNKNOWN
```

This is another potential adapter/research target rather than something we should pretend we already understand.

---

# 16. What commercial industry actually does

This is where things get interesting.

## Magnet WITNESS

Magnet WITNESS has the broader workflow:

```text
Acquire
 ↓
Recover
 ↓
Acquire metadata
 ↓
Review
 ↓
Analyze
```

Magnet explicitly describes WITNESS as the evolution of DVR Examiner and says it retains DVR recovery features including acquisition of video/metadata, password bypass and collection of deleted/overwritten data. ([Magnet Forensics][12])

[Magnet WITNESS vs DVR Examiner](https://www.magnetforensics.com/resources/compare-magnet-witness-and-dvr-examiner/?utm_source=chatgpt.com)

But here's a crucial limitation:

**Magnet does not publish a simple complete public list saying "we support every CP Plus model, every Uniview model, every TP-Link model..."**

Instead, its ecosystem has mechanisms for handling unsupported/unrecognized systems.

That means vendor support is **not magically universal**.

---

# 17. Amped is another major industry solution

Amped FIVE supports the majority of proprietary CCTV/DVR video formats and can convert, analyze and report on them. ([Amped Software][13])

[Amped FIVE](https://ampedsoftware.com/five?utm_source=chatgpt.com)

Its proprietary-format engine is continuously updated.

More interestingly, Amped explicitly says users can submit files that it cannot currently process so its team can analyze them and potentially add support. ([Amped Software][13])

That means the industry itself effectively acknowledges:

> **Proprietary-format support is an evolving coverage problem.**

This is extremely relevant to our project.

---

# 18. Amped's architecture is worth copying conceptually

Amped Engine is specifically designed to integrate proprietary CCTV conversion into third-party systems.

It can:

```text
Proprietary CCTV
       ↓
Amped Engine
       ↓
Open-compatible output
       ↓
Forensic / evidence-management system
```

It preserves the original file and generates an output plus a processing report. ([Amped Software][14])

[Amped Engine](https://ampedsoftware.com/engine?utm_source=chatgpt.com)

This reinforces our architecture:

```text
Vendor-specific parsing
          ↓
Common normalized representation
          ↓
Common forensic engine
```

---

# 19. Open-source ecosystem

There is a surprisingly useful open-source ecosystem.

### Hikvision

[Hikvision DVR parser](https://github.com/akira7799/hikvision-dvr-parser?utm_source=chatgpt.com)

[HIKVISION DVR Tool](https://github.com/vishwajitsarnobat/HIKVISION-DVR-Tool?utm_source=chatgpt.com)

### Dahua

Your uploaded research already identified open-source Dahua tools, including DHFS extraction and DVR_Dahua. The broader literature confirms DHFS-specific parsing and recovery work. 

This gives us a very useful implementation philosophy:

> **Don't reinvent a parser if a validated/open parser already exists; build adapters around proven components where licensing and forensic requirements permit.**

---

# 20. Indian solution landscape

India actually has a fairly substantial practical ecosystem.

## DRISHTI

Field Forensic's DRISHTI claims filesystem-specific scanners for:

* Hikvision
* Dahua
* Uniview
* CP Plus
* WFS
* Zhiling
* generic OEMs

and supports:

* Raw
* E01
* Ex01
* AFF
* hash verification
* metadata
* recovery
* fragment analysis
* H.264/H.265. ([Field Forensic][15])

[DRISHTI CCTV Forensic Analysis Suite](https://www.fieldforensic.com/drishti.html?utm_source=chatgpt.com)

**This is a serious existing competitor/reference.**

---

# 21. Indian recovery services

There are also commercial recovery businesses doing this operationally.

Micronics states that DVR recovery requires vendor-specific expertise because each DVR can use its own filesystem/security design, and it lists CP Plus, Dahua and Hikvision among its supported systems. ([Micronics India][7])

[Micronics India — DVR/CCTV recovery](https://www.micronicsindia.com/service/dvr-cctv-data-recovery/?utm_source=chatgpt.com)

Yash Data Recovery lists:

* CP Plus
* Dahua
* Godrej
* Honeywell
* Panasonic
* Samsung

among supported CCTV systems. ([Yash Data Recovery][16])

[Yash Data Recovery — CCTV DVR recovery](https://yashdatarecovery.com/cctv-dvr-recovery.html?utm_source=chatgpt.com)

Another Indian recovery provider lists:

* Hikvision
* Honeywell
* CP Plus
* TP-Link

and other systems. ([Yash Data Recovery Services][17])

This means:

> **The practical recovery problem absolutely exists in India even when public academic documentation is sparse.**

---

# 22. Important distinction: "supports" ≠ "publicly documented"

This is one of the biggest lessons from this research.

Consider CP Plus.

We have:

```text
CP Plus proprietary storage       VERIFIED
CP Plus DAV exports               VERIFIED
Indian recovery services          VERIFIED
Commercial forensic support       CLAIMED/AVAILABLE
Peer-reviewed filesystem study    NOT FOUND
Open forensic parser              NOT ESTABLISHED
```

So we cannot say:

> "Nobody can parse CP Plus."

Nor can we say:

> "CP Plus is completely solved."

The scientifically correct statement is:

> **Practical recovery capability exists, but publicly documented/reproducible filesystem research appears much thinner than for Hikvision/Dahua.**

That distinction could become important for our project.

---

# 23. What about simply using FFmpeg?

This is where people often misunderstand the problem.

FFmpeg is excellent at:

```text
H.264 → decode
H.265 → decode
MP4 → decode
raw H.264 → decode
```

But FFmpeg does **not inherently understand every proprietary DVR filesystem**.

Imagine:

```text
DVR HDD
 ↓
UNKNOWN proprietary filesystem
 ↓
video block at sector 9,384,291
 ↓
custom header
 ↓
H.265
```

FFmpeg can't magically know:

> "Sector 9,384,291 contains Camera 4 footage from 14:32:12."

Our **parser** must first find and reconstruct the stream.

Then FFmpeg can become useful:

```text
Proprietary storage
       ↓
OUR VENDOR ADAPTER
       ↓
Recovered H.264/H.265 stream
       ↓
FFmpeg
       ↓
playable/standardized representation
```

This is why FFmpeg belongs **after parsing**, not as the parser itself.

---

# 24. The same applies to OpenCV

OpenCV can process:

```text
decoded frames
```

It does not solve:

```text
unknown DVR filesystem
```

So:

```text
Filesystem parser
       ↓
Video extractor
       ↓
FFmpeg decoder
       ↓
OpenCV / AI
```

That's the correct layering.

---

# 25. Our proposed architecture after Requirement 2

Now the system is becoming much clearer:

```text
                 FORENSIC IMAGE
                       │
                       ▼
             ┌───────────────────┐
             │ Device Identifier │
             └─────────┬─────────┘
                       │
                       ▼
             Vendor / Model /
             Firmware detection
                       │
                       ▼
            ┌────────────────────┐
            │ Adapter Selection  │
            └─────────┬──────────┘
                      │
        ┌─────────────┼──────────────┐
        ▼             ▼              ▼
    Hikvision       Dahua         CP Plus
     Adapter        Adapter        Adapter
        │             │              │
        ▼             ▼              ▼
   FS parser       FS parser      FS parser
        │             │              │
        └─────────────┼──────────────┘
                      ▼
              Normalized metadata
                      │
                      ▼
              Video block extraction
                      │
                      ▼
                H.264 / H.265
                      │
                      ▼
                  FFmpeg
                      │
                      ▼
             Standardized evidence
```

This is **much stronger** than:

> "We'll use FFmpeg to convert DVR files."

---

# 26. What exactly should the normalized output contain?

Every vendor adapter should eventually produce something like:

```text
Recording
│
├── evidence_id
├── vendor
├── model
├── firmware
├── channel
├── recording_type
├── start_timestamp
├── end_timestamp
├── timestamp_source
├── storage_offset
├── storage_length
├── codec
├── resolution
├── frame_rate
├── stream_type
├── source_hash
├── recovery_status
└── validation_status
```

Then downstream components don't care whether the source was:

```text
Hikvision
```

or:

```text
Dahua
```

or:

```text
CP Plus
```

They see the same normalized object.

---

# 27. What happens when the parser doesn't understand something?

This is where the architecture must be honest.

```text
Identify vendor
      ↓
Known adapter?
   /        \
 YES         NO
 │            │
 ▼            ▼
Parse       Unknown
             │
             ▼
      Binary inspection
             │
             ▼
      Candidate structures
             │
             ▼
      Controlled research
             │
             ▼
      New adapter/version
             │
             ▼
          Validate
```

**Do not silently guess.**

If the system doesn't understand the filesystem:

> **UNKNOWN / UNSUPPORTED**

is a valid forensic result.

A wrong reconstruction is much worse than an incomplete reconstruction.

---

# 28. How do we validate a parser?

This is extremely important.

Suppose we claim:

> "Our CP Plus parser recovered 95 recordings."

How do we know they're correct?

We need controlled test evidence.

### Test setup

```text
Camera
 ↓
Known event
 ↓
DVR records
 ↓
Record exact wall-clock event
 ↓
Acquire HDD
 ↓
Parse
```

Then compare:

```text
Expected:
Camera 3
10:32:14
Person enters frame

Recovered:
Camera 3
10:32:14
Person enters frame
```

Repeat across:

* channels
* timestamps
* recording modes
* firmware versions
* fragmented recordings
* overwritten blocks
* intentionally deleted footage.

This is why your actual hardware is so valuable.

---

# 29. Your hardware gives us a realistic research path

You have:

```text
CP Plus
████████████████
5 cameras

TP-Link
████████
2 cameras

Hikvision
████████
college access

Xiaomi
████
friend
```

But there is an important caveat:

**Camera ≠ DVR filesystem.**

A TP-Link IP camera by itself gives us camera/video data.

For filesystem research, what we really want is:

> **the storage device used by the NVR/DVR recording that camera footage is written to.**

If your two TP-Link cameras record into a TP-Link VIGI NVR, that's excellent.

If they only record to SD/cloud, that's a different experiment.

Likewise, your five CP Plus cameras are valuable because the **CP Plus recorder/storage** is what we need for proprietary filesystem research.

---

# 30. What is actually novel here?

We have to be extremely strict because we've already had this discussion.

### NOT novel:

❌ Parsing Hikvision.

❌ Parsing Dahua.

❌ Supporting H.264/H.265.

❌ Converting proprietary CCTV files.

❌ Recovering DVR video.

❌ Building a DVR parser.

❌ Detecting a proprietary filesystem.

All of those already exist in some form. ([MDPI][4])

### Potentially interesting:

**A reusable multi-vendor forensic architecture where vendor-specific filesystem adapters feed a common evidence model, with measurable adaptation cost and validation across genuinely different proprietary storage architectures.**

But even this should **not yet be called novel** until we finish the full existing-solution comparison.

That's the right level of caution.

---

# 31. The strongest current observation

The market appears to have two extremes:

### Open research

Very deep work on individual vendors:

```text
Hikvision
Dahua
Honeywell
```

### Commercial tools

Broad vendor coverage:

```text
Magnet
Amped
DRISHTI
recovery laboratories
```

### The gap

What remains difficult is not:

> "Can anyone parse a DVR?"

Clearly yes.

It is:

> **"Can we create a transparent, reproducible, validated, adapter-based architecture that can be extended to poorly documented Indian-market recorder variants without turning into a collection of opaque vendor-specific hacks?"**

That is where our project should investigate.

---

# 32. Requirement 2 — current status

| Question                                     | Finding                                  |
| -------------------------------------------- | ---------------------------------------- |
| Proprietary DVR filesystems exist?           | ✅ Definitely                             |
| Hikvision solved?                            | ✅ Strongly studied                       |
| Dahua solved?                                | ✅ Strongly studied                       |
| Honeywell solved?                            | 🟡 Recent 2026 research exists           |
| CP Plus practical recovery exists?           | ✅ Yes                                    |
| CP Plus public filesystem research?          | 🟡 Much weaker / not established         |
| Uniview proprietary storage?                 | ✅ Officially confirmed                   |
| Uniview public forensic filesystem research? | 🟡 Not established                       |
| TP-Link proprietary recorder storage?        | 🟡 Need exact model/storage architecture |
| Godrej forensic filesystem research?         | 🟡 Not established                       |
| Matrix forensic filesystem research?         | 🟡 Not established                       |
| Commercial global solutions?                 | ✅ Magnet, Amped                          |
| Indian forensic solution?                    | ✅ DRISHTI + recovery ecosystem           |
| Open-source parsers?                         | ✅ Hikvision/Dahua etc.                   |
| Generic filesystem parser solves this?       | ❌ No                                     |
| FFmpeg alone solves this?                    | ❌ No                                     |

---

# 33. Our current technical decision

**Filesystem layer**

> Vendor/model/firmware-specific adapters.

**Detection**

> Signature + structural analysis, not filename extension alone.

**Parsing**

> Interpret filesystem structures and metadata first.

**Extraction**

> Recover referenced video blocks.

**Decoding**

> FFmpeg or equivalent after stream extraction.

**Normalization**

> Convert vendor-specific metadata into one common forensic evidence schema.

**Validation**

> Compare filesystem metadata, recovered video, timestamps and known test events.

**Unknown format**

> Flag it rather than inventing an interpretation.

---

# 34. The judge questions you should now be able to answer

### "Why can't you just use NTFS?"

> Because many DVR/NVRs don't store recordings using a conventional desktop filesystem. They use vendor-specific embedded storage structures.

### "Why can't you just search for H.264?"

> Because finding H.264 byte sequences doesn't necessarily tell us which camera, timestamp, recording segment or filesystem record they belong to. We need the vendor's storage structures and metadata to reconstruct evidence correctly.

### "Why do you need vendor adapters?"

> Different manufacturers organize their storage, metadata and recording structures differently. An adapter isolates those differences while allowing the downstream forensic engine to operate on one normalized evidence model.

### "Why not FFmpeg?"

> FFmpeg handles video decoding and conversion; it doesn't replace the vendor-specific filesystem/parser layer needed to locate and reconstruct recordings from raw DVR storage.

### "Does this already exist?"

> **Yes, partially and extensively.** Commercial systems such as Magnet WITNESS and Amped provide broad proprietary-format support, while research and open-source tools deeply cover specific vendors such as Hikvision and Dahua. Our research therefore treats multi-vendor support as an engineering and validation problem rather than claiming that proprietary-format parsing itself is new. ([Magnet Forensics][12])

### "Then why are you building it?"

This is the answer we should eventually refine:

> **"Because NTRO is asking for one standardized forensic workflow across multiple proprietary recorder ecosystems, while existing solutions range from deep single-vendor research to broad commercial products with evolving proprietary-format coverage. Our approach is to build a transparent adapter-based architecture and validate it experimentally across multiple recorder architectures rather than claiming that proprietary DVR parsing itself is new."**

That is defensible.

---

# 35. Requirement 2 verdict

**Understanding:** ✅ **Strong**

**Existing technology:** ✅ **Very mature for some vendors**

**Hikvision:** ✅ Deeply solved

**Dahua:** ✅ Deeply solved

**Honeywell:** 🟡 Recently researched

**CP Plus:** 🟡 Practical recovery exists; public reproducible filesystem research is much thinner

**Uniview:** 🟡 Proprietary storage definitely exists; forensic reverse-engineering coverage not established

**TP-Link/Godrej/Matrix:** 🟡 Need exact-model/physical research before making strong claims

**Global industry:** 🥇 **Magnet WITNESS + Amped ecosystem**

**Indian industry:** 🥇 **DRISHTI + specialized recovery labs**

**What we should build:** **adapter → parser → normalized evidence model → common forensic engine**

**What we should NOT claim as novel:** proprietary filesystem parsing itself.

**Most valuable experiment for us:** **CP Plus raw HDD → identify structure → map metadata → locate recordings → extract known test footage → validate against known events.**

And there is a very useful progression now:

> **Requirement 1 = How do we safely acquire the bytes?**
> **Requirement 2 = How do we understand those bytes?**
> **Requirement 3 should naturally be = How do we extract video + metadata from those understood structures?**

That is where we should go next.

[1]: https://nvlpubs.nist.gov/nistpubs/ir/2017/NIST.IR.8172.pdf?utm_source=chatgpt.com "Assessment of Closed Circuit Television Digital Video Recording and Export Technologies"
[2]: https://github.com/akira7799/hikvision-dvr-parser?utm_source=chatgpt.com "GitHub - akira7799/hikvision-dvr-parser: Forensic python scripted parser for HIKVision formatted DVR drives · GitHub"
[3]: https://github.com/vishwajitsarnobat/HIKVISION-DVR-Tool?utm_source=chatgpt.com "GitHub - vishwajitsarnobat/HIKVISION-DVR-Tool · GitHub"
[4]: https://www.mdpi.com/2078-2489/16/11/983?utm_source=chatgpt.com "Automated Forensic Recovery Methodology for Video Evidence from Hikvision and Dahua DVR/NVR Systems"
[5]: https://www.mdpi.com/2078-2489/17/5/493?utm_source=chatgpt.com "Forensic Video Recovery from Multi-Channel Analog DVR Systems: Channel Demultiplexing and Temporal Reconstruction from Interleaved DHAV Streams | MDPI"
[6]: https://www.cpplusworld.com/orange-series/img/User_Manual_MDVR.pdf?utm_source=chatgpt.com "Figure 5-20 Backup (1)"
[7]: https://www.micronicsindia.com/service/dvr-cctv-data-recovery/?utm_source=chatgpt.com "DVR/CCTV Data Recovery Services by Micronics"
[8]: https://www.sciencedirect.com/science/article/pii/S2666281726000739?utm_source=chatgpt.com "Forensic analysis of video data deletion and recovery in Honeywell surveillance file system - ScienceDirect"
[9]: https://cms-unv.uniview.com/res/202412/27/20241227_1929723_UNV%202025%20CCTV%20Product%20Guide_1006124_168459_0.pdf?utm_source=chatgpt.com "UNIVIEW
PRODUCT GUIDE 2025"
[10]: https://static.tp-link.com/configuration-guides/2021/202107/20210713/vigi-surveillance-solution.pdf?utm_source=chatgpt.com "Security Never Shuts Down"
[11]: https://indiankanoon.org/doc/109355525/?utm_source=chatgpt.com "Anil Kumar vs State on 26 June, 2023"
[12]: https://www.magnetforensics.com/resources/compare-magnet-witness-and-dvr-examiner/?utm_source=chatgpt.com "Compare Magnet Witness and DVR Examiner - Magnet Forensics"
[13]: https://ampedsoftware.com/five?utm_source=chatgpt.com "Amped FIVE | Forensic Image and Video Enhancement"
[14]: https://ampedsoftware.com/engine?utm_source=chatgpt.com "Amped Engine | Integrated CCTV/DVR Converter"
[15]: https://www.fieldforensic.com/drishti.html?utm_source=chatgpt.com "DRISHTI — CCTV Forensic Analysis Suite | Field Forensic"
[16]: https://yashdatarecovery.com/cctv-dvr-recovery.html?utm_source=chatgpt.com "CCTV DVR Data Recovery Services | Yash Data Recovery"
[17]: https://www.yashdatarecovery.in/cctv-dvr-data-recovery?utm_source=chatgpt.com "CCTV OR DVR DATA RECOVERY | Yash Data Recovery"

# Requirement 3 — Extract videos and metadata

We now move to the next NTRO requirement:

> **After acquiring the DVR/NVR storage and understanding its proprietary structure, extract the actual recordings and the information that describes those recordings.**

This sounds simple.

It is not.

NTRO is asking us to recover **two different kinds of evidence**:

1. **The actual video/audio data**
2. **The metadata that explains what that video represents**

The second part is easy to underestimate.

A recovered video without reliable:

* camera/channel
* date/time
* duration
* recording type
* storage location
* source information

can be much less useful for an investigation.

NIST specifically identifies date, time and camera information as important CCTV evidence metadata and has developed a standardized export profile around preserving it. ([NIST Services][1])

---

# 1. Where this sits in our architecture

So far:

```text
DVR/NVR
   │
   ▼
1. Acquisition
   │
   ▼
Forensic image
   │
   ▼
2. Identify proprietary structure
   │
   ▼
Vendor-specific filesystem
   │
   ▼
3. Extract video + metadata
   │
   ▼
Normalized evidence
```

Then later:

```text
Normalized evidence
       │
       ├──► Recovery
       ├──► Timeline
       ├──► Event correlation
       ├──► AI analysis
       ├──► Validation
       └──► Report
```

This is why **extraction must happen before AI**.

---

# 2. What exactly are we extracting?

Imagine a CP Plus recording.

The storage may contain something equivalent to:

```text
Recording #18432

Channel:       04
Start:         2026-08-25 18:42:13
End:           2026-08-25 18:47:51
Recording:     Motion
Stream:        Main
Codec:         H.265
Resolution:    1920 × 1080
Frame rate:    25 fps
Storage offset: 0x18A34000
Size:          842 MB
```

And separately:

```text
VIDEO DATA
│
├── frame
├── frame
├── frame
├── frame
└── ...
```

Our job is to connect those two.

---

# 3. The output we actually want

Not merely:

```text
video1.mp4
video2.mp4
video3.mp4
```

We want:

```text
Evidence Record
│
├── Video
│     └── recovered_video.mp4
│
├── Source
│     ├── Vendor
│     ├── Model
│     ├── Firmware
│     └── Evidence ID
│
├── Camera
│     └── Channel 04
│
├── Time
│     ├── Start
│     ├── End
│     └── Clock source/offset
│
├── Recording
│     ├── Motion
│     ├── Continuous
│     └── Alarm
│
├── Technical
│     ├── Codec
│     ├── Resolution
│     ├── FPS
│     └── Stream type
│
└── Integrity
      ├── SHA-256
      └── MD5
```

That becomes the **normalized evidence object** used by the rest of our system.

---

# 4. First major problem — proprietary video containers

Suppose the recorder gives us:

```text
something.DAV
```

We cannot assume:

> `.DAV = ordinary video file`

It may contain:

```text
Proprietary container
│
├── vendor header
├── metadata
├── video stream
├── timestamps
└── proprietary information
```

The actual encoded video might be:

```text
H.264
```

or:

```text
H.265
```

The container and codec are different things.

This distinction is why **conversion software and filesystem parsers are separate components**.

---

# 5. The ideal extraction pipeline

Our system should conceptually perform:

```text
Raw DVR storage
      │
      ▼
Vendor filesystem parser
      │
      ▼
Recording index
      │
      ├───────────────┐
      ▼               ▼
Metadata          Video blocks
      │               │
      │               ▼
      │          Reconstruct stream
      │               │
      │               ▼
      │         H.264 / H.265
      │               │
      │               ▼
      │            Decoder
      │               │
      └───────┬───────┘
              ▼
       Evidence Record
              │
              ▼
     Standardized output
```

---

# 6. Recent research — 2025 Hikvision/Dahua

The strongest recent research we found is the **2025 peer-reviewed Hikvision/Dahua forensic recovery study**.

[https://www.mdpi.com/2078-2489/16/11/983](https://www.mdpi.com/2078-2489/16/11/983?utm_source=chatgpt.com)

The researchers perform:

```text
Raw disk
 ↓
Manufacturer identification
 ↓
Binary parsing
 ↓
Frame extraction
 ↓
Timestamp extraction
 ↓
Frame validation
 ↓
Video reconstruction
 ↓
MP4 conversion
```

They explicitly preserve temporal metadata during extraction and reconstruct fragmented streams using timestamp and frame-number information. ([MDPI][2])

They tested **27 surveillance hard drives** and reported:

* 91.8% overall recovery
* 96.7% temporal accuracy
* 2.4% false-positive rate
* 87.2% fragmented-stream recovery compared with 82.4% for commercial tools in their test. ([MDPI][2])

### Why this matters to us

This gives us a concrete example of how **raw storage → frames → metadata → reconstructed video** can actually be implemented.

---

# 7. What the parser extracts

For Hikvision, the open-source parser provides an excellent practical example.

[https://github.com/akira7799/hikvision-dvr-parser](https://github.com/akira7799/hikvision-dvr-parser?utm_source=chatgpt.com)

The parser can extract:

* H.264 video
* system logs
* HIKBTREE structures
* SQLite recording metadata
* channel information
* start/end timestamps
* recording sizes
* storage offsets.

It also cross-references HIKBTREE information against the embedded SQLite database for forensic verification. ([GitHub][3])

That last point is particularly important.

---

# 8. Why cross-reference metadata?

Imagine:

```text
HIKBTREE says:

Camera 04
18:42:13
Block = X
```

but:

```text
SQLite says:

Camera 04
18:42:14
Block = X
```

We now have a discrepancy.

A forensic tool should not silently pick one.

It should record:

```text
Metadata conflict detected.
Source A: HIKBTREE
Source B: SQLite
Status: REQUIRES VALIDATION
```

This is much more defensible.

---

# 9. This gives us an important design principle

### Never trust one metadata source blindly.

Instead:

```text
Filesystem metadata
       +
Embedded database
       +
Video frame metadata
       +
Known recorder clock
       +
Recovered stream
       ↓
Cross-validation
```

This is much stronger than:

```text
Read timestamp
↓
Trust timestamp
```

---

# 10. Example: extracting an individual frame

The 2025 research describes a Hikvision frame structure with fields such as:

```text
Magic number
Frame type
Frame size
Timestamp
Channel ID
Video payload
```

The parser can therefore conceptually do:

```text
Read bytes
    ↓
Find magic number
    ↓
Read frame header
    ↓
Read size
    ↓
Read timestamp
    ↓
Read channel
    ↓
Read payload
    ↓
Validate
    ↓
Store frame record
```

Result:

```text
Frame #18342

Disk offset: 0x1A73F000
Channel: 4
Timestamp: 18:42:13.421
Size: 38,214 bytes
Type: video
Validity: VALID
```

The actual field structure is vendor-specific. The 2025 research describes this type of frame-level parsing for Hikvision and DHFS/Dahua. ([MDPI][2])

---

# 11. Dahua is more complicated

The 2025 research describes Dahua's DHFS4.1 frame structure with:

```text
DHAV
 ↓
frame information
 ↓
channel
 ↓
frame number
 ↓
frame size
 ↓
timestamp
 ↓
milliseconds
 ↓
video payload
 ↓
footer / validation information
```

The 2026 research goes further for multi-channel analog DVRs.

[https://www.mdpi.com/2078-2489/17/5/493](https://www.mdpi.com/2078-2489/17/5/493?utm_source=chatgpt.com)

It describes a reusable pipeline:

```text
Vendor-specific frame parser
             ↓
Channel demultiplexing
             ↓
Temporal reconstruction
             ↓
Validation
             ↓
Output
```

The important architectural insight is:

> **Only the first stage is vendor-specific.**

The later stages can operate on a normalized frame representation. ([MDPI][4])

That is **very relevant to our architecture**.

---

# 12. This is how our common frame model should work

Each vendor parser produces:

```text
FrameRecord
│
├── vendor
├── channel
├── frame_number
├── timestamp
├── timestamp_precision
├── frame_type
├── storage_offset
├── payload_offset
├── payload_size
├── codec
└── validation_status
```

Then the common engine can do:

```text
FrameRecord
   ↓
Sort by channel
   ↓
Sort by timestamp
   ↓
Detect gaps
   ↓
Detect overlaps
   ↓
Reconstruct sequence
   ↓
Decode
```

So we don't write separate timeline/reconstruction algorithms for every vendor.

---

# 13. What about ordinary exported video?

This is where NIST becomes very useful.

NIST investigated CCTV interoperability and found that different systems commonly produce proprietary formats, creating conversion problems, quality loss and metadata loss. ([NIST Publications][5])

NIST's recommended CCTV export profile specifies:

* MP4 container
* H.264 video
* standard date/time metadata
* system clock offset metadata. ([NIST Services][1])

[https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=922342](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=922342&utm_source=chatgpt.com)

This gives us an important output strategy:

### Preserve original

```text
original.DAV
```

### Create standardized derivative

```text
evidence_001.mp4
```

### Keep metadata

```text
evidence_001.json
```

### Keep provenance

```text
conversion_report.json
```

### Hash everything

```text
SHA-256
MD5
```

**Never replace the original with the converted file.**

---

# 14. Why not just convert everything to MP4 immediately?

Because conversion can potentially:

* change the container
* lose proprietary metadata
* change timestamps
* alter encoding
* introduce transcoding
* change frame representation
* make later verification harder.

NIST specifically identified conversion-related quality and metadata-loss problems in CCTV workflows. ([NIST Publications][5])

Therefore:

```text
ORIGINAL
   │
   ├──────────────► PRESERVE
   │
   └──► CONVERSION
           │
           ▼
       REVIEW COPY
```

Not:

```text
ORIGINAL
 ↓
MP4
 ↓
delete original
```

---

# 15. Best global industry solution — Amped

For this particular requirement, **Amped is arguably the clearest industry reference**.

### Amped DVRConv

[https://ampedsoftware.com/dvrconv](https://ampedsoftware.com/dvrconv?utm_source=chatgpt.com)

It is specifically designed to convert proprietary CCTV/DVR files into open-compatible formats.

It supports:

* proprietary CCTV formats
* batch conversion
* stream-copy conversion
* transcoding when required
* output codec/format selection
* splitting/merging
* playback-speed correction.

Most importantly, Amped says its conversion engine:

> preserves the original stream and separates standard encoding information from proprietary metadata.

That is exactly the design problem we're dealing with. ([Amped Software][6])

---

# 16. Amped Engine

This is even more relevant.

[https://ampedsoftware.com/engine](https://ampedsoftware.com/engine?utm_source=chatgpt.com)

Amped Engine is a command-line conversion engine designed to integrate into other forensic systems.

Its architecture is basically:

```text
Third-party forensic system
          │
          ▼
      Amped Engine
          │
          ▼
Proprietary CCTV format
          │
          ▼
Open-compatible output
```

It:

* preserves the original file;
* generates an open-format playable version;
* maintains an audit trail;
* produces a report describing the processing. ([Amped Software][7])

### This is a major industry lesson for us.

We should **not try to make our entire forensic platform responsible for every possible video codec/container**.

Our architecture should separate:

**forensic parsing**

from

**video conversion/decoding**.

---

# 17. Amped's biggest lesson: proprietary formats keep changing

This is particularly relevant to our SIH project.

Amped's 2026 update describes new proprietary formats and timestamp/audio-stream variations being added to its system. It specifically mentions Panasonic N3R/N3A and says new formats are discovered partly through files submitted by users. ([Amped Software Blog][8])

Their 2023 update similarly notes that CCTV manufacturers continually change formats, players and devices. ([Amped Software Blog][9])

So:

```text
Vendor supported today
        ≠
Every future firmware/model supported
```

This is one of the strongest arguments for our **adapter architecture**.

---

# 18. Amped also demonstrates an important fallback

When a format isn't supported:

```text
Unknown file
      ↓
Submit sample
      ↓
Forensic format analysis
      ↓
Decoder/demuxer development
      ↓
Future support
```

Amped explicitly provides a mechanism for users to submit unsupported files for analysis and potential support in later releases. ([Amped Software][6])

This means **unknown formats are a real industry problem**, not a theoretical one.

---

# 19. Best global forensic-analysis reference — Amped FIVE

[https://ampedsoftware.com/five](https://ampedsoftware.com/five?utm_source=chatgpt.com)

Amped FIVE goes beyond conversion.

Its workflow includes:

```text
Convert
   ↓
Analyze
   ↓
Select relevant frames
   ↓
Restore/enhance
   ↓
Redact/annotate
   ↓
Export
   ↓
Report
```

It can inspect:

* metadata
* video format
* codec characteristics
* frame-level encoding
* compression information.

It also produces reports containing the processing steps, settings and algorithms used. ([Amped Software][10])

This becomes important later when we discuss **reporting and forensic reproducibility**.

---

# 20. Magnet WITNESS

Magnet's platform is more focused on the broader DVR/NVR forensic workflow.

[https://www.magnetforensics.com/products/magnet-witness/](https://www.magnetforensics.com/products/magnet-witness/?utm_source=chatgpt.com)

It combines:

* acquisition
* proprietary DVR recovery
* video/metadata collection
* review
* analysis
* reporting.

The important lesson is:

> **Extraction is not an isolated utility. It is part of the complete forensic case workflow.**

---

# 21. Indian solution — DRISHTI

The strongest Indian reference we currently have is:

[https://www.fieldforensic.com/drishti.html](https://www.fieldforensic.com/drishti.html?utm_source=chatgpt.com)

DRISHTI claims:

* filesystem-aware parsing
* Hikvision
* Dahua
* Uniview
* CP Plus
* generic OEM support
* H.264/H.265
* preview
* recovery
* fragment analysis
* channel verification
* segment export
* report generation.

It also supports forensic image inputs such as:

* RAW/DD
* E01
* Ex01
* AFF.

([Field Forensic][11])

This is important because **we cannot claim India has no solution for extraction.**

---

# 22. Indian government / forensic ecosystem

The broader Indian forensic ecosystem already expects CCTV evidence to be extracted and analyzed in specialized environments.

C-DAC's cyber-forensics laboratory project explicitly includes DVR analysis as part of its forensic toolset.

[https://www.cdac.in/index.aspx?id=project_details&projectId=SettingupofCyberForensicsLaboratoryCumTrainingLab%2CStateofArunachalPradesh](https://www.cdac.in/index.aspx?id=project_details&projectId=SettingupofCyberForensicsLaboratoryCumTrainingLab%2CStateofArunachalPradesh&utm_source=chatgpt.com)

And the MHA forensic equipment specification includes requirements around proprietary DVR video decoding and forensic video processing.

[https://www.mha.gov.in/web/sites/default/files/2022-11/FORENSICSStandardequipmentList_25102022%5B1%5D.pdf](https://www.mha.gov.in/web/sites/default/files/2022-11/FORENSICSStandardequipmentList_25102022%5B1%5D.pdf?utm_source=chatgpt.com)

So the requirement is **very real in India**.

---

# 23. The most important difference: extraction vs conversion

These words can get mixed up.

### Extraction

Finding the recording inside the storage:

```text
HDD
 ↓
filesystem
 ↓
recording blocks
 ↓
video payload
```

### Conversion

Making that video playable/usable in a standard format:

```text
.DAV / proprietary stream
 ↓
conversion/demuxing
 ↓
MP4/H.264/etc.
```

### Decoding

Turning compressed video into frames:

```text
H.264
 ↓
decoder
 ↓
frames
```

These are three different operations.

---

# 24. Our architecture should therefore be

```text
             RAW DVR IMAGE
                    │
                    ▼
          Vendor Filesystem Parser
                    │
                    ▼
            Recording Metadata
                    │
                    ▼
            Video Block Locator
                    │
                    ▼
          Stream Reconstruction
                    │
                    ▼
        ┌──────────────────────┐
        │ Proprietary Stream   │
        │ H.264 / H.265 / etc. │
        └──────────┬───────────┘
                   │
                   ▼
             Demux / Decoder
                   │
                   ▼
             Standard Frames
                   │
                   ▼
             MP4 / Review Copy
```

And alongside it:

```text
Filesystem Metadata
       │
       ├── Camera
       ├── Timestamp
       ├── Recording type
       ├── Duration
       └── Storage location
                │
                ▼
        Normalized Metadata
```

Then combine:

```text
VIDEO
 +
METADATA
 +
SOURCE
 +
HASH
 +
PROVENANCE
 ↓
FORENSIC EVIDENCE OBJECT
```

---

# 25. What should our normalized evidence object look like?

I would currently use something similar to:

```json
{
  "evidence_id": "CASE001-EV0042",
  "source_vendor": "CP Plus",
  "source_model": "UNKNOWN",
  "source_firmware": "UNKNOWN",
  "channel": 4,
  "recording_type": "motion",
  "start_time": "2026-08-25T18:42:13",
  "end_time": "2026-08-25T18:47:51",
  "timestamp_source": "filesystem_metadata",
  "codec": "H.265",
  "resolution": "1920x1080",
  "frame_rate": 25,
  "storage_offset": 412345678,
  "storage_length": 842000000,
  "recovery_status": "VALID",
  "validation_status": "VERIFIED"
}
```

The exact fields will change as we research more vendors.

But this is the **conceptual model** we need.

---

# 26. What happens when metadata is missing?

This is a very important forensic scenario.

Suppose:

```text
Video found:
YES

Timestamp:
NO

Camera:
NO

Filesystem index:
CORRUPTED
```

We shouldn't invent:

```text
Camera = 4
Time = 18:42
```

Instead:

```text
Camera: UNKNOWN
Timestamp: UNKNOWN
Metadata confidence: LOW
```

Then we can attempt secondary reconstruction:

```text
Frame timestamp
+
neighboring blocks
+
filesystem structures
+
known recording sequence
+
other cameras
```

If reconstruction succeeds:

```text
Timestamp:
RECONSTRUCTED

Confidence:
HIGH/MEDIUM/LOW
```

This becomes extremely important later when we reach **recovery and timeline reconstruction**.

---

# 27. What happens if video is fragmented?

Suppose storage contains:

```text
A B C D E F G H
```

but the actual recording was stored:

```text
A C D H B G F E
```

because the storage was fragmented.

We can't simply read sequentially.

We need:

```text
Metadata/index
       +
frame numbers
       +
timestamps
       +
storage offsets
       ↓
reconstruction
```

The 2025 research specifically addresses fragmented streams through temporal sequencing and reports improved fragmented recovery. ([MDPI][2])

This will become a major part of **Requirement 4 — deleted/damaged/fragmented recovery**.

---

# 28. What happens if the recording is partially corrupted?

Suppose:

```text
Frame 1  ✓
Frame 2  ✓
Frame 3  ✓
Frame 4  ✗
Frame 5  ✓
Frame 6  ✓
```

We should not necessarily discard the entire recording.

Instead:

```text
Frame 1 → valid
Frame 2 → valid
Frame 3 → valid
Frame 4 → corrupted
Frame 5 → valid
Frame 6 → valid
```

Then produce:

```text
Recovered video
+
corruption map
+
validation information
```

This is much more useful for forensic work.

---

# 29. Why the output should preserve the original stream where possible

This is a very strong industry practice.

Amped says its conversion technology preserves the original stream and separates standard encoding information from proprietary metadata to avoid errors and lost frames. ([Amped Software][6])

Therefore our preferred conversion strategy should be:

### First choice

**Demux / stream copy**

Meaning:

> Extract the existing encoded video without re-encoding it.

```text
Original H.265
      ↓
Extract
      ↓
H.265 in standard container
```

### Second choice

**Transcode**

Only if necessary:

```text
Unsupported proprietary stream
       ↓
Decode
       ↓
Encode
       ↓
standard format
```

But transcoding can alter the data representation.

Therefore we should preserve:

```text
ORIGINAL
+
LOSSLESS/STREAM-COPIED DERIVATIVE
+
TRANSCODED DERIVATIVE (if needed)
```

---

# 30. What technology should we use?

We haven't finished the entire technology study yet, but based on the evidence for this requirement:

### Filesystem parsing

**Vendor-specific parser/adapters**

Not FFmpeg.

### Video demuxing/conversion

**FFmpeg or equivalent**

Potentially after the proprietary layer has extracted the stream.

### Metadata

A structured internal schema:

```text
JSON / database
```

### Output

Prefer:

```text
Original proprietary evidence
+
standard review copy
+
machine-readable metadata
```

### Validation

Cross-check:

```text
filesystem
↔ metadata
↔ frame timestamps
↔ reconstructed video
```

---

# 31. What NOT to do

### ❌ Don't do this

```text
.DAV
 ↓
rename
 ↓
.mp4
```

Changing the extension doesn't convert the data.

### ❌ Don't do this

```text
DVR image
 ↓
find H.264
 ↓
dump bytes
 ↓
call it recovered evidence
```

You may lose channel/time/recording relationships.

### ❌ Don't do this

```text
Original
 ↓
transcode
 ↓
delete original
```

You lose the source evidence.

### ❌ Don't do this

```text
Metadata says 18:42
 ↓
assume correct
```

Metadata itself may be corrupted.

---

# 32. What we should actually test on your equipment

This is where the project becomes real.

## Experiment A — CP Plus normal export

Record a controlled event:

```text
Camera 1
Person walks past
18:00:00
```

Export using the normal CP Plus procedure.

Record:

* file extension
* player
* codec
* metadata
* timestamp
* channel
* resolution
* frame rate.

---

## Experiment B — Inspect the exported file

Use:

```text
FFprobe / MediaInfo
```

to determine:

```text
Container
Codec
Resolution
FPS
Duration
Streams
Metadata
```

We need to research and choose the exact tool later.

---

## Experiment C — Compare native export with storage

If we can safely obtain a controlled forensic image:

```text
Native export
       VS
Raw storage
```

Ask:

> What information exists only in the storage?

This is an excellent demonstration.

---

## Experiment D — TP-Link

If your TP-Link cameras record to a VIGI NVR/storage:

```text
Record known event
 ↓
Export
 ↓
Inspect
 ↓
Identify storage architecture
```

This could give us a second vendor.

---

## Experiment E — Hikvision

With college permission:

```text
Known test recording
 ↓
Native export
 ↓
Inspect metadata
 ↓
Compare against public Hikvision research
```

If storage access is permitted:

```text
HDD image
 ↓
existing open-source parser
 ↓
compare recovered result
```

This would be extremely valuable because we'd be testing a **published methodology against our own controlled hardware**.

---

# 33. What we can put in the PPT

Don't say:

> "Our system converts all DVR videos to MP4."

Too simplistic.

Say something closer to:

> **"The platform first parses vendor-specific storage structures to recover recordings and associated metadata. The recovered stream is then reconstructed and, where necessary, converted into a standardized review format while preserving the original evidence and recording the conversion process."**

That is technically much stronger.

---

# 34. Judge question preparation

### "Why not just convert everything to MP4?"

> Because conversion alone doesn't solve proprietary storage parsing or evidence extraction. We first need to locate and reconstruct the recording and preserve its associated metadata. A standardized review copy is generated only after the original evidence has been preserved.

---

### "Why do you need metadata?"

> Metadata connects the video to its investigative context — camera, time, recording type, stream and source. Without it, a playable video may not be enough to establish when or where the recording originated.

NIST specifically identifies camera, date and time information as important CCTV evidence metadata. ([NIST Services][1])

---

### "Why not just use FFmpeg?"

> FFmpeg is useful for decoding and processing standard video streams, but it does not replace the vendor-specific filesystem and metadata parsing required to locate recordings in proprietary DVR storage.

---

### "Why preserve the original?"

> Because the converted video is a derivative. The original proprietary evidence must remain available so the extraction and conversion can be independently checked.

Amped's forensic conversion workflow similarly preserves the original while producing an open-format derivative and processing report. ([Amped Software][7])

---

### "What if the metadata is wrong?"

> We don't blindly trust it. We cross-check metadata from the filesystem, embedded databases, frame timestamps and other available evidence. Conflicts are recorded rather than silently corrected.

---

### "What if the video is fragmented?"

> We reconstruct it using vendor-specific storage information and frame-level information such as timestamps and frame numbers. This is already demonstrated in recent Hikvision/Dahua forensic research. ([MDPI][2])

---

### "Does this already exist?"

> **Yes.** Commercial systems such as Amped and Magnet already perform substantial proprietary CCTV extraction and conversion. Open-source and academic work also covers individual vendors. Our project therefore should not claim that video extraction itself is novel. Our focus is the standardized multi-vendor forensic workflow and experimentally validated integration across different recorder ecosystems.

---

# 35. Requirement 3 — current verdict

| Question                                           | Current finding                                         |
| -------------------------------------------------- | ------------------------------------------------------- |
| Video extraction already exists?                   | ✅ Mature                                                |
| Proprietary-to-standard conversion exists?         | ✅ Mature                                                |
| Metadata extraction exists?                        | ✅ Mature                                                |
| Hikvision extraction                               | ✅ Strong research + open-source                         |
| Dahua extraction                                   | ✅ Strong research                                       |
| Commercial global solutions                        | 🥇 Amped + Magnet                                       |
| Indian solution                                    | 🥇 DRISHTI                                              |
| Standardized CCTV export research                  | 🥇 NIST                                                 |
| FFmpeg useful?                                     | ✅ Yes, after proprietary extraction                     |
| FFmpeg solves DVR parsing?                         | ❌ No                                                    |
| Metadata can be blindly trusted?                   | ❌ No                                                    |
| Original should be replaced by MP4?                | ❌ Absolutely not                                        |
| Stream-copy preferable to unnecessary transcoding? | ✅ Strong current direction                              |
| Extraction itself novel?                           | ❌ No                                                    |
| Normalized cross-vendor evidence model             | 🟡 Proposed direction; novelty still needs verification |

---

# 36. The three requirements now form one coherent system

We can now explain the first three stages very cleanly:

```text
                    DVR / NVR
                       │
                       ▼
┌─────────────────────────────────────────┐
│ 1. FORENSIC ACQUISITION                 │
│                                         │
│ Safely obtain the evidence              │
│ Native export / direct storage / image  │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│ 2. PROPRIETARY FORMAT PARSING           │
│                                         │
│ Understand the vendor's storage system  │
│ Identify filesystem / structures        │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│ 3. VIDEO + METADATA EXTRACTION           │
│                                         │
│ Find recordings                          │
│ Recover metadata                         │
│ Reconstruct streams                      │
│ Produce standardized review copy         │
└──────────────────┬──────────────────────┘
                   │
                   ▼
             NORMALIZED
          FORENSIC EVIDENCE
                   │
                   ▼
             REQUIREMENT 4
          RECOVERY / RECONSTRUCTION
```

And **Requirement 4 is where things get substantially harder**:

> What if the recording is deleted, partially overwritten, fragmented or damaged?

That is where we'll go next.

---

## Clean source set for Requirement 3

**Recent research**

[2025 Hikvision/Dahua forensic recovery paper — https://www.mdpi.com/2078-2489/16/11/983](https://www.mdpi.com/2078-2489/16/11/983?utm_source=chatgpt.com)

[2026 multi-channel analog DVR recovery paper — https://www.mdpi.com/2078-2489/17/5/493](https://www.mdpi.com/2078-2489/17/5/493?utm_source=chatgpt.com)

**Open source**

[Hikvision DVR parser — https://github.com/akira7799/hikvision-dvr-parser](https://github.com/akira7799/hikvision-dvr-parser?utm_source=chatgpt.com)

**Standards / government**

[NIST CCTV export profile — https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=922342](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=922342&utm_source=chatgpt.com)

[NIST CCTV recording/export assessment — https://nvlpubs.nist.gov/nistpubs/ir/2017/NIST.IR.8172.pdf](https://nvlpubs.nist.gov/nistpubs/ir/2017/NIST.IR.8172.pdf?utm_source=chatgpt.com)

[SWGDE DVR acquisition guidance — https://www.swgde.org/wp-content/uploads/2024/12/SWGDE-17-V-002-1.3-Best-Practices-for-Data-Acquisition-from-Digital-Video-Recorders.pdf](https://www.swgde.org/wp-content/uploads/2024/12/SWGDE-17-V-002-1.3-Best-Practices-for-Data-Acquisition-from-Digital-Video-Recorders.pdf?utm_source=chatgpt.com)

**Global industry**

[Amped DVRConv — https://ampedsoftware.com/dvrconv](https://ampedsoftware.com/dvrconv?utm_source=chatgpt.com)

[Amped Engine — https://ampedsoftware.com/engine](https://ampedsoftware.com/engine?utm_source=chatgpt.com)

[Amped FIVE — https://ampedsoftware.com/five](https://ampedsoftware.com/five?utm_source=chatgpt.com)

[Magnet WITNESS — https://www.magnetforensics.com/products/magnet-witness/](https://www.magnetforensics.com/products/magnet-witness/?utm_source=chatgpt.com)

**India**

[DRISHTI CCTV Forensic Analysis Suite — https://www.fieldforensic.com/drishti.html](https://www.fieldforensic.com/drishti.html?utm_source=chatgpt.com)

[C-DAC Cyber Forensics Laboratory — https://www.cdac.in/index.aspx?id=project_details&projectId=SettingupofCyberForensicsLaboratoryCumTrainingLab%2CStateofArunachalPradesh](https://www.cdac.in/index.aspx?id=project_details&projectId=SettingupofCyberForensicsLaboratoryCumTrainingLab%2CStateofArunachalPradesh&utm_source=chatgpt.com)

[MHA forensic equipment specifications — https://www.mha.gov.in/web/sites/default/files/2022-11/FORENSICSStandardequipmentList_25102022%5B1%5D.pdf](https://www.mha.gov.in/web/sites/default/files/2022-11/FORENSICSStandardequipmentList_25102022%5B1%5D.pdf?utm_source=chatgpt.com)

**Current engineering conclusion:**
**Parse first → extract metadata + video → reconstruct → validate → generate standardized derivative → preserve original.**

**Do not claim extraction as novel.**

The next requirement is the one where we need to go particularly deep: **deleted, damaged and fragmented recording recovery**. That is where the difference between *"we can play CCTV"* and *"we can perform forensic reconstruction"* becomes very clear.

[1]: https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=922342&utm_source=chatgpt.com "Recommendation: Closed Circuit Television (CCTV) Digital Video Export Profile – Level 0"
[2]: https://www.mdpi.com/2078-2489/16/11/983?utm_source=chatgpt.com "Automated Forensic Recovery Methodology for Video Evidence from Hikvision and Dahua DVR/NVR Systems"
[3]: https://github.com/akira7799/hikvision-dvr-parser?utm_source=chatgpt.com "GitHub - akira7799/hikvision-dvr-parser: Forensic python scripted parser for HIKVision formatted DVR drives · GitHub"
[4]: https://www.mdpi.com/2078-2489/17/5/493?utm_source=chatgpt.com "Forensic Video Recovery from Multi-Channel Analog DVR Systems: Channel Demultiplexing and Temporal Reconstruction from Interleaved DHAV Streams | MDPI"
[5]: https://nvlpubs.nist.gov/nistpubs/ir/2017/NIST.IR.8172.pdf?utm_source=chatgpt.com "Assessment of Closed Circuit Television Digital Video Recording and Export Technologies"
[6]: https://ampedsoftware.com/dvrconv?utm_source=chatgpt.com "Amped DVRConv | Automatic CCTV/DVR Converter"
[7]: https://ampedsoftware.com/engine?utm_source=chatgpt.com "Amped Engine | Integrated CCTV/DVR Converter"
[8]: https://blog.ampedsoftware.com/2026/05/20/amped-five-update-40823?utm_source=chatgpt.com "Amped FIVE Update: New Formats, Assistant Automation, More"
[9]: https://blog.ampedsoftware.com/2023/06/28/amped-dvrconv-update-29658-new-format-variations-and-timestamp-support?utm_source=chatgpt.com "Amped DVRConv Update 29658: New Format Variations and Timestamp Support"
[10]: https://ampedsoftware.com/five?utm_source=chatgpt.com "Amped FIVE | Forensic Image and Video Enhancement"
[11]: https://www.fieldforensic.com/drishti.html?utm_source=chatgpt.com "DRISHTI — CCTV Forensic Analysis Suite | Field Forensic"

## Requirement 4 — Deleted, damaged and fragmented recording recovery

This is the part where **SIH26150 becomes much more than a CCTV video player**.

NTRO explicitly asks for:

* deleted recording recovery
* damaged recording recovery
* fragmented recording recovery
* recovery from proprietary storage
* reliable analysis of recovered evidence

The important distinction is:

> **"The DVR cannot see the video anymore" does not necessarily mean "the video bytes are gone."**

But there is also a hard limit:

> **If the underlying data has actually been overwritten, software cannot magically recover the original video.**

That distinction needs to be part of our design and our PPT.

---

# 1. What exactly are we trying to recover?

Imagine a DVR hard drive.

Normal situation:

```text
Storage
│
├── Recording A
├── Recording B
├── Recording C
├── Recording D
└── Recording E
```

The DVR maintains some kind of index/metadata telling it where these recordings are.

Now somebody deletes Recording C.

The DVR may effectively do:

```text
INDEX

A → location 100
B → location 200
C → DELETE
D → location 400
E → location 500
```

But the actual bytes may still be sitting on the disk:

```text
DISK

A A A A
B B B B
C C C C    ← still physically present
D D D D
E E E E
```

So:

```text
Deleted from DVR interface
          ≠
Immediately erased from disk
```

Magnet documents this exact principle: DVR deletion often removes the index/accessibility information while the underlying video remains until overwritten. ([Magnet Forensics][1])

---

# 2. There are actually several different recovery problems

We should **not call everything "deleted recovery."**

## Case A — Inaccessible/de-indexed video

The video still exists.

The DVR simply no longer knows where it is.

```text
Metadata/index
      X
      │
      ▼
Video bytes
      ✓
```

This is comparatively easier.

---

## Case B — Deleted but partially overwritten

Some of the recording survives.

```text
Original:

AAAA BBBB CCCC DDDD EEEE

After overwrite:

AAAA BBBB XXXX XXXX EEEE
```

We may recover:

```text
AAAA BBBB ???? ???? EEEE
```

Some useful footage may remain.

Magnet's documentation distinguishes ordinary inaccessible recovery from **frame-level inaccessible recovery**, where very small surviving portions can be recovered even after partial overwriting. ([Magnet Forensics][1])

---

## Case C — Fragmented recording

The recording exists, but its pieces are scattered.

```text
Disk:

A
X
C
Y
B
Z
D
```

The correct sequence is:

```text
A → B → C → D
```

not the physical order on the disk.

We need to reconstruct the sequence.

---

## Case D — Damaged recording

The video exists, but some structures are damaged.

For example:

```text
Frame 1 ✓
Frame 2 ✓
Frame 3 ✓
Frame 4 ✗
Frame 5 ✓
Frame 6 ✓
```

The question becomes:

> Can we recover the valid portions without pretending the damaged portion is valid?

---

## Case E — Actually overwritten

This is the hard boundary.

```text
OLD VIDEO
   ↓
OVERWRITTEN
   ↓
NEW DATA
```

If the old information has genuinely been replaced, **we cannot promise recovery**.

Our system should report:

```text
Recovery status:
NOT RECOVERABLE

Reason:
Underlying data overwritten / unavailable
```

That is much more defensible than claiming "AI recovery."

---

# 3. What the real forensic workflow looks like

The process should be:

```text
Forensic image
      ↓
Identify vendor/filesystem
      ↓
Read filesystem structures
      ↓
Find active recordings
      ↓
Find inaccessible/deleted structures
      ↓
Locate surviving video blocks
      ↓
Validate candidate blocks
      ↓
Reconstruct frame sequence
      ↓
Reconstruct timestamps
      ↓
Decode
      ↓
Validate recovered video
      ↓
Assign recovery confidence
      ↓
Export recovered evidence
```

---

# 4. Recovery method 1 — filesystem-based recovery

This is the preferred method when possible.

Suppose the filesystem contains:

```text
Recording index

ID 1842
Channel 4
Start 18:00
End 18:15
Blocks:
100
101
102
103
104
```

After deletion:

```text
Recording index entry removed
```

But the blocks remain.

We can potentially locate them using:

* filesystem structures
* allocation information
* timestamps
* frame numbers
* recording headers
* storage offsets.

This is much stronger than blindly searching the entire disk.

---

# 5. Recovery method 2 — file carving

**File carving** = searching raw storage for recognizable patterns that indicate the beginning/end of a file or data structure.

Example:

```text
Raw disk
────────────────────────────

00 00 FF A1 ...
...
DHAV
...
video data
...
dhav
...
```

We recognize:

```text
DHAV
```

as a potential Dahua frame signature.

Then:

```text
candidate frame
      ↓
check size
      ↓
check timestamp
      ↓
check frame type
      ↓
check footer/signature
      ↓
VALID / INVALID
```

This is useful when the filesystem index is missing or damaged.

But it has a major problem:

> **Finding bytes that look like video does not prove that they belong to the required recording.**

That is why validation matters.

---

# 6. SWGDE already documents advanced DVR recovery

SWGDE has a dedicated document for advanced recovery from security DVRs containing H.264 data.

[SWGDE — Advanced Data Recovery from Security DVRs containing H.264](https://www.swgde.org/documents/published-complete-listing/15-v-002-swgde-proposed-techniques-for-advanced-data-recovery-from-security-digital-video-recorders-containing-h-264-data/?utm_source=chatgpt.com)

It explicitly covers situations where normal DVR retrieval methods fail.

It describes the need for:

* forensic clones/images
* write blockers
* hex editors
* video playback/decoding software
* header extraction
* demultiplexing
* sequencing
* frame recovery.

It also explicitly warns that these advanced techniques are for trained personnel and that traditional recovery methods should be attempted first. ([SWGDE - SWGDE][2])

---

# 7. Important: H.264 recovery is not just "find H.264"

The SWGDE guidance makes this very clear.

After recovering raw H.264 data, additional processing may be needed for:

* aspect ratio
* frame rate
* sequencing
* demultiplexing
* audio
* metadata.

And not all video necessarily can be recovered. ([SWGDE - SWGDE][2])

So our pipeline cannot be:

```text
find H.264
↓
MP4
```

It needs to be:

```text
find candidate data
↓
validate
↓
sequence
↓
demultiplex
↓
reconstruct
↓
decode
↓
validate output
```

---

# 8. Recent research — Hikvision + Dahua

The strongest recent paper we found remains:

[2025 Automated Forensic Recovery Methodology — Hikvision/Dahua](https://www.mdpi.com/2078-2489/16/11/983?utm_source=chatgpt.com)

The study tested **27 surveillance hard drives**.

Reported results included:

* **91.8% recovery rate**
* **96.7% temporal accuracy**
* **2.4% false-positive rate**
* **87.2% fragmented-stream recovery**

The methodology uses:

* direct binary analysis
* proprietary filesystem analysis
* frame-based parsing
* adaptive temporal sequencing
* dual-signature validation
* automatic manufacturer identification
* automated reconstruction. ([MDPI][3])

This is extremely useful for us because it gives us an actual research-backed methodology rather than an imaginary architecture.

---

# 9. What is adaptive temporal sequencing?

Suppose we find:

```text
Frame A
18:00:01

Frame B
18:00:02

Frame C
18:00:03

Frame D
18:05:40
```

Is D part of the same recording?

Not necessarily.

A fixed rule like:

```text
gap > 2 sec = new recording
```

may fail.

Different systems and circumstances produce different gaps.

The 2025 research therefore uses **adaptive temporal sequencing**.

In simple terms:

> The system adjusts how much timestamp discontinuity it will tolerate when deciding whether recovered frames belong to the same sequence.

This is much better than blindly sorting frames by timestamp.

---

# 10. What is dual-signature validation?

Suppose we find:

```text
Candidate frame
```

We don't immediately accept it.

We can check multiple properties.

For example:

```text
Header signature ✓
Footer signature ✓
Frame size ✓
Timestamp plausible ✓
Frame type valid ✓
```

Only then:

```text
VALID FRAME
```

This reduces false positives.

The 2025 Hikvision/Dahua study specifically uses header/footer validation for DHFS frames. ([Directory of Open Access Journals][4])

---

# 11. This is exactly where our "recovery confidence" idea becomes useful

Instead of:

```text
Recovered = YES
```

we should produce something like:

```text
Recovery result

Frames recovered: 94.3%
Metadata recovered: 88.1%
Timestamp continuity: 96.7%
Frame validation: 99.1%

Overall confidence:
HIGH
```

Or:

```text
Recovery result

Frames recovered: 41%
Metadata recovered: 12%
Timestamp continuity: poor

Overall confidence:
LOW
```

### Important:

The exact formula for such a score is **our proposed design**.

We should not claim that the industry universally uses our proposed formula.

---

# 12. New research finding — analog DVRs

This is especially interesting for SIH26150.

A **2026 paper** studied forensic recovery from multi-channel analog Dahua DVRs.

[2026 Analog DVR forensic recovery paper](https://www.mdpi.com/2078-2489/17/5/493?utm_source=chatgpt.com)

The problem is fundamentally different from a typical IP NVR.

An analog DVR may take multiple camera feeds:

```text
Camera 1 ─┐
Camera 2 ─┤
Camera 3 ─┤
Camera 4 ─┤
           ▼
       DVR encoder
           │
           ▼
    Interleaved stream
```

The disk might therefore contain:

```text
Cam1
Cam2
Cam3
Cam4
Cam1
Cam2
Cam3
Cam4
...
```

The system has to **demultiplex** the channels.

The study reports a methodology for separating interleaved DHAV frames and reconstructing individual camera streams. It tested 14 analog Dahua DVR hard drives and reported 92.3% recovery, 91.3% temporal accuracy and 97.5% channel-separation accuracy. ([MDPI][5])

---

# 13. This is a very important lesson for our project

"Multi-vendor" is not only:

```text
CP Plus
Hikvision
Dahua
TP-Link
...
```

It can also mean:

```text
IP NVR
vs
analog DVR
vs
hybrid DVR
```

because their storage architecture can be fundamentally different.

The 2026 study explicitly identifies this difference between IP-based systems and analog multi-channel DVRs. ([MDPI][5])

That makes our vendor adapter concept more meaningful.

---

# 14. New 2026 Honeywell research

There is another very relevant recent paper:

[2026 Honeywell surveillance filesystem deletion/recovery study](https://www.sciencedirect.com/science/article/pii/S2666281726000739?utm_source=chatgpt.com)

This study examined an **undocumented Honeywell proprietary filesystem**.

It investigated three deletion mechanisms:

1. formatting-based deletion
2. data expiration
3. overwrite

The researchers used binary-diffing techniques to examine changes in filesystem metadata and on-disk structures and demonstrated recovery after deletion. ([ScienceDirect][6])

### This is extremely relevant to NTRO.

NTRO specifically names **Honeywell**.

And this research demonstrates that:

> **Different vendors can implement fundamentally different deletion mechanisms.**

Therefore we cannot create one universal recovery algorithm and expect it to work everywhere.

---

# 15. This strengthens the vendor-adapter architecture

Instead of:

```text
Universal recovery algorithm
```

we should have:

```text
                  Recovery Engine
                       ▲
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   CP Plus adapter  Hikvision      Dahua
        │              │              │
   vendor rules     vendor rules   vendor rules
        │              │              │
        └──────────────┼──────────────┘
                       │
                 Normalized frames
                       │
                       ▼
              Common reconstruction
```

The vendor-specific layer understands:

* filesystem
* headers
* indexes
* frame structure
* deletion behaviour
* storage organisation.

The common layer handles:

* reconstruction
* validation
* timeline
* evidence objects
* reporting.

That is a much more sensible architecture.

---

# 16. Best global industry solution

## Magnet WITNESS

Magnet's current product is **Magnet WITNESS**, the successor to DVR Examiner.

[Magnet WITNESS — official product page](https://www.magnetforensics.com/products/magnet-witness/?utm_source=chatgpt.com)

Magnet states that WITNESS retains DVR Examiner's capabilities including:

* video acquisition
* metadata acquisition
* deleted/overwritten data collection
* password bypass
* video review
* analysis. ([Magnet Forensics][7])

Its predecessor's documentation explicitly describes:

```text
inaccessible recovery
frame-level inaccessible recovery
deleted video
partially overwritten video
```

([Magnet Forensics][1])

So **deleted recovery absolutely already exists commercially**.

We cannot claim it as our innovation.

---

# 17. What Magnet does differently from simple file carving

A commercial forensic system isn't simply:

```text
scan HDD for H.264
```

It understands supported DVR filesystems.

For example:

```text
DVR HDD
 ↓
filesystem detection
 ↓
filesystem-specific processing
 ↓
recording discovery
 ↓
deleted/inaccessible recovery
 ↓
video + metadata
 ↓
review/report
```

This is exactly why our project needs **filesystem-specific adapters**.

---

# 18. The biggest limitation of commercial recovery

There is a critical point here.

Magnet itself explains that recovery capabilities depend on the filesystem.

Its recovery interface tells the examiner which capabilities are supported for the detected filesystem. ([Magnet Forensics][1])

So:

```text
Supported filesystem
        ↓
strong recovery capability
```

but:

```text
Unknown filesystem
        ↓
limited/no specialized recovery
```

This is important because SIH asks for a much broader vendor set.

---

# 19. The real engineering problem isn't "can we recover deleted video?"

That has already been solved.

The stronger question is:

> **Can we build a repeatable framework that can learn/implement recovery methods for different proprietary DVR ecosystems and then represent the recovered evidence in one standardized workflow?**

That is much closer to what SIH is asking.

---

# 20. Indian situation

We have to be careful here.

There are Indian forensic products and capabilities.

For example:

[DRISHTI — Field Forensic DVR forensic suite](https://www.fieldforensic.com/drishti.html?utm_source=chatgpt.com)

And Indian government forensic ecosystems include DVR analysis capabilities.

Therefore:

❌ "India has no DVR recovery."

is not defensible.

A better statement is:

> **India already has forensic DVR-analysis capabilities, but the publicly documented breadth of vendor coverage, proprietary filesystem research, validation methodology and standardized cross-vendor architecture is not clearly established from public sources.**

That is a statement we can investigate further rather than exaggerate.

---

# 21. What should our recovery engine actually output?

Not just:

```text
recovered.mp4
```

Something more like:

```text
RecoveryResult
│
├── Source evidence ID
│
├── Vendor
│
├── Device/model
│
├── Recovery method
│
├── Source storage offsets
│
├── Recovered frames
│
├── Missing frames
│
├── Timestamp range
│
├── Camera/channel
│
├── Fragment count
│
├── Corruption indicators
│
├── Validation results
│
├── Recovery confidence
│
└── Hashes
```

Then:

```text
RecoveryResult
      ↓
Normalized Evidence
```

---

# 22. Validation is more important than recovery

Suppose our system says:

> "Recovered 10,000 frames."

That doesn't prove anything.

We need to ask:

```text
Are these actually video frames?
       ↓
Do their sizes make sense?
       ↓
Are timestamps plausible?
       ↓
Are frame numbers consistent?
       ↓
Do frames belong to the same channel?
       ↓
Can the stream decode?
       ↓
Does the reconstructed video make sense?
```

Only then:

```text
Recovered + validated
```

---

# 23. A useful validation hierarchy

I would currently design it as:

### Level 1 — Structural validation

```text
Header
Size
Footer
Magic bytes
```

### Level 2 — Semantic validation

```text
Timestamp
Channel
Frame type
Frame number
```

### Level 3 — Sequence validation

```text
Ordering
Continuity
Fragment relationships
```

### Level 4 — Decoder validation

```text
Can video actually decode?
```

### Level 5 — Cross-source validation

```text
Filesystem metadata
↔
frame metadata
↔
recording index
```

### Level 6 — Evidence validation

```text
Hash
provenance
acquisition record
```

This hierarchy is **our proposed architecture**, informed by the published recovery methods. It is not something we should present as an established universal forensic standard.

---

# 24. What happens when recovery fails?

This is important.

Our software should not simply say:

```text
ERROR
```

It should explain:

```text
Recovery unsuccessful

Reason:
Filesystem metadata unavailable

Alternative attempted:
Frame-level carving

Result:
14,832 candidate frames found

Validated:
3,921

Reconstructed:
2,847

Reason remaining frames rejected:
Invalid frame size / timestamp inconsistency

Final status:
PARTIAL RECOVERY
```

That is far more useful to an investigator.

---

# 25. This leads directly into our proposed "recovery confidence"

Potential statuses:

```text
COMPLETE
PARTIAL
FRAGMENTED
CORRUPTED
UNVERIFIED
NOT RECOVERABLE
```

And perhaps:

```text
Confidence:
HIGH
MEDIUM
LOW
```

Again:

**This is our proposed reporting mechanism, not a claim that the forensic industry has standardized these exact labels.**

---

# 26. What we should test ourselves

This is where your actual hardware becomes valuable.

## Test 1 — Normal recording

```text
Record known event
↓
Acquire storage
↓
Recover
↓
Compare against original
```

Expected:

```text
100% known recording
```

---

## Test 2 — Delete recording

```text
Record event
↓
Delete through DVR
↓
Acquire storage
↓
Attempt recovery
```

Measure:

```text
Was recording found?
How many frames?
Metadata?
Timestamp?
Video quality?
```

---

## Test 3 — Continued recording

```text
Record A
↓
Delete A
↓
Record B/C/D/E
↓
Acquire storage
↓
Recover A
```

This tests partial overwrite.

---

## Test 4 — Fragmentation

Create enough recordings to cause storage reuse.

Then:

```text
Acquire
↓
Locate fragments
↓
Reconstruct
```

---

## Test 5 — Multi-camera

This is particularly important for your CP Plus system.

```text
Camera 1
Camera 2
Camera 3
Camera 4
...
```

Record known events simultaneously.

Then verify whether the recovered data can correctly separate:

```text
Channel 1
Channel 2
Channel 3
...
```

---

# 27. Your CP Plus + TP-Link + Hikvision access is particularly useful

We now have a possible progression:

```text
PHASE 1

CP Plus
↓
controlled experiments
↓
understand storage
```

Then:

```text
PHASE 2

Hikvision
↓
compare against published research
```

Then:

```text
PHASE 3

TP-Link
↓
determine whether architecture differs
```

Then:

```text
PHASE 4

Xiaomi / other available systems
↓
test vendor abstraction
```

But we must distinguish **camera footage** from **raw recorder storage**.

Your Xiaomi footage can help test:

* decoding
* metadata
* analytics
* timestamp processing.

It does **not automatically give us a Xiaomi DVR filesystem to reverse-engineer**.

---

# 28. The strongest thing we can say in the PPT

Not:

> "We can recover any deleted CCTV."

Absolutely not.

Instead:

> **"Our recovery architecture is designed to distinguish indexed, inaccessible, fragmented, damaged and genuinely overwritten recordings. Recovery is performed from the underlying evidence image using vendor-specific filesystem/frame structures, followed by sequence and integrity validation. Where the original data has been physically overwritten, the system reports it as unrecoverable rather than fabricating recovery."**

That is technically defensible.

---

# 29. What NTRO explicitly asks vs what we're adding

| Capability                      |                   NTRO asks? |                        Existing? | Our role                            |
| ------------------------------- | ---------------------------: | -------------------------------: | ----------------------------------- |
| Deleted footage recovery        |                            ✅ |                                ✅ | Integrate/adapt                     |
| Damaged footage recovery        |                            ✅ |                      ✅ partially | Integrate/adapt                     |
| Fragmented footage recovery     |                            ✅ |                                ✅ | Improve/standardize                 |
| Filesystem-aware recovery       |                            ✅ |                                ✅ | Vendor adapters                     |
| Frame-level recovery            |                      Implied |                                ✅ | Integrate                           |
| Recovery validation             |                            ✅ |              ✅ in research/tools | Standardize                         |
| Recovery confidence             |     Not explicitly specified |                           Varies | **Proposed**                        |
| Cross-vendor recovery framework |                Core SIH goal | Partially addressed commercially | **Our architecture**                |
| Unknown/new vendor handling     | Implied by multi-vendor goal |                          Limited | **Important engineering challenge** |
| Analog + IP differences         |      Not explicitly detailed |                  Research exists | **Architecture consideration**      |

---

# 30. The uncomfortable truth

This requirement **does not give us novelty by itself**.

Deleted DVR recovery already exists.

Fragmented recovery already exists.

Hikvision recovery exists.

Dahua recovery exists.

Commercial products already do substantial portions of this.

The 2025 research even demonstrates strong recovery performance against commercial tools. ([Directory of Open Access Journals][4])

So we should **not** tell judges:

> "Nobody has solved DVR recovery."

They can destroy that claim immediately.

---

# 31. But there is still a meaningful engineering challenge

The difficult part is the combination:

```text
Many vendors
      +
Different proprietary filesystems
      +
Different deletion mechanisms
      +
Different frame formats
      +
Different timestamp behaviour
      +
Different analog/IP architectures
      +
One standardized forensic workflow
      +
Validation
      +
Reproducible evidence
      +
Standardized reporting
```

That is the system-level problem we should investigate.

And the new Honeywell research is a particularly useful warning: even within the same broad CCTV domain, a vendor's undocumented filesystem and deletion mechanisms can require dedicated reverse engineering. ([ScienceDirect][6])

---

# 32. Current Requirement 4 verdict

| Question                                        | Finding                                        |
| ----------------------------------------------- | ---------------------------------------------- |
| Deleted recovery exists?                        | ✅ Yes                                          |
| Partially overwritten recovery exists?          | ✅ Yes                                          |
| Fragmented recovery exists?                     | ✅ Yes                                          |
| H.264 forensic recovery methodology exists?     | ✅ Yes                                          |
| Hikvision recovery                              | ✅ Strong                                       |
| Dahua recovery                                  | ✅ Strong                                       |
| Honeywell recovery                              | ✅ Recent research                              |
| Analog DVR recovery                             | ✅ Recent research                              |
| Commercial recovery                             | 🥇 Mature                                      |
| Indian forensic capability                      | ✅ Exists                                       |
| Universal recovery of every DVR?                | ❌ No                                           |
| Recovery after genuine overwrite?               | ❌ Cannot generally be guaranteed               |
| One algorithm for all vendors?                  | ❌ Unrealistic                                  |
| Vendor-specific adapters justified?             | ✅ Strongly                                     |
| Validation required?                            | ✅ Absolutely                                   |
| Recovery confidence framework                   | 🟡 Our proposed direction                      |
| Multi-vendor standardized recovery architecture | 🟡 **Still needs deeper novelty verification** |

---

## The key takeaway for your team

Think of Requirement 4 as:

```text
                 DELETED / DAMAGED STORAGE
                           │
                           ▼
                 ┌──────────────────┐
                 │ Can filesystem   │
                 │ metadata help?   │
                 └────────┬─────────┘
                          │
                   YES ───┴─── NO
                    │          │
                    ▼          ▼
              filesystem    raw/frame
                recovery     carving
                    │          │
                    └────┬─────┘
                         ▼
                  candidate frames
                         │
                         ▼
                  validate frames
                         │
                         ▼
                 reconstruct sequence
                         │
                         ▼
                    decode video
                         │
                         ▼
                 validate chronology
                         │
                         ▼
                  recovery result
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
           COMPLETE    PARTIAL   UNRECOVERABLE
```

**That is the mental model you need for the PPT.**

And the most important judge answer is:

> **We are not claiming that deleted-video recovery itself is new. Existing forensic tools and research already demonstrate it. Our challenge is building a standardized architecture that can apply vendor-specific recovery methods across the heterogeneous DVR/NVR ecosystem requested by NTRO, while preserving provenance and validating what was actually recovered.**

That is the position I would defend.

[1]: https://www.magnetforensics.com/blog/recovering-deleted-dvr-video-with-dvr-examiner/?utm_source=chatgpt.com "Recovering Deleted DVR Video with DVR Examiner - Magnet Forensics"
[2]: https://www.swgde.org/documents/published-complete-listing/15-v-002-swgde-proposed-techniques-for-advanced-data-recovery-from-security-digital-video-recorders-containing-h-264-data/?utm_source=chatgpt.com "SWGDE Proposed Techniques for Advanced Data Recovery from Security Digital Video Recorders Containing H.264 Data - SWGDE"
[3]: https://www.mdpi.com/2078-2489/16/11/983?utm_source=chatgpt.com "Automated Forensic Recovery Methodology for Video Evidence from Hikvision and Dahua DVR/NVR Systems"
[4]: https://doaj.org/article/0553b31906f547a2b978fe6604048eaf?utm_source=chatgpt.com "Automated Forensic Recovery Methodology for Video Evidence from Hikvision and Dahua DVR/NVR Systems – DOAJ"
[5]: https://www.mdpi.com/2078-2489/17/5/493?utm_source=chatgpt.com "Forensic Video Recovery from Multi-Channel Analog DVR Systems: Channel Demultiplexing and Temporal Reconstruction from Interleaved DHAV Streams | MDPI"
[6]: https://www.sciencedirect.com/science/article/pii/S2666281726000739?utm_source=chatgpt.com "Forensic analysis of video data deletion and recovery in Honeywell surveillance file system - ScienceDirect"
[7]: https://www.magnetforensics.com/resources/compare-magnet-witness-and-dvr-examiner/?utm_source=chatgpt.com "Compare Magnet Witness and DVR Examiner - Magnet Forensics"

# Requirement 5 — Timestamp Normalization and Timeline Analysis

This is the next NTRO requirement:

> **Handle inconsistent timestamps and create a reliable timeline across recordings and cameras.**

This is not simply "change all timestamps to the same timezone."

Forensics has a harder question:

> **What time did this event actually happen, and how confident are we that the displayed time is correct?**

That distinction matters.

SWGDE explicitly states that because DVRs and video formats vary widely, **there is no single approach to determining video timing that works for every system**. ([SWGDE - SWGDE][1])

---

# 1. Why NTRO asks for this

Imagine an incident at:

**18:30:00**

There are three cameras.

| Camera   | Recorder time |
| -------- | ------------: |
| Camera 1 |      18:29:57 |
| Camera 2 |      18:30:04 |
| Camera 3 |      18:31:12 |

Now the investigator has to determine:

> Did all three cameras capture the same event?

If we simply sort the displayed timestamps, the answer could be wrong.

The cameras may have:

* different clocks
* incorrect time zones
* daylight-saving configuration
* manual clock changes
* drift
* incorrect NTP configuration
* different timestamp sources
* different recording delays
* different frame timing.

And sometimes the **video timestamp itself is not the only clock involved**.

---

# 2. What "timestamp" actually means

There can be several different times associated with one piece of CCTV evidence.

For example:

```text
Camera clock
      │
      ▼
Timestamp embedded in video
      │
      ▼
DVR filesystem timestamp
      │
      ▼
Export file timestamp
      │
      ▼
Computer acquisition timestamp
```

These are not automatically identical.

Example:

```text
Camera timestamp:
18:30:02

Filesystem timestamp:
18:30:04

Exported file creation:
19:15:21

Investigator acquisition:
21:04:37
```

The last two obviously do **not** mean the event happened at those times.

---

# 3. Our system must distinguish event time from file time

This is extremely important.

### Event time

When the camera actually captured the scene.

### File time

When a file was created or modified on a storage system.

### Acquisition time

When investigators obtained the evidence.

### Processing time

When our software processed it.

These must never be casually mixed together.

---

# 4. What NTRO effectively wants

The requirement is:

```text
Raw recordings
      ↓
Understand timestamps
      ↓
Identify inconsistencies
      ↓
Normalize timeline
      ↓
Correlate cameras
      ↓
Reliable investigation timeline
```

So the output should not merely be:

```text
Camera 1 → 18:30
Camera 2 → 18:31
```

It should be more like:

```text
Camera 1
Recorded time: 18:29:57
Estimated actual time: 18:30:02
Offset: +5 sec
Confidence: HIGH

Camera 2
Recorded time: 18:30:04
Estimated actual time: 18:30:01
Offset: -3 sec
Confidence: MEDIUM
```

---

# 5. First problem — clock offset

Suppose:

```text
Real time:       18:30:00

Camera A:        18:29:55
Camera B:        18:30:03
Camera C:        18:30:01
```

Then:

```text
Camera A = +5 seconds
Camera B = -3 seconds
Camera C = -1 second
```

If we know the offsets, we can transform:

```text
Normalized time
=
Recorded time
+
Estimated offset
```

So:

```text
Camera A:
18:29:55 + 5 sec
= 18:30:00
```

But there is a major question:

> **How do we know the offset?**

That is the real forensic problem.

---

# 6. We cannot just assume the correct time

Bad approach:

```text
Camera A says 18:29
Camera B says 18:30
Camera B looks more reasonable
Therefore Camera A is wrong.
```

That is not defensible.

We need evidence.

Possible reference sources include:

* known event time
* synchronized cameras
* NTP configuration
* system logs
* GPS time
* external clock
* phone recording
* access-control system
* alarm system
* another trusted camera
* identifiable real-world event.

---

# 7. NTP

**NTP (Network Time Protocol)** = a protocol used to synchronize computer/device clocks with a time source over a network.

A recorder may be configured to periodically synchronize with an NTP server.

Conceptually:

```text
NTP server
     │
     ▼
DVR clock
     │
     ├── Camera 1
     ├── Camera 2
     └── Camera 3
```

If NTP was correctly configured and logs are available, that can provide useful evidence about clock synchronization.

But:

> **NTP configuration does not automatically prove that the recorded timestamp is correct.**

The system may have:

* lost network access
* incorrect configuration
* clock drift
* incorrect timezone
* failed synchronization.

So our system should record the source of the time information.

---

# 8. Timezone is a different problem

Suppose:

```text
Camera says:
18:00
```

What does that mean?

Could be:

```text
IST
UTC
UTC+1
UTC-5
```

If we have:

```text
Camera timezone = UTC
```

then:

```text
18:00 UTC
=
23:30 IST
```

So our normalized representation should ideally store:

```text
Original:
18:00

Timezone:
UTC

Normalized:
23:30 IST
```

Never silently modify the original timestamp.

---

# 9. Daylight-saving time

This is more relevant globally than in India, but because our system must be multi-vendor and potentially globally usable, we should account for it.

A clock can jump:

```text
01:59
02:00
03:00
```

or:

```text
01:59
01:00
```

depending on the timezone transition.

Therefore:

> **"One hour gap" does not necessarily mean missing video.**

It could be a clock adjustment.

---

# 10. Clock drift

A more difficult problem is **drift**.

Suppose Camera A starts:

```text
Real:   10:00
Camera: 09:59:55
```

Five hours later:

```text
Real:   15:00
Camera: 14:59:40
```

The difference changed from:

```text
5 seconds
```

to:

```text
20 seconds
```

So the camera is not merely offset.

Its clock is running at a slightly different rate.

That means a simple:

```text
+5 seconds
```

correction is insufficient.

---

# 11. Offset vs drift

We should understand these separately.

### Offset

Constant difference.

```text
Real:
10:00
11:00
12:00

Camera:
09:59
10:59
11:59
```

Difference:

```text
-1 minute
```

throughout.

### Drift

Difference changes over time.

```text
Real:
10:00
11:00
12:00

Camera:
09:59:55
10:59:50
11:59:40
```

Difference increases.

This requires a more sophisticated correction model.

---

# 12. Frame timing makes this even harder

A video is not simply:

```text
25 frames = 1 second
```

SWGDE explains that modern video containers use **time bases and timestamps** to represent frame timing, rather than relying solely on nominal frame rate. ([SWGDE - SWGDE][2])

For example:

```text
25 FPS
```

doesn't necessarily mean every frame is displayed at exactly:

```text
0.040000 seconds
```

after the previous frame.

This is why forensic timing analysis must inspect the actual timing information.

---

# 13. Why this matters for our recovery engine

Suppose we recover:

```text
Frame 1 → 18:30:00.000
Frame 2 → 18:30:00.040
Frame 3 → 18:30:00.080
Frame 4 → 18:30:04.000
Frame 5 → 18:30:04.040
```

There is a huge gap.

Possibilities:

1. Missing frames.
2. Recording stopped.
3. Motion recording.
4. Fragmentation.
5. Timestamp corruption.
6. Clock adjustment.
7. Different timestamp interpretation.

Our system should **detect the anomaly**, not automatically "fix" it.

---

# 14. The forensic principle

The safest architecture is:

```text
ORIGINAL TIME
      │
      ▼
PRESERVE
      │
      ▼
ANALYZE
      │
      ▼
ESTIMATE CORRECTION
      │
      ▼
NORMALIZED TIME
```

Not:

```text
ORIGINAL TIME
      ↓
overwrite
      ↓
NORMALIZED TIME
```

We need both.

---

# 15. Proposed timestamp object

Something like:

```json
{
  "recorded_timestamp": "2026-08-25T18:29:57",
  "timezone": "Asia/Kolkata",
  "normalized_timestamp": "2026-08-25T18:30:02",
  "correction_seconds": 5,
  "correction_method": "external_reference_event",
  "confidence": "HIGH",
  "original_preserved": true
}
```

Again:

**This is our proposed data structure, not an existing forensic standard.**

---

# 16. How do we estimate the correction?

There are several possible approaches.

## Method 1 — Known external event

Suppose a person rings a bell at exactly:

```text
18:30:00
```

from an independently timestamped system.

Camera shows the event at:

```text
18:29:55
```

Potential offset:

```text
+5 seconds
```

This is relatively understandable.

---

# 17. Method 2 — Cross-camera event

Suppose a person walks from:

```text
Camera A
```

to:

```text
Camera B
```

and the movement is physically known to take approximately 4 seconds.

Camera A:

```text
18:30:00
```

Camera B:

```text
18:30:09
```

Potential discrepancy:

```text
5 seconds
```

But this is **not automatically proof** because the person's actual movement time may vary.

Therefore this should be treated as supporting evidence rather than absolute truth.

---

# 18. Method 3 — Common event

Suppose:

```text
Lightning
vehicle collision
door opening
alarm activation
person entering
```

appears simultaneously across several cameras.

We can use the common event as a temporal anchor.

Example:

```text
Camera A: 18:30:05
Camera B: 18:30:12
Camera C: 18:30:08
```

If the physical event should be simultaneous:

```text
A offset = +7
B offset = 0
C offset = +4
```

Again:

**This is an inference and must be labelled as such.**

---

# 19. Method 4 — Device/system logs

The recorder may contain:

```text
NTP synchronization logs
system logs
boot events
configuration changes
timezone changes
```

These can help determine:

```text
When was the clock changed?
When was it synchronized?
Was the timezone modified?
```

This is potentially much stronger than guessing from the video.

---

# 20. Method 5 — Embedded metadata

The video itself may contain timing information.

SWGDE notes that timing information can be distributed across multiple elements within a multimedia file and must be decoded/calculated rather than simply read from one field. ([SWGDE - SWGDE][2])

Therefore:

```text
Container metadata
+
frame timestamps
+
DVR metadata
```

can be compared.

---

# 21. What if the displayed timestamp was manually changed?

This is a serious forensic issue.

Suppose:

```text
Original camera:
14:00
```

Someone changes it:

```text
16:00
```

Now the footage appears to show the wrong time.

Our system should not automatically "correct" it.

Instead:

```text
Timestamp anomaly:
Detected

Potential cause:
Device clock modification

Evidence:
System configuration/log information
```

Then the examiner decides how to interpret it.

---

# 22. India-specific evidence

This requirement is not theoretical.

A recent 2025 case study from India's Directorate of Forensic Science Services examined **temporal inconsistencies and metadata discrepancies in CCTV footage** in a forensic context. ([qjoest.com][3])

That is a particularly useful source for us because it shows that:

> **timestamp/metadata inconsistency is an actual forensic issue in India.**

It should be useful in the PPT when explaining why this requirement matters.

---

# 23. Best global guidance

SWGDE is the strongest practical reference here.

Its current published video guidance includes:

* digital video analysis
* frame timing
* DVR acquisition
* digital video authentication
* video evidence collection. ([SWGDE - SWGDE][4])

[SWGDE Video guidance](https://www.swgde.org/documents/published-by-committee/video/)

[SWGDE Core Technical Concepts for Time-Based Analysis](https://www.swgde.org/documents/published-complete-listing/19-v-002-swgde-core-technical-concepts-for-time-based-analysis-of-digital-video-files/)

[SWGDE Frame Timing Analysis](https://www.swgde.org/documents/published-complete-listing/19-v-005-swgde-best-practice-for-frame-timing-analysis-of-video-stored-in-iso-base-media-file-formats/)

These are much better references for our PPT than generic "timestamp normalization" articles.

---

# 24. NIST's contribution

NIST's CCTV work is also directly relevant.

NIST states that the lack of a common CCTV export standard causes:

* conversion
* metadata loss
* quality degradation
* delays
* interoperability problems. ([NIST][5])

Its goal is standardized exchange of CCTV evidence between systems and law enforcement.

That directly supports our **normalization layer**.

---

# 25. What is the difference between normalization and correction?

This is something we should explain carefully to judges.

### Normalization

Put different timestamp representations into a common representation.

Example:

```text
Camera A:
25/08/2026 18:30

Camera B:
2026-08-25 18:30:00 UTC

Camera C:
18:30:00 +0530
```

Normalize into:

```text
2026-08-25T18:30:00+05:30
```

No claim that the time itself is correct.

---

### Correction

Estimate that the recorder clock is wrong.

Example:

```text
Recorded:
18:29:55

Estimated actual:
18:30:00
```

This requires evidence.

Therefore:

> **Normalization is formatting. Correction is forensic inference.**

That's a very important distinction.

---

# 26. Proposed processing pipeline

```text
                 VIDEO + METADATA
                         │
                         ▼
               Extract all time sources
                         │
                         ▼
              Identify timezone/format
                         │
                         ▼
              Preserve original timestamp
                         │
                         ▼
             Detect temporal anomalies
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
       No anomaly                Anomaly
             │                       │
             │               investigate source
             │                       │
             │               ┌───────┼────────┐
             │               ▼       ▼        ▼
             │              NTP    logs   other video
             │                       │
             └───────────────┬───────┘
                             ▼
                    Estimate correction
                             │
                             ▼
                     Confidence score
                             │
                             ▼
                    Normalized timeline
```

---

# 27. The normalized timeline

The final output could look like:

| Event               | Camera        | Original time | Correction | Normalized time | Confidence |
| ------------------- | ------------- | ------------: | ---------: | --------------: | ---------- |
| Person enters       | CP Plus CH1   |      18:29:55 |     +5 sec |        18:30:00 | High       |
| Person enters       | Hikvision CH3 |      18:30:03 |     −3 sec |        18:30:00 | Medium     |
| Person crosses road | TP-Link CH2   |      18:30:08 |     −7 sec |        18:30:01 | Low        |

The important part:

**Original time is never deleted.**

---

# 28. Timeline anomalies should be visible

Suppose:

```text
18:30:00
18:30:01
18:30:02
18:45:02
18:45:03
```

Our interface should show:

```text
⚠ 15-minute temporal gap
```

Then:

```text
Possible explanations:
- recording interruption
- motion-triggered recording
- missing data
- clock adjustment
- damaged metadata
```

The system should **flag**, not invent an explanation.

---

# 29. Cross-camera event correlation

This leads directly to the next NTRO requirement.

Once timestamps are normalized:

```text
Camera 1
18:30:00
     │
     ├──────► Person enters
     │
Camera 2
18:30:02
     │
     ├──────► Person crosses corridor
     │
Camera 3
18:30:05
     │
     └──────► Person exits
```

We can produce:

```text
18:30:00 ─ Person enters building
18:30:02 ─ Person appears in corridor
18:30:05 ─ Person exits corridor
```

This is the beginning of **event correlation**.

---

# 30. But don't overclaim "AI correlation"

For Round 1, we don't need some giant AI model.

Basic correlation can be:

```text
timestamp window
+
camera location
+
event type
```

For example:

```text
Person detected
Camera A
±5 sec
        ↓
Person detected
Camera B
```

Later we can add:

```text
object identity
trajectory
appearance similarity
```

But those are much harder.

---

# 31. Technology options

For timestamp processing, the important technologies are not necessarily glamorous.

### Python

Useful for:

* timestamp parsing
* timezone conversion
* data processing
* timeline generation
* orchestration.

### FFmpeg / FFprobe

Useful for:

* extracting media timing information
* frame-level inspection
* technical metadata.

SWGDE explicitly references FFmpeg for generating frame-information reports. ([SWGDE - SWGDE][1])

### Database

Useful for:

```text
recording
camera
timestamp
event
offset
confidence
```

relationships.

### Timezone database

Use a proper timezone database rather than hard-coding:

```text
+05:30
```

for every situation.

---

# 32. Alternatives

| Approach                    | Use                    | Problem                            |
| --------------------------- | ---------------------- | ---------------------------------- |
| Simple timestamp conversion | Basic normalization    | Doesn't establish correctness      |
| Fixed offset correction     | Known clock offset     | Fails with drift                   |
| Linear drift correction     | Clock drift            | Requires reliable reference points |
| NTP evidence                | Device synchronization | NTP may not have worked            |
| Cross-camera correlation    | Common events          | Inference, not absolute truth      |
| External reference          | Strong anchor          | Often unavailable                  |
| Manual examiner correction  | Complex cases          | Slow and subjective                |
| Automated correction        | Large-scale analysis   | Risk of false confidence           |

Therefore:

> **Our system should support multiple evidence sources rather than relying on one correction method.**

---

# 33. What should happen when we cannot determine the correct time?

This is important.

We should output:

```text
Original timestamp:
18:29:55

Timezone:
Unknown

Clock correction:
Not established

Normalized timestamp:
18:29:55

Confidence:
LOW

Warning:
Absolute event time could not be independently established.
```

That is much better forensic behaviour than pretending:

```text
18:30:00
```

is definitely correct.

---

# 34. Industry lesson

Professional forensic systems don't magically know the "true time."

The examiner has to establish it from evidence.

SWGDE specifically cautions that the source of the video should be known and verified and that transcoding can affect playback timing. It also notes that playback software may interpret timing differently. ([SWGDE - SWGDE][2])

So our software should assist the examiner rather than pretend to replace forensic judgement.

---

# 35. Indian solution/research

The recent Indian DFSS case study is useful:

[Forensic Analysis of Temporal Inconsistencies and Metadata Discrepancies in CCTV Footage](https://www.qjoest.com/index.php/qjoest/article/view/267)

It demonstrates that Indian forensic examination can encounter:

* timestamp inconsistency
* metadata discrepancies
* authenticity questions
* temporal analysis.

([qjoest.com][3])

For the PPT, this gives us a concrete Indian example supporting the problem.

---

# 36. Existing solution status

| Capability                                        | Status                                    |
| ------------------------------------------------- | ----------------------------------------- |
| Read video timestamps                             | ✅ Mature                                  |
| Frame timing analysis                             | ✅ Mature                                  |
| Timezone normalization                            | ✅ Standard engineering                    |
| NTP-based investigation                           | ✅ Existing                                |
| Detect timestamp inconsistencies                  | ✅ Existing                                |
| Cross-camera timeline creation                    | ✅ Existing concept                        |
| Correct clock offset                              | ✅ Existing methodologies                  |
| Correct clock drift                               | ✅ Existing methodologies                  |
| Determine "true time" automatically in every case | ❌ Not solved                              |
| One universal timestamp method for all DVRs       | ❌ Not possible                            |
| Preserve original + corrected representation      | ✅ Established forensic principle          |
| Automated confidence-based correction             | 🟡 Possible, but needs careful validation |
| Vendor-independent temporal model                 | 🟡 Proposed architecture                  |

---

# 37. What is actually interesting for our project?

Again, **timestamp normalization itself is not novel.**

We should not claim:

> "We invented timestamp correction."

Instead, our engineering challenge is:

```text
Different vendors
      ↓
Different timestamp formats
      ↓
Different metadata structures
      ↓
Different clock behaviour
      ↓
Different video timing
      ↓
ONE normalized evidence timeline
```

The value is in **integrating vendor-specific extraction with a common forensic timeline model**.

---

# 38. What we should test ourselves

This is an excellent area for a Round 1 experiment.

## Test A — Intentionally change a DVR clock

On your CP Plus system, with a controlled test setup:

```text
Camera clock = correct time
```

Record event.

Then:

```text
change DVR clock by +30 sec
```

Record another event.

Then recover both.

Question:

> Can our system detect the discontinuity?

---

## Test B — Multiple cameras

Record the same event across:

* CP Plus
* Hikvision, if permitted
* TP-Link, where technically comparable.

Compare timestamps.

---

## Test C — External reference

Record the same event using a trusted external clock/video source.

Then compare:

```text
DVR timestamp
vs
external reference
```

---

## Test D — Drift

Leave a controlled device running for an extended period.

Measure:

```text
Day 1 offset
Day 2 offset
Day 3 offset
```

This tells us whether a constant-offset model is sufficient.

---

# 39. What we should say in the PPT

### Weak version

> "We normalize timestamps between cameras."

Too vague.

### Better version

> **"Because different DVR/NVR systems can use different clock settings, metadata structures and frame-timing mechanisms, our platform preserves the original timestamps, identifies temporal inconsistencies, records the evidence used for any correction, and generates a normalized investigation timeline without overwriting the source timestamps."**

That's defensible.

---

# 40. Judge questions

### "How do you know your corrected timestamp is correct?"

**Answer:**

> We don't automatically assume it is correct. The original timestamp is preserved. A correction is made only when supporting evidence such as system time information, synchronization records, known events or cross-camera evidence supports it. The correction method and confidence are recorded.

---

### "Why can't you just synchronize all cameras?"

> Because the recordings may already exist with different clock states. We are performing forensic analysis on evidence that has already been recorded. We need to preserve and interpret the original timestamps rather than simply changing the devices' clocks.

---

### "What if the camera clock is wrong?"

> We detect the discrepancy where supporting evidence exists, estimate the offset or drift, and retain both the original and normalized times.

---

### "What if you don't know the correct time?"

> We report the original timestamp and mark the absolute time as unverified rather than inventing a correction.

---

### "Why not just sort all videos by timestamp?"

> Because timestamps can be wrong, clocks can differ, and video timing itself may not be represented by a simple frame-rate calculation. SWGDE specifically notes that no single timing approach applies to all proprietary DVR/video systems. ([SWGDE - SWGDE][1])

---

### "Can FFmpeg solve this?"

> FFmpeg can expose useful frame and media timing information, but it cannot determine whether a DVR's physical clock was correct. That requires forensic interpretation and potentially external evidence.

SWGDE specifically references FFmpeg for frame-information analysis. ([SWGDE - SWGDE][1])

---

# 41. Requirement 5 — verdict

### What NTRO asks

```text
Handle inconsistent timestamps
+
timeline analysis
```

### What already exists

```text
YES
```

There are established:

* frame timing methods
* forensic timing guidance
* timestamp analysis
* CCTV timeline workflows
* synchronization approaches.

### What remains difficult

```text
Determining the actual event time
when multiple unreliable/proprietary
recorders disagree.
```

### Our architecture

```text
Original timestamp
       ↓
Metadata extraction
       ↓
Timing analysis
       ↓
Anomaly detection
       ↓
Evidence-based correction
       ↓
Confidence
       ↓
Normalized timeline
```

### What we should NOT claim

❌ "Our timestamp correction is novel."

### What we CAN reasonably propose

> **A common, auditable timeline layer that takes vendor-specific timestamp information, preserves the original values, records correction evidence, and exposes uncertainty instead of silently modifying forensic evidence.**

That is the correct direction.

---

## The pipeline now becomes

```text
┌──────────────────────────────┐
│ 1. ACQUIRE                   │
│ Get original evidence        │
└──────────────┬───────────────┘
               ↓
┌──────────────────────────────┐
│ 2. IDENTIFY / PARSE          │
│ Understand vendor storage     │
└──────────────┬───────────────┘
               ↓
┌──────────────────────────────┐
│ 3. EXTRACT                   │
│ Video + metadata             │
└──────────────┬───────────────┘
               ↓
┌──────────────────────────────┐
│ 4. RECOVER                   │
│ Deleted / fragmented /       │
│ damaged recordings           │
└──────────────┬───────────────┘
               ↓
┌──────────────────────────────┐
│ 5. TIMELINE                  │
│ Normalize + validate time    │
└──────────────┬───────────────┘
               ↓
        NEXT: REQUIREMENT 6
       CROSS-CAMERA EVENT
          CORRELATION
```

And **Requirement 6 is where we start connecting multiple cameras into one incident timeline**. That is where we need to be particularly careful about the difference between simple timestamp matching and genuine event/identity correlation.

[1]: https://www.swgde.org/wp-content/uploads/2023/11/2020-09-17-SWGDE-Core-Technical-Concepts-for-Time-Based-Analysis-of-Digital-Video-Files_v1.0.pdf?utm_source=chatgpt.com "SWGDE Core Technical Concepts for Time-Based Analysis of Digital Video Files"
[2]: https://www.swgde.org/documents/published-complete-listing/19-v-002-swgde-core-technical-concepts-for-time-based-analysis-of-digital-video-files/?utm_source=chatgpt.com "SWGDE Core Technical Concepts for Time-Based Analysis of Digital Video Files - SWGDE"
[3]: https://www.qjoest.com/index.php/qjoest/article/view/267?utm_source=chatgpt.com "FORENSIC ANALYSIS OF TEMPORAL INCONSISTENCIES AND METADATA DISCREPANCIES IN CCTV FOOTAGE: A CASE STUDY | Quantum Journal of Engineering, Science and Technology"
[4]: https://www.swgde.org/documents/published-by-committee/video/?utm_source=chatgpt.com "Video - SWGDE"
[5]: https://www.nist.gov/programs-projects/digital-video-exchange-standards?utm_source=chatgpt.com "Digital Video Exchange Standards | NIST"

# Requirement 6 — Cross-Camera Event Correlation

This is the next major NTRO requirement.

NTRO asks for:

> **correlating events across multiple cameras**

The simple version sounds easy:

```text
Camera 1 → person at 10:00
Camera 2 → person at 10:02
Camera 3 → person at 10:04
```

But a forensic system has to answer something much harder:

> **Are these actually the same incident/person/event, and what evidence supports that conclusion?**

This is where **timeline normalization + camera metadata + object detection + tracking + location information** start coming together.

---

# 1. What does "event correlation" mean?

Imagine a building with 5 cameras.

```text
Camera 1
Entrance
   ↓
Camera 2
Lobby
   ↓
Camera 3
Corridor
   ↓
Camera 4
Stairs
   ↓
Camera 5
Exit
```

A person enters at:

```text
10:00:12
```

Then appears in:

```text
Camera 2 → 10:00:19
Camera 3 → 10:00:31
Camera 4 → 10:00:47
Camera 5 → 10:01:12
```

Instead of forcing an investigator to watch five videos independently, our system could construct:

```text
10:00:12  Person enters
10:00:19  Person appears in lobby
10:00:31  Person enters corridor
10:00:47  Person reaches stairs
10:01:12  Person exits
```

That is **cross-camera event correlation**.

SWGDE explicitly describes video as useful for establishing timelines and visualizing an incident from multiple perspectives and locations. ([SWGDE - SWGDE][1])

---

# 2. But correlation does NOT automatically mean "face recognition"

This is important.

There are different levels.

### Level 1 — Time correlation

```text
Camera A
10:00:00

Camera B
10:00:04
```

Events occurring within a defined time window.

---

### Level 2 — Location correlation

If Camera A covers:

```text
Entrance
```

and Camera B covers:

```text
Lobby
```

then a person appearing in A and shortly afterwards in B is plausible.

---

### Level 3 — Object correlation

**Object detection (AI that identifies objects such as people, cars, bags, etc.)**

Example:

```text
Camera A:
Person + red shirt

Camera B:
Person + red shirt
```

---

### Level 4 — Appearance correlation

**Re-identification (matching the same person/object across different camera views using visual characteristics).**

For example:

```text
Camera A
Person:
red shirt
black trousers
backpack

          ↓

Camera B
Person:
red shirt
black trousers
backpack
```

This is stronger than simply saying "a person was detected."

---

### Level 5 — Face recognition

The system compares facial features.

Potentially:

```text
Camera A
Face → Person X

Camera B
Face → Person X
```

But this is much more sensitive and technically difficult.

And importantly:

> **NTRO asks for face detection, not necessarily identity recognition.**

Do not accidentally turn "face detection" into "we identify criminals."

---

# 3. The first layer should be non-AI

We should not immediately throw a neural network at the problem.

Start with:

```text
Camera metadata
+
timestamp
+
location
+
event type
```

Example:

```text
Camera A
Location = Entrance
Time = 10:00:12
Event = Person detected

Camera B
Location = Lobby
Time = 10:00:19
Event = Person detected
```

The system can determine:

```text
Possible continuation
```

before using more expensive AI analysis.

---

# 4. Why location matters

Suppose:

```text
Camera A = Building entrance
Camera B = Parking lot
```

A person appearing in both within 1 second may be impossible depending on the physical layout.

But:

```text
Camera A = Entrance
Camera B = Lobby
```

makes a 5-second transition plausible.

So the system needs a **camera topology (information describing how cameras are physically related)**.

Example:

```text
Entrance
   │
   ▼
Lobby
   │
   ├── Corridor
   │
   └── Stairs
```

This can become a graph.

---

# 5. Camera graph

Think of it as:

```text
              Camera 2
                Lobby
               /     \
              /       \
      Camera 3       Camera 4
      Corridor        Stairs
          |
      Camera 5
        Exit
```

Each node:

```text
Camera
```

Each connection:

```text
Possible movement path
```

Then the system can reject impossible sequences.

Example:

```text
Camera 1 → Camera 2
5 seconds
```

Possible.

But:

```text
Camera 1 → Camera 5
1 second
```

Maybe impossible.

The exact travel-time constraints should be based on the physical site, not invented by the software.

---

# 6. What input does our correlation layer need?

```text
                    INPUT
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   Video events    Timestamps    Camera info
        │             │             │
        │             │             ├── location
        │             │             ├── direction
        │             │             └── relationships
        │             │
        ▼             ▼
   AI detections   normalized time
        │             │
        └─────────────┘
               │
               ▼
       EVENT CORRELATION
```

---

# 7. What exactly is an "event"?

We should define this carefully.

An event could be:

```text
Person detected
Vehicle detected
Face detected
Object left behind
Door opened
Motion detected
Person enters region
Person exits region
Recording starts
Recording stops
Alarm triggered
```

The first version should probably focus on:

```text
Person
Vehicle
Motion
```

rather than trying to support every imaginable event.

---

# 8. Motion detection is not the same as object detection

### Motion detection

Something changed between frames.

```text
Frame 1
████████

Frame 2
█████ person ███

→ Motion detected
```

It doesn't necessarily know what moved.

---

### Object detection

AI identifies:

```text
Person
Car
Motorcycle
Bag
Dog
etc.
```

So:

```text
Motion:
"Something moved."

Object detection:
"A person moved."
```

This distinction matters when answering judges.

---

# 9. Object detection output

A detector might produce:

```text
Camera 1
Timestamp: 10:00:12

Person
Bounding box:
x=100
y=50
width=120
height=300

Confidence:
0.94
```

**Bounding box (a rectangle showing where an detected object appears in an image).**

Then:

```text
Camera 2
10:00:19

Person
Confidence:
0.91
```

Now the correlation engine has something to work with.

---

# 10. Tracking is the next step

**Object tracking (following a detected object across consecutive video frames).**

Suppose:

```text
Frame 1 → Person
Frame 2 → Person
Frame 3 → Person
Frame 4 → Person
```

The tracker tries to maintain:

```text
Track ID = 17
```

So:

```text
10:00:12 → Person #17
10:00:13 → Person #17
10:00:14 → Person #17
```

This is different from detection.

Detection:

> "There is a person."

Tracking:

> "This is the same detected person as in the previous frame."

---

# 11. Cross-camera tracking is harder

Within one camera:

```text
Person #17
↓
Person #17
↓
Person #17
```

Easy enough.

Across cameras:

```text
Camera A:
Person #17

Camera B:
Person #4
```

The numbers are local to each camera.

We need to determine:

```text
Person #17 in A
       ?
Person #4 in B
```

That is **cross-camera re-identification**.

---

# 12. Re-identification

**Re-identification (Re-ID)** = estimating whether two detections from different cameras represent the same physical person/object.

Possible features:

```text
clothing
color
body shape
backpack
vehicle appearance
movement pattern
```

But this can fail badly.

Example:

```text
Camera A:
red shirt

Camera B:
red shirt
```

There could be 20 people wearing red shirts.

So:

> **Appearance similarity is evidence, not identity proof.**

This is a critical forensic distinction.

---

# 13. Face recognition has the same problem

A face recognition system may output:

```text
Person A
similarity = 0.92
```

That does not mean:

> "This is definitely Person A."

There can be:

* poor lighting
* blur
* occlusion
* camera angle
* low resolution
* compression
* masks
* aging
* false matches.

Therefore our forensic system should preserve:

```text
model
version
threshold
confidence
source frame
```

rather than simply output:

```text
IDENTIFIED
```

---

# 14. Proposed architecture

The correlation layer should look something like:

```text
                  NORMALIZED EVIDENCE
                         │
                         ▼
                ┌─────────────────┐
                │ Event Extraction│
                └────────┬────────┘
                         │
             ┌───────────┼───────────┐
             ▼           ▼           ▼
          Person       Vehicle      Motion
          events       events       events
             │           │           │
             └───────────┼───────────┘
                         ▼
                 Camera Topology
                         │
                         ▼
                   Time Window
                         │
                         ▼
                Candidate Matches
                         │
                         ▼
                Appearance / Re-ID
                         │
                         ▼
                 Correlation Score
                         │
                         ▼
                Human Review
                         │
                         ▼
                 Incident Timeline
```

---

# 15. Why "human review" should remain

This is extremely important for a forensic product.

We should not say:

> "AI determines the suspect."

Instead:

```text
AI
 ↓
Candidate relationship
 ↓
Investigator review
 ↓
Final interpretation
```

The AI assists the examiner.

The examiner remains responsible for interpretation.

SWGDE's forensic-video guidance is explicitly oriented toward analysts performing examination and evaluation of evidence for legal matters. ([SWGDE - SWGDE][2])

---

# 16. Correlation score

We could potentially calculate:

```text
Correlation Score =
time similarity
+
location compatibility
+
object similarity
+
appearance similarity
```

For example:

```text
Candidate A

Time compatibility       0.95
Location compatibility   0.90
Appearance similarity    0.82

Overall:
0.89
```

But this must be treated carefully.

A simple weighted score is **our proposed design**, not a universal forensic standard.

The system should show **why** it reached the score.

---

# 17. Explainable correlation

Instead of:

```text
MATCH = 94%
```

show:

```text
Possible same person

Reasons:
✓ Appeared 7 seconds later
✓ Camera B is connected to Camera A
✓ Same clothing colour
✓ Same backpack
✓ Movement direction consistent

Uncertainty:
⚠ Face not visible
⚠ Camera B image quality low
```

This is much more useful to an investigator.

---

# 18. Event correlation without AI

This is actually a useful Round 1 prototype.

Suppose we manually provide:

```text
Camera 1
Entrance
10:00:00
Person

Camera 2
Lobby
10:00:07
Person

Camera 3
Corridor
10:00:14
Person
```

Our software can automatically generate:

```text
INCIDENT #001

10:00:00
Person enters

       ↓ 7 sec

10:00:07
Person enters lobby

       ↓ 7 sec

10:00:14
Person enters corridor
```

No fancy AI required.

That proves the core architecture.

---

# 19. Then add AI

Once the timeline works:

```text
Video
 ↓
Object detector
 ↓
Person/vehicle events
 ↓
Tracker
 ↓
Correlation engine
```

This gives us an incremental implementation path.

---

# 20. What existing standards tell us

NIST's CCTV export work is highly relevant.

NIST's objective is interoperability between CCTV/DVR systems and law enforcement, and its recommended format includes standardized date/time metadata and additional metadata for video analytics. ([NIST][3])

The NIST specification specifically emphasizes:

* frame-level timestamps
* system clock offset
* metadata
* interoperability
* video analytics. ([NIST Publications][4])

That means our **normalized evidence representation** is not an arbitrary idea.

It follows the same broader problem that NIST has identified:

```text
Different systems
      ↓
Different representations
      ↓
Need common evidence representation
```

---

# 21. NIST gives us an interesting architectural clue

NIST's proposed export profile includes:

```text
Video
+
standard timestamp information
+
clock-offset metadata
+
metadata
```

and was specifically developed to support law-enforcement investigations. ([NIST][5])

Our system is going one level earlier:

```text
Proprietary DVR storage
        ↓
vendor-specific extraction
        ↓
normalized evidence
        ↓
timeline/correlation
```

So the normalization layer becomes the bridge between:

```text
proprietary evidence
```

and:

```text
standardized investigation workflow
```

That is a very important architectural point for SIH26150.

---

# 22. Existing industry capability

Professional forensic/video platforms already provide substantial forms of:

* multi-camera review
* timeline analysis
* object detection
* tracking
* video search
* evidence management.

Therefore:

❌ We cannot claim:

> "Cross-camera analysis is new."

Nor:

❌ "AI object detection in CCTV is new."

Both are mature areas.

Our question is:

> **How do we connect these capabilities to evidence recovered from heterogeneous proprietary DVR/NVR storage inside the standardized forensic workflow NTRO requests?**

That's the more defensible system-level question.

---

# 23. The important difference

Typical video analytics:

```text
MP4
 ↓
AI
 ↓
person detected
```

Our architecture:

```text
DVR/NVR
 ↓
forensic acquisition
 ↓
proprietary parsing
 ↓
recovery
 ↓
metadata
 ↓
timestamp normalization
 ↓
AI analysis
 ↓
cross-camera correlation
 ↓
validated evidence
```

That distinction matters.

The AI itself isn't the difficult part.

**Getting trustworthy evidence into the AI pipeline without losing its forensic context is.**

---

# 24. Why recovered footage complicates correlation

Suppose:

```text
Camera A:
18:30:00
Recovered normally

Camera B:
18:30:04
Recovered from fragments

Camera C:
18:30:08
Timestamp uncertain
```

Can we simply correlate them?

No.

The correlation engine needs to know:

```text
Camera A
timestamp confidence = HIGH

Camera B
timestamp confidence = MEDIUM

Camera C
timestamp confidence = LOW
```

So the previous requirement directly affects this one.

---

# 25. Evidence provenance

**Provenance (the record showing where a piece of evidence came from and what happened to it).**

For every correlated event, we should be able to trace:

```text
Incident
 ↓
Camera
 ↓
Recording
 ↓
Recovered frame
 ↓
Storage offset
 ↓
Forensic image
 ↓
Acquisition hash
```

Then an investigator can answer:

> "Where did this event come from?"

That is far more important than simply displaying a pretty timeline.

---

# 26. Proposed event object

Conceptually:

```text
Event
│
├── Event ID
├── Camera ID
├── Source evidence ID
├── Original timestamp
├── Normalized timestamp
├── Timestamp confidence
├── Event type
├── Object type
├── Detection confidence
├── Frame references
├── Storage location
├── Evidence hash
└── Correlation links
```

Then:

```text
Event A
    │
    ├── correlated with
    ▼
Event B
    │
    ├── correlated with
    ▼
Event C
```

This produces an **evidence graph**.

---

# 27. Evidence graph

For example:

```text
              Person detected
                    │
                    ▼
             Camera 1 / 10:00
                    │
            7 sec / possible path
                    │
                    ▼
             Camera 2 / 10:07
                    │
           8 sec / appearance
                    │
                    ▼
             Camera 3 / 10:15
```

Each relationship can contain:

```text
Why linked?
Confidence?
Evidence?
```

This is much more defensible than a black-box AI answer.

---

# 28. What if cameras overlap?

This is actually easier.

Suppose two cameras see the same doorway.

```text
Camera A ──┐
           │
        doorway
           │
Camera B ──┘
```

A person appears:

```text
A → 10:00:05
B → 10:00:06
```

This provides a strong temporal/spatial relationship.

The system can use:

* overlapping field of view
* timestamp difference
* object appearance
* movement direction.

---

# 29. What if cameras do NOT overlap?

Then we rely more on:

* camera topology
* travel-time constraints
* timestamps
* appearance
* object characteristics.

Confidence should be lower.

Example:

```text
Camera A
10:00:00

        20 seconds

Camera B
10:00:20
```

If they are 100 metres apart, plausible.

If they are 5 km apart, probably not.

Again:

**Physical layout matters.**

---

# 30. Camera topology could be manually configured

For the prototype, we do not need computer vision to automatically map the entire building.

We could provide:

```text
Camera 1
Location: Main Entrance

Camera 2
Location: Lobby

Connection:
Camera 1 → Camera 2
Minimum transition: 3 sec
Typical transition: 8 sec
Maximum expected: 30 sec
```

Then the correlation engine works with this information.

Later:

```text
automatic topology discovery
```

could be researched.

---

# 31. Why this is useful for SIH

Imagine a judge asks:

> "You have six cameras. Why is your system better than watching six videos?"

We can demonstrate:

```text
Upload evidence
      ↓
System extracts events
      ↓
Normalize time
      ↓
Build timeline
      ↓
Group related events
      ↓
Show investigator:
```

```text
INCIDENT #17

18:30:02
Person enters Gate A

18:30:08
Person enters lobby

18:30:17
Person enters corridor

18:30:31
Person reaches staircase

18:31:02
Person exits building
```

That is a strong demo.

---

# 32. But don't make the demo dependent on perfect Re-ID

This is important.

Your first demo should work even if:

```text
face unavailable
```

or:

```text
person appearance changes
```

The core correlation should work using:

```text
time
+
camera topology
+
event type
```

Then AI becomes an enhancement.

This reduces project risk.

---

# 33. AI layer options

Potential components:

### Object detection

Examples:

* YOLO family
* RT-DETR
* other modern detectors.

### Tracking

Examples:

* ByteTrack
* Deep SORT
* OC-SORT.

### Re-identification

Person Re-ID models can compare visual embeddings.

**Embedding (a numerical representation of visual characteristics used for similarity comparison).**

But we should research these choices separately before committing.

---

# 34. What we should NOT do

Don't build:

```text
YOLO
+
face recognition
+
LLM
+
dashboard
```

and call it:

> "AI-powered forensic correlation."

That would be exactly the kind of superficial AI layer we wanted to avoid.

The forensic pipeline must come first.

---

# 35. Proposed complete processing

```text
RAW DVR/NVR EVIDENCE
          │
          ▼
   FORENSIC ACQUISITION
          │
          ▼
    VENDOR PARSING
          │
          ▼
 VIDEO + METADATA RECOVERY
          │
          ▼
 TIMESTAMP NORMALIZATION
          │
          ▼
      EVENT EXTRACTION
          │
       ┌──┴─────┐
       ▼        ▼
    Motion    Object
   detection detection
       │        │
       └──┬─────┘
          ▼
      TRACKING
          │
          ▼
   CAMERA TOPOLOGY
          │
          ▼
 CROSS-CAMERA CORRELATION
          │
          ▼
   CORRELATION EVIDENCE
          │
          ▼
     HUMAN REVIEW
          │
          ▼
    INCIDENT TIMELINE
```

---

# 36. What should the investigator see?

Not:

```text
AI says:
Same person = 96%
```

Instead:

```text
Possible cross-camera match

Camera A
10:00:12

Camera B
10:00:19

Supporting evidence:
✓ Compatible timestamps
✓ Camera B follows Camera A
✓ Same object class
✓ Similar clothing
✓ Movement direction compatible

Limitations:
⚠ Face not visible
⚠ Camera B resolution low

Assessment:
POSSIBLE MATCH
```

This is much more forensic-friendly.

---

# 37. Existing vs our proposed work

| Capability                                           |      Existing? | Our position           |
| ---------------------------------------------------- | -------------: | ---------------------- |
| Multi-camera video review                            |              ✅ | Use                    |
| Timeline generation                                  |              ✅ | Integrate              |
| Object detection                                     |              ✅ | Integrate              |
| Motion detection                                     |              ✅ | Integrate              |
| Object tracking                                      |              ✅ | Integrate              |
| Person Re-ID                                         |              ✅ | Optional               |
| Face recognition                                     |              ✅ | Optional               |
| Cross-camera correlation                             |              ✅ | Integrate              |
| Camera topology                                      | ✅ conceptually | Build                  |
| Evidence-aware correlation                           |             🟡 | Important architecture |
| Recovery-aware correlation                           |             🟡 | Important architecture |
| Confidence + reasons                                 |      🟡 varies | Proposed               |
| Trace correlation back to forensic source            |             🟡 | Core design            |
| Unified multi-vendor forensic → correlation workflow |             🟡 | **Core SIH direction** |

---

# 38. Round 1 implementation

We don't need to implement everything.

A good prototype:

```text
3–5 cameras
      ↓
known timestamps
      ↓
predefined camera topology
      ↓
person/object detection
      ↓
simple tracking
      ↓
time-window correlation
      ↓
incident timeline
```

Then show:

```text
SOURCE
↓
CAMERA
↓
FRAME
↓
EVENT
↓
CORRELATION
↓
TIMELINE
```

That proves the architecture.

---

# 39. The best Round 1 experiment

Use your actual data where possible.

For example:

```text
CP Plus recordings
+
TP-Link recordings
+
Hikvision recording if permitted
```

Create a controlled event:

> One person walks through known locations.

Then record:

```text
Camera A → entrance
Camera B → lobby
Camera C → corridor
```

The goal:

```text
Expected sequence:

A → B → C
```

Then see whether our system reconstructs it.

This gives us an actual measurable result.

---

# 40. Metrics

We should measure:

### Event detection accuracy

How many actual events did we detect?

### False positive rate

How many reported events were wrong?

### Correlation precision

Of the matches we produced, how many were correct?

### Correlation recall

Of the true relationships, how many did we find?

### Timeline accuracy

How close was the generated timeline to the controlled ground truth?

### Processing time

How long did the system take?

These are much stronger PPT numbers than:

> "Our AI is powerful."

---

# 41. Judge questions

### "How do you know two people in different cameras are the same?"

**Answer:**

> We do not treat appearance similarity alone as proof. We combine temporal compatibility, camera topology, object characteristics and, where available, visual similarity. The result is presented as a correlation with supporting evidence and uncertainty, not as an absolute identity claim.

---

### "Why do you need AI?"

> AI helps extract events and object information from large volumes of video. The forensic correlation itself can also use deterministic evidence such as timestamps and camera topology. This prevents the system from becoming completely dependent on an AI model.

---

### "What if your AI is wrong?"

> The AI output is treated as an analysis result, not as the original evidence. The source frame and metadata remain linked, and the investigator can review the underlying footage.

---

### "Can your system identify a person?"

> Identification is not guaranteed. Face detection and person re-identification are optional analytical capabilities. We distinguish detection, tracking, similarity and confirmed identity rather than treating them as the same thing.

---

### "Why not just watch the videos?"

> Manual review remains possible, but it becomes difficult when investigators have many cameras and long recording periods. Our system reduces the search space by generating an evidence-linked timeline of potentially related events while retaining the original recordings for review.

---

### "What if the timestamps are wrong?"

> That is why timestamp normalization occurs before correlation. Original timestamps are preserved, corrections are recorded separately, and confidence is carried into the correlation result.

---

# 42. Requirement 6 — verdict

### What NTRO asks

```text
Correlate events across cameras.
```

### Does this already exist?

**Yes.**

Multi-camera analytics, tracking, timeline analysis and video search already exist.

### Is AI itself novel?

**No.**

Object detection, tracking and re-identification are established technologies.

### Is our system still meaningful?

**Yes, if we solve the integration problem correctly.**

The architecture becomes:

```text
Proprietary evidence
        ↓
Vendor-specific recovery
        ↓
Normalized evidence
        ↓
Normalized timeline
        ↓
Cross-camera events
        ↓
AI-assisted correlation
        ↓
Evidence-linked incident timeline
```

The important part is that **the correlation result remains traceable to the original forensic evidence**.

---

# 43. The three requirements now connect

We now have:

```text
REQUIREMENT 4
Recovery
     ↓
What footage actually exists?
```

```text
REQUIREMENT 5
Timestamp normalization
     ↓
When did it happen?
```

```text
REQUIREMENT 6
Cross-camera correlation
     ↓
How do events from different cameras relate?
```

So the investigator's workflow becomes:

> **Recover → establish time → connect events.**

And that leads directly into the next NTRO requirement:

# Requirement 7 — Cryptographic Hashing + Evidence Integrity

This is where we answer:

> **How do we prove that the evidence we analyzed is the same evidence we acquired, and that our processing did not silently change the source?**

[1]: https://www.swgde.org/documents/published-complete-listing/20-v-002-swgde-guidelines-for-video-evidence-canvassing-and-collection/?utm_source=chatgpt.com "SWGDE Guidelines for Video Evidence Canvassing and Collection - SWGDE"
[2]: https://www.swgde.org/documents/published-complete-listing/18-v-001-best-practices-for-digital-forensic-video-analysis/?utm_source=chatgpt.com "Best Practices for Digital Forensic Video Analysis - SWGDE"
[3]: https://www.nist.gov/programs-projects/digital-video-exchange-standards?utm_source=chatgpt.com "Digital Video Exchange Standards | NIST"
[4]: https://nvlpubs.nist.gov/nistpubs/ir/2019/NIST.IR.8161r1.pdf?utm_source=chatgpt.com "Recommendation: Closed Circuit Television (CCTV) Digital Video Export Profile – Level 0 (Revision 1)"
[5]: https://www.nist.gov/publications/recommendation-closed-circuit-television-cctv-digital-video-export-profile-level-0?utm_source=chatgpt.com "Recommendation: Closed Circuit Television (CCTV) Digital Video Export Profile - Level 0 (Revision 1) | NIST"

# Requirement 7 — Cryptographic Hashing and Evidence Integrity

NTRO explicitly asks for:

> **Cryptographic hashes (MD5 and SHA-256)**

and expects the system to:

> **verify evidence integrity through cryptographic hashing**

This requirement is much simpler than the recovery/parsing requirements technically, but it is **critical** because everything before and after it depends on being able to prove that the evidence was not silently changed.

NIST defines a hash value as a numerical string used to substantiate the integrity of digital evidence. ([NIST][1])

---

# 1. The basic problem

Imagine we acquire a DVR hard disk.

Original:

```text
DVR HDD
500 GB
```

We create:

```text
Forensic Image
500 GB
```

Then we analyze the image.

A judge could ask:

> "How do you know the image you analyzed is the same evidence you originally acquired?"

We need a way to demonstrate that.

That's where hashing comes in.

---

# 2. What is a hash?

**Hash (a fixed-length digital fingerprint calculated from data).**

Imagine:

```text
DATA
  ↓
Hash algorithm
  ↓
DIGITAL FINGERPRINT
```

For example:

```text
Evidence
    ↓
SHA-256
    ↓
A3F7...9D21
```

If the input changes, the resulting hash normally changes.

NIST describes cryptographic hash functions as producing a digest that can be used to detect whether data has changed since the digest was generated. ([NIST][2])

---

# 3. Extremely simple example

Suppose our evidence contains:

```text
ABC
```

Hash:

```text
SHA-256
→ X
```

Now someone changes it:

```text
ABD
```

Hash:

```text
SHA-256
→ Y
```

Therefore:

```text
X ≠ Y
```

So we know:

> Something changed.

The hash does **not** tell us what changed.

It tells us that the data represented by that hash is different.

---

# 4. What hashing does NOT do

This is extremely important for the PPT.

Hashing does **not**:

* prevent someone from modifying evidence
* prove who modified it
* tell us what the modification was
* magically establish chain of custody
* prove the original evidence was genuine before hashing

SWGDE explicitly notes that hashing protects integrity **from the time the hash is created**, and that proper chain of custody starts from collection, even before the hash is generated. ([SWGDE - SWGDE][3])

So:

```text
Hash ≠ complete forensic protection
```

Instead:

```text
Controlled acquisition
+
documentation
+
hashing
+
secure storage
+
chain of custody
=
strong evidence integrity process
```

---

# 5. Where hashing belongs in OUR architecture

This is important.

We should **not hash only the final recovered MP4**.

We need hashing at multiple stages.

A simplified pipeline:

```text
DVR/NVR HDD
     │
     ▼
Acquisition
     │
     ▼
Forensic Image
     │
     ▼
Hash
     │
     ▼
Verification
     │
     ▼
Working Copy
     │
     ▼
Parsing / Recovery
     │
     ▼
Recovered Evidence
     │
     ▼
Hash
     │
     ▼
Report
```

---

# 6. Acquisition hash

Suppose the original storage contains:

```text
DVR HDD
```

During acquisition:

```text
DVR HDD
   ↓
Forensic acquisition
   ↓
Forensic image
```

We calculate a hash.

This becomes the:

> **Acquisition hash (hash calculated during or around forensic acquisition to identify the acquired data).**

SWGDE recommends hashing acquired data and using the resulting values for later integrity validation. ([SWGDE - SWGDE][4])

---

# 7. Verification hash

After acquisition, we can calculate the hash again.

Conceptually:

```text
HASH #1
calculated during acquisition

vs

HASH #2
calculated after acquisition
```

If:

```text
HASH #1 = HASH #2
```

then the acquired data matches the data represented by the original hash.

SWGDE describes this comparison as verification of the integrity of acquired data. ([SWGDE - SWGDE][4])

---

# 8. Example

Suppose:

```text
Acquisition hash:
A1B2C3...
```

After acquisition:

```text
Verification hash:
A1B2C3...
```

Result:

```text
✓ VERIFIED
```

If:

```text
Acquisition:
A1B2C3...

Verification:
F8D9E1...
```

Then:

```text
✗ INTEGRITY MISMATCH
```

The software should stop and investigate rather than simply continue.

---

# 9. Why NTRO explicitly mentions MD5 AND SHA-256

NTRO asks for:

```text
MD5
+
SHA-256
```

These are two different hash algorithms.

### MD5

**MD5 (Message Digest 5)** = an older cryptographic hash algorithm producing a 128-bit digest.

### SHA-256

**SHA-256 (Secure Hash Algorithm with a 256-bit output)** = a member of the SHA-2 family.

NIST permits SHA-2 algorithms for secure hash applications and recommends SHA-256 at minimum where interoperability is required. ([NIST Computer Security Resource Center][5])

---

# 10. Is MD5 secure?

This is where we need to be precise.

**MD5 is cryptographically broken for collision resistance.**

That means attackers can deliberately construct different data with the same MD5 hash under certain conditions.

SWGDE therefore recommends moving toward SHA-2/SHA-3 for stronger security applications. ([SWGDE - SWGDE][3])

But SWGDE also states that MD5 can remain acceptable for certain **forensic integrity-verification and file-identification purposes**, provided it is used appropriately. ([SWGDE - SWGDE][3])

Therefore:

### Do NOT say:

> "MD5 is secure."

Wrong.

### Say:

> "NTRO explicitly requests MD5 and SHA-256. We can generate both for compatibility with the requirement, while treating SHA-256 as the stronger modern integrity hash."

That's much more defensible.

---

# 11. Why generate both?

There are practical reasons.

Suppose an existing forensic tool produces:

```text
MD5
```

and another produces:

```text
SHA-256
```

If our platform records both:

```text
Evidence ID
MD5
SHA-256
```

we can compare our evidence with multiple existing workflows.

The two hashes also provide independent identifiers.

But we should **not claim that using two hashes magically doubles security**.

---

# 12. SHA-256 should be our primary integrity mechanism

Our proposed approach:

```text
MD5
  +
SHA-256
```

with:

```text
SHA-256 = primary modern integrity value
MD5 = compatibility / forensic identification value
```

That aligns better with current guidance.

NIST states that SHA-2 algorithms such as SHA-256 may be used for secure hash applications. ([NIST Computer Security Resource Center][5])

---

# 13. Hashing a 500 GB image

A common misconception:

> "Can we hash a huge forensic image?"

Yes.

A hash function can process data of arbitrary length and produce a fixed-size digest.

Conceptually:

```text
500 GB
   ↓
SHA-256
   ↓
32-byte digest
```

The output does not become 500 GB.

---

# 14. But hashing takes time

For a very large DVR disk:

```text
1 TB
2 TB
4 TB
```

calculating hashes requires reading the data.

Therefore:

```text
Storage speed
+
CPU
+
I/O
```

affect processing time.

This becomes an actual engineering issue for our project.

---

# 15. Hashing should happen as early as practical

This is one of the strongest points we can use with judges.

NIST recommends hashing evidence as close to collection as possible. ([NIST Publications][6])

SWGDE likewise recommends early hashing and emphasizes that hashes should be securely stored. ([SWGDE - SWGDE][3])

Therefore:

```text
Acquire
 ↓
Hash
 ↓
Preserve
 ↓
Analyze
```

is preferable to:

```text
Acquire
 ↓
Analyze
 ↓
Maybe hash later
```

---

# 16. What if the source DVR is already damaged?

Suppose:

```text
DVR HDD
```

has bad sectors.

We may not be able to read everything.

Then our system must not output:

```text
✓ Complete acquisition
```

if it wasn't complete.

Instead:

```text
Acquisition status:
PARTIAL

Unreadable sectors:
X

Errors:
Y

Hash:
...

Coverage:
...
```

SWGDE specifically warns that verification of an acquisition does not necessarily prove that every area of the source was successfully read, because damaged sectors and other protected areas can prevent acquisition. ([SWGDE - SWGDE][4])

This is very important for our system.

---

# 17. Hash ≠ completeness

This is an excellent judge question.

Imagine:

```text
Original HDD
500 GB
```

Our acquisition only successfully reads:

```text
498 GB
```

We calculate a hash.

The hash is valid for what we acquired.

But that doesn't mean:

> "We acquired the complete original HDD."

Therefore the report must separately record:

```text
Integrity
+
Acquisition completeness
```

---

# 18. Evidence record

Our system should maintain something like:

```text
Evidence ID:
CASE-001-EVID-003

Device:
CP Plus NVR

Model:
[identified model]

Serial number:
[...]

Source:
DVR HDD

Capacity:
1 TB

Acquisition method:
[method]

Acquisition start:
[...]

Acquisition end:
[...]

MD5:
[...]

SHA-256:
[...]

Unreadable sectors:
[...]

Verification:
PASSED
```

This becomes part of the forensic record.

---

# 19. Hash the original evidence or the forensic image?

Ideally, the workflow should distinguish:

### Source data

The actual storage being acquired.

### Forensic image

A bit-level representation of the acquired storage.

### Extracted file

A recovered video.

### Derived artifact

Something generated by analysis.

Each can have its own identifier/hash.

---

# 20. Example

```text
DVR HDD
   │
   │ acquisition
   ▼
E01 image
   │
   ├── SHA-256 A
   │
   ▼
Recovered recording
   │
   ├── SHA-256 B
   │
   ▼
Extracted frame
   │
   └── SHA-256 C
```

Now:

```text
Evidence → Image → Recording → Frame
```

can all be traced.

---

# 21. Why this is useful for our project

Suppose the investigator sees:

```text
18:30:05
Person detected
```

The system should ideally allow:

```text
Incident
 ↓
Event
 ↓
Frame
 ↓
Recovered video
 ↓
Original recording
 ↓
Forensic image
 ↓
Source device
```

and the corresponding evidence identifiers/hashes.

This connects Requirement 7 to the previous requirements.

---

# 22. Hashing recovered footage

Suppose we recover a deleted video.

We should calculate:

```text
Recovered video
      ↓
SHA-256
      ↓
Hash
```

But here's the important distinction:

The hash proves:

> **This recovered output has this exact content.**

It does **not** prove:

> **This video is an authentic representation of the original event.**

Authenticity requires the recovery process, source evidence, provenance and validation.

---

# 23. Recovery + hashing

Imagine:

```text
DVR HDD
 ↓
forensic image
 ↓
filesystem reconstruction
 ↓
fragment recovery
 ↓
video reconstruction
```

At the end:

```text
Recovered video
SHA-256 = ABC...
```

We can prove:

```text
The recovered file has not changed
after this hash was created.
```

But we also need:

```text
Where did the recovered bytes come from?
Which sectors?
Which fragments?
Which metadata?
Which recovery algorithm?
```

That's **provenance**.

---

# 24. Provenance

**Provenance (the record of where evidence came from and what processing happened to it).**

For example:

```text
Recovered video #17

Source image:
CASE001.E01

Source sectors:
1,283,400 – 1,295,201

Filesystem:
Vendor-specific parser X

Recovery method:
Fragment reconstruction

Processing software:
Version 0.1

SHA-256:
ABC123...
```

This is far more useful than simply storing:

```text
video17.mp4
```

---

# 25. Hashing every frame?

No.

That would be unnecessarily expensive.

We should hash:

* forensic image
* extracted evidence files
* important generated artifacts

and preserve their relationship.

Frame-level hashing can be considered for specific workflows, but it should not be the default design unless there is a clear reason.

---

# 26. Hashing the report

We can also hash the final report:

```text
Report.pdf
    ↓
SHA-256
    ↓
REPORT HASH
```

That lets us detect later modification of the report itself.

Again:

> Hashing is an integrity mechanism, not an entire evidence-management system.

---

# 27. Where should hashes be stored?

This is surprisingly important.

Suppose:

```text
Evidence:
ABC...

Hash:
XYZ...
```

are stored on the same writable computer.

An attacker could theoretically replace:

```text
Evidence
+
Hash
```

together.

Now the hash still matches.

NIST explicitly discusses this risk and recommends storing hashes or digital signatures in a manner that prevents unauthorized alteration. ([NIST Publications][6])

---

# 28. Secure hash storage

Possible approaches:

### Option 1 — Protected case database

```text
Evidence
Hash
Metadata
```

stored in controlled case-management infrastructure.

### Option 2 — Signed evidence manifest

Create:

```text
manifest.json
```

containing:

```text
Evidence ID
SHA-256
MD5
metadata
```

Then protect the manifest.

### Option 3 — Hash chain

**Hash chain (a sequence where each record incorporates information from the previous record's hash).**

This can make tampering more detectable.

NIST discusses hash chains as one possible method for protecting stored hashes. ([NIST Publications][6])

---

# 29. What about blockchain?

This is interesting because SIH26150 is under:

> **Blockchain & Cybersecurity**

But we should **not blindly add blockchain**.

NIST explicitly discusses blockchain for digital-evidence management but warns that the overhead of operating a distributed ledger can be too large for many evidence units. ([NIST Publications][6])

Therefore:

### Bad pitch

> "We use blockchain because the theme says Blockchain."

### Better pitch

> "Our primary integrity mechanism is cryptographic hashing and controlled evidence logging. A blockchain-backed audit layer is an optional extension if the deployment environment justifies its overhead."

This is much more technically defensible.

---

# 30. Our proposed integrity architecture

```text
                 ORIGINAL DVR/NVR
                        │
                        ▼
                FORENSIC ACQUISITION
                        │
                        ▼
                 ACQUISITION HASH
                 MD5 + SHA-256
                        │
                        ▼
                 FORENSIC IMAGE
                        │
                        ▼
                  VERIFY HASH
                        │
                 ┌──────┴──────┐
                 │             │
              MATCH          MISMATCH
                 │             │
                 ▼             ▼
             CONTINUE        STOP/FLAG
                 │
                 ▼
             WORKING COPY
                 │
        ┌────────┴─────────┐
        ▼                  ▼
     PARSING             RECOVERY
        │                  │
        └────────┬─────────┘
                 ▼
            OUTPUT FILE
                 │
                 ▼
              SHA-256
                 │
                 ▼
          EVIDENCE MANIFEST
                 │
                 ▼
          CASE REPORT / COC
```

---

# 31. What is the "evidence manifest"?

**Evidence manifest (a structured record describing each evidence item, its hash, origin, processing history and verification state).**

Example:

```json
{
  "evidence_id": "CASE001-VIDEO17",
  "source_image": "CASE001.E01",
  "sha256": "...",
  "md5": "...",
  "recovery_method": "fragment_reconstruction",
  "source_sectors": "...",
  "processing_version": "0.1.0",
  "verification": "passed"
}
```

This is **our proposed implementation**, not an NTRO-prescribed format.

---

# 32. What happens if evidence changes?

Suppose:

```text
Original:
SHA-256 = ABC
```

Later:

```text
Current:
SHA-256 = XYZ
```

Then:

```text
ABC ≠ XYZ
```

Our system should report:

```text
⚠ INTEGRITY MISMATCH
```

and identify:

```text
Evidence ID
Previous hash
Current hash
Verification time
```

---

# 33. But don't automatically say "tampered"

This is another important forensic distinction.

If:

```text
Old hash ≠ new hash
```

we know:

> The data representation changed.

We don't automatically know:

> Someone maliciously tampered with it.

Possible causes include:

* legitimate processing
* file conversion
* metadata modification
* accidental modification
* corruption
* malicious manipulation.

Therefore the correct output is:

```text
INTEGRITY MISMATCH
```

not:

```text
CRIMINAL TAMPERING DETECTED
```

---

# 34. Hashing and video transcoding

Suppose we take:

```text
Original DVR video
```

and convert it to:

```text
MP4
```

The MP4 will have a completely different hash.

That's expected.

So:

```text
Original hash ≠ converted file hash
```

does **not** mean the original was altered.

We need to record the relationship:

```text
Original
   ↓
Conversion
   ↓
Derived copy
```

This is another reason provenance matters.

---

# 35. Hashing and recovered footage

Same issue.

If we reconstruct a deleted video:

```text
Fragments
 ↓
Recovery algorithm
 ↓
Recovered.mp4
```

the recovered file is a **derived artifact**.

Its hash establishes the integrity of that derived artifact.

The system must separately record:

```text
source evidence
+
recovery method
+
source fragments
+
result hash
```

---

# 36. Existing industry practice

Professional forensic tools already use hashing heavily.

The important point for our project is not:

> "We invented evidence hashing."

We absolutely did not.

Instead:

> **We need to implement standard evidence-integrity practices correctly inside our multi-vendor DVR/NVR workflow.**

SWGDE recommends cryptographic hashing of acquired data and documentation of hash values as part of acquisition and validation. ([SWGDE - SWGDE][4])

---

# 37. What NIST says

NIST's digital-evidence preservation guidance is particularly useful for us.

It recommends:

* hashing close to collection
* securely storing hashes
* tracking evidence
* protecting stored hash values
* documenting preservation activities. ([NIST Publications][6])

NIST also warns that merely having a hash isn't enough if both the evidence and its stored hash can be changed. ([NIST Publications][6])

---

# 38. Technology choices

## Python

Can calculate:

```text
MD5
SHA-256
```

using standard cryptographic libraries.

Good for our prototype because:

* simple
* mature
* easy integration
* sufficient performance for prototype-scale evidence.

---

## OpenSSL

**OpenSSL (widely used open-source cryptographic library).**

Can provide cryptographic hashing functionality and is mature.

Potentially useful if we need lower-level integration.

---

## System utilities

Operating systems already provide:

```text
md5sum
sha256sum
```

or equivalents.

Useful for independent verification.

---

# 39. Independent verification is valuable

Suppose our software says:

```text
SHA-256:
ABC123...
```

We can independently run:

```text
sha256sum evidence.E01
```

and compare.

If:

```text
Our tool = ABC123
Independent tool = ABC123
```

then we have a useful validation test.

This is exactly the type of experiment we should perform before claiming the implementation works.

---

# 40. Round 1 experiment

This is extremely easy to demonstrate.

Take a test file:

```text
test-video.mp4
```

Calculate:

```text
MD5
SHA-256
```

Then:

```text
copy file
```

Calculate again:

```text
same hashes
```

Then modify one byte.

Calculate again:

```text
different hashes
```

Show:

```text
Original
SHA-256 = A

Modified
SHA-256 = B

A ≠ B
```

That demonstrates the basic principle.

But for our actual project, we should eventually test this against a **forensic image and recovered CCTV evidence**, not just a random MP4.

---

# 41. Better Round 1 experiment

Use your CP Plus system.

Create:

```text
CCTV recording
```

Acquire a controlled sample.

Then:

```text
Sample
 ↓
Hash
 ↓
Copy
 ↓
Verify
```

Then intentionally modify the working copy.

Our system should show:

```text
ORIGINAL:
SHA-256 = ABC

WORKING COPY:
SHA-256 = XYZ

STATUS:
INTEGRITY MISMATCH
```

That gives us a real project-specific demonstration.

---

# 42. What we should measure

### Hash correctness

Does our calculated hash match independent tools?

### Verification accuracy

Does the system detect intentional modifications?

### Processing speed

How long does hashing take for:

```text
1 GB
10 GB
100 GB
```

### Failure handling

What happens if:

* file disappears?
* file becomes unreadable?
* acquisition is incomplete?
* hash manifest is missing?

---

# 43. Judge question: "Why SHA-256?"

Answer:

> **SHA-256 is part of the SHA-2 family and is an accepted modern secure hash algorithm. NIST permits SHA-2 for secure hash applications and encourages SHA-256 at minimum for interoperability.** ([NIST Computer Security Resource Center][5])

---

# 44. Judge question: "Why MD5 if it is broken?"

Answer:

> **NTRO explicitly specifies MD5 and SHA-256. We therefore support MD5 for compatibility and forensic identification/integrity workflows where appropriate, but SHA-256 is our stronger modern integrity hash. We do not claim MD5 provides modern collision-resistant security.**

That answer is much stronger than pretending MD5 is secure.

SWGDE explicitly discusses this distinction. ([SWGDE - SWGDE][3])

---

# 45. Judge question: "Can a hash prove evidence is genuine?"

Answer:

> **No. A hash can show that data has remained unchanged since the hash was securely established. It cannot by itself prove that the original evidence was genuine before hashing. That is why acquisition procedure, documentation, provenance and chain of custody are also required.**

This is directly consistent with SWGDE/NIST guidance. ([SWGDE - SWGDE][3])

---

# 46. Judge question: "Why not blockchain?"

Answer:

> **Blockchain can provide an additional tamper-evident audit mechanism, but it is not required to perform cryptographic integrity verification. NIST itself notes the implementation overhead of blockchain and indicates that it may not be justified for many evidence-management environments. Our base architecture therefore uses cryptographic hashes plus controlled evidence logging; blockchain can be evaluated as an optional extension.** ([NIST Publications][6])

This is a very good answer for an NTRO problem under the Blockchain & Cybersecurity theme.

---

# 47. Judge question: "What if someone changes both the evidence and the hash?"

Answer:

> **Then the hash alone is insufficient. The hash record itself must be protected. That is why we maintain controlled evidence manifests, audit records and chain-of-custody information separately from the working evidence.**

NIST explicitly identifies this type of risk. ([NIST Publications][6])

---

# 48. Judge question: "What if acquisition is incomplete?"

Answer:

> **The hash does not prove completeness. We separately record acquisition errors, unreadable sectors and acquisition coverage. A verified hash only establishes integrity of the acquired data represented by that hash.**

SWGDE specifically makes this distinction. ([SWGDE - SWGDE][4])

---

# 49. Existing vs our project

| Capability                    |          Existing? | What we do       |
| ----------------------------- | -----------------: | ---------------- |
| MD5                           |                  ✅ | Implement        |
| SHA-256                       |                  ✅ | Implement        |
| Acquisition hashing           |                  ✅ | Implement        |
| Verification hashing          |                  ✅ | Implement        |
| Hash manifests                |          ✅ Concept | Implement        |
| Evidence integrity validation |                  ✅ | Implement        |
| Secure hash storage           |                  ✅ | Design           |
| Chain-of-custody integration  |                  ✅ | Integrate        |
| Hashing recovered files       |                  ✅ | Implement        |
| Provenance linking            |          ✅ Concept | Integrate        |
| Blockchain evidence logging   | ✅ Existing concept | Optional         |
| Hashing itself as novelty     |                  ❌ | **Do not claim** |

---

# 50. What is important for SIH26150?

This requirement is **not a novelty opportunity**.

And that's completely fine.

NTRO explicitly asks for it.

Our job is to implement it correctly and integrate it with the rest of the system.

The important architecture is:

```text
SOURCE
  ↓
ACQUISITION
  ↓
HASH
  ↓
FORENSIC IMAGE
  ↓
VERIFY
  ↓
WORKING COPY
  ↓
ANALYSIS
  ↓
DERIVED EVIDENCE
  ↓
HASH
  ↓
PROVENANCE
  ↓
REPORT
```

---

# 51. Requirement 7 — final verdict

### What NTRO asks

```text
MD5
+
SHA-256
+
evidence integrity verification
```

### Is this already solved?

**Yes. Completely established technology.**

### Should we claim novelty?

**No.**

### What should we build?

A proper integrity layer that:

1. hashes acquired evidence;
2. generates MD5 + SHA-256 as requested;
3. verifies acquisition;
4. preserves original hashes;
5. hashes important derived evidence;
6. records processing history;
7. detects integrity mismatches;
8. records acquisition errors;
9. links hashes to evidence provenance;
10. integrates with chain of custody.

### Most important limitation

> **A hash proves integrity from the point where the hash was securely established. It does not, by itself, prove authenticity, completeness or legal admissibility.**

That distinction should absolutely be in our PPT.

---

## Clean sources for our project

**NIST — Hash Functions / SHA-2 policy**
[https://csrc.nist.gov/projects/hash-functions/nist-policy-on-hash-functions](https://csrc.nist.gov/projects/hash-functions/nist-policy-on-hash-functions) ([NIST Computer Security Resource Center][5])

**NIST — Secure Hash Standard**
[https://www.nist.gov/publications/secure-hash-standard](https://www.nist.gov/publications/secure-hash-standard) ([NIST][2])

**NIST — Digital Evidence Preservation**
[https://nvlpubs.nist.gov/nistpubs/ir/2022/NIST.IR.8387.pdf](https://nvlpubs.nist.gov/nistpubs/ir/2022/NIST.IR.8387.pdf) ([NIST Publications][6])

**NIST — Digital Evidence**
[https://www.nist.gov/digital-evidence](https://www.nist.gov/digital-evidence) ([NIST][7])

**SWGDE — MD5/SHA-1 Position for Digital & Multimedia Forensics**
[https://www.swgde.org/documents/published-complete-listing/swgde-position-on-the-use-of-md5-and-sha1-hash-algorithms-in-digital-and-multimedia-forensics/](https://www.swgde.org/documents/published-complete-listing/swgde-position-on-the-use-of-md5-and-sha1-hash-algorithms-in-digital-and-multimedia-forensics/) ([SWGDE - SWGDE][3])

**SWGDE — Best Practices for Computer Forensic Acquisition**
[https://www.swgde.org/documents/published-complete-listing/17-f-002-2-1/](https://www.swgde.org/documents/published-complete-listing/17-f-002-2-1/) ([SWGDE - SWGDE][4])

---

### Pipeline so far

```text
1. ACQUISITION
        ↓
2. DEVICE IDENTIFICATION
        ↓
3. FILESYSTEM / FORMAT PARSING
        ↓
4. VIDEO + METADATA EXTRACTION
        ↓
5. DELETED / DAMAGED RECOVERY
        ↓
6. TIMESTAMP NORMALIZATION
        ↓
7. CROSS-CAMERA CORRELATION
        ↓
8. HASHING + INTEGRITY VALIDATION   ← JUST COMPLETED
        ↓
9. CHAIN OF CUSTODY
        ↓
10. STANDARDIZED REPORTING
        ↓
11. AI ANALYTICS
        ↓
12. MULTI-VENDOR EXPANSION
```

**Next: Requirement 8 — Chain of Custody.**

This is where we connect the hashes and provenance into a defensible record of **who collected the evidence, who handled it, when it moved, what was done to it, and where it is now.**

[1]: https://www.nist.gov/glossary-term/38726?utm_source=chatgpt.com "Hash, Hash Value | NIST"
[2]: https://www.nist.gov/publications/secure-hash-standard?utm_source=chatgpt.com "Secure Hash Standard | NIST"
[3]: https://www.swgde.org/documents/published-complete-listing/swgde-position-on-the-use-of-md5-and-sha1-hash-algorithms-in-digital-and-multimedia-forensics/?utm_source=chatgpt.com "SWGDE Position on the Use of MD5 and SHA1 Hash Algorithms in Digital and Multimedia Forensics - SWGDE"
[4]: https://www.swgde.org/documents/published-complete-listing/17-f-002-2-1/?utm_source=chatgpt.com "Best Practices for Computer Forensic Acquisition - SWGDE"
[5]: https://csrc.nist.gov/projects/hash-functions/nist-policy-on-hash-functions?utm_source=chatgpt.com "Hash Functions | CSRC"
[6]: https://nvlpubs.nist.gov/nistpubs/ir/2022/NIST.IR.8387.pdf?utm_source=chatgpt.com "Digital Evidence Preservation: Considerations for Evidence Handlers"
[7]: https://www.nist.gov/digital-evidence?utm_source=chatgpt.com "Digital evidence | NIST"

# Requirement 9 — Chain of Custody

This is one of the most important requirements in the entire project because it answers a different question from hashing.

**Hashing asks:**

> "Has this data changed?"

**Chain of custody asks:**

> "Where did this evidence come from, who handled it, when was it handled, and what happened to it?"

SWGDE's current digital-evidence collection guidance explicitly requires contemporaneous chain-of-custody documentation and an evidence inventory, including a unique evidence identifier, receipt date/time, transfers, and the people taking possession. ([SWGDE - SWGDE][1])

---

# 1. Simple example

Imagine police collect a DVR from a shop.

```text
Shop DVR
   ↓
Officer A collects it
   ↓
Forensic laboratory
   ↓
Examiner B
   ↓
Forensic workstation
   ↓
Evidence storage
```

A court could ask:

> "How do you know this is the same DVR that was collected?"

We need a record.

```text
Evidence ID:
CASE-001-DVR-01

Collected:
24 Aug 2026, 10:32

Collected by:
Officer A

Location:
ABC Store

Transferred to:
Forensic Lab

Received:
24 Aug 2026, 14:18

Received by:
Examiner B
```

That is the basic idea of **chain of custody**.

---

# 2. What NTRO is asking for

The PS specifically asks the platform to:

> **maintain chain-of-custody records**

So this is not something we invented.

It is an explicit requirement.

The system needs to maintain a history of evidence handling throughout the investigation.

---

# 3. Chain of custody ≠ hashing

This distinction needs to be crystal clear.

| Hashing                               | Chain of custody                          |
| ------------------------------------- | ----------------------------------------- |
| Detects data changes                  | Records evidence handling                 |
| Mathematical operation                | Documentation/process                     |
| Produces a digest                     | Produces an evidence history              |
| Can verify integrity                  | Establishes provenance and accountability |
| Doesn't identify who handled evidence | Records people/actions                    |
| Doesn't replace documentation         | Includes documentation                    |

SWGDE treats hashing and chain-of-custody documentation as separate components of evidence handling. ([SWGDE - SWGDE][1])

---

# 4. What does the chain actually contain?

At minimum, we should record:

```text
Evidence ID
Case ID
Description
Source device
Collection location
Collection date/time
Collector
Initial condition
Transfer history
Current custodian
Storage location
Acquisition method
Hash values
Processing activities
Access history
Final disposition
```

SWGDE specifically recommends recording the evidence identifier, receipt date/time, transfers and the identity of each person taking possession. It also recommends detailed collection notes covering software, logs, reports, screenshots, data size, filenames and hash values. ([SWGDE - SWGDE][1])

---

# 5. The complete chain

For our DVR project:

```text
DVR/NVR
   │
   ▼
COLLECTION
   │
   ▼
EVIDENCE REGISTRATION
   │
   ▼
ACQUISITION
   │
   ▼
HASH
   │
   ▼
FORENSIC IMAGE
   │
   ▼
SECURE STORAGE
   │
   ▼
EXAMINATION
   │
   ▼
RECOVERY
   │
   ▼
ANALYSIS
   │
   ▼
REPORT
```

At each important transition:

```text
WHO?
WHEN?
WHAT?
WHY?
WHERE?
```

should be recorded.

---

# 6. Input

The chain-of-custody layer receives information from practically every other layer.

```text
Evidence acquisition
       │
       ├── device information
       ├── collector
       ├── date/time
       ├── acquisition method
       ├── hash
       └── acquisition logs

Parsing
       │
       └── processing record

Recovery
       │
       └── recovery method

Analysis
       │
       └── analyst + software + operation

Reporting
       │
       └── final evidence record
```

So chain of custody is not an isolated feature.

It sits across the entire architecture.

---

# 7. Evidence registration

The first thing we should do when evidence enters the system:

```text
Create Case
      ↓
Create Evidence ID
      ↓
Record source
      ↓
Record condition
      ↓
Record collector
      ↓
Record time
```

Example:

```text
CASE-2026-001

Evidence:
CASE-2026-001-E001

Type:
DVR/NVR

Vendor:
CP Plus

Model:
X

Serial:
X

Location:
ABC Building

Condition:
Powered off

Storage:
1 TB HDD
```

---

# 8. Why record the device condition?

Imagine two situations.

### Situation A

```text
DVR
Powered OFF
```

### Situation B

```text
DVR
Powered ON
Recording active
```

The acquisition procedure may be completely different.

SWGDE recommends documenting the device state and physical characteristics during collection. ([SWGDE - SWGDE][1])

So our evidence record should contain:

```text
Power state
Network state
Visible screen
Connections
Physical damage
Serial number
Storage devices
```

where applicable.

---

# 9. Photographing evidence

A professional workflow may also record:

```text
DVR front
DVR rear
serial number
connections
HDD
cabling
screen state
physical damage
```

These aren't just decorative photographs.

They establish the condition and context of the evidence when collected.

SWGDE recommends photographs or written descriptions of the collection location, device state and physical characteristics. ([SWGDE - SWGDE][1])

---

# 10. Transfer event

Suppose:

```text
Officer A
```

hands the DVR to:

```text
Examiner B
```

The system records:

```text
Transfer ID:
T001

Evidence:
CASE-001-E001

From:
Officer A

To:
Examiner B

Date:
24 Aug 2026

Time:
14:18

Reason:
Forensic examination

Location:
Forensic laboratory
```

Then:

```text
Officer A → Examiner B
```

becomes a permanent event in the evidence history.

---

# 11. Multiple transfers

Suppose:

```text
Officer A
    ↓
Lab B
    ↓
Examiner C
    ↓
Secure storage
    ↓
Examiner C
```

The system shouldn't overwrite the previous record.

It should append events.

```text
T001
A → B

T002
B → C

T003
C → Storage

T004
Storage → C
```

This creates an **audit trail (a chronological record of actions performed on an item).**

---

# 12. Why append-only matters

Bad design:

```text
Current Owner:
Examiner C
```

This tells us nothing about the previous history.

Better:

```text
History:
A → B
B → C
C → Storage
Storage → C
```

We preserve the entire history.

---

# 13. What happens when we analyze evidence?

Suppose Examiner C opens:

```text
CASE-001.E01
```

The system can record:

```text
Action:
Opened forensic image

User:
Examiner C

Time:
...

Purpose:
Filesystem analysis

Software:
Our platform v0.1
```

This is useful because chain of custody isn't only about physical movement.

It also needs to account for evidence handling and processing.

---

# 14. Processing history

Suppose we perform:

```text
DVR image
 ↓
filesystem parser
 ↓
recording extraction
 ↓
deleted recovery
 ↓
timestamp normalization
 ↓
AI analysis
```

Our system should know:

```text
Who performed it?
When?
Using what software?
Using what version?
What input?
What output?
```

Example:

```text
Operation:
Deleted-video recovery

Input:
CASE001.E01

Tool:
DVRForensic v0.2

Module:
CPPlusParser

Algorithm:
Fragment reconstruction

Operator:
Examiner C

Timestamp:
...

Output:
REC-017.mp4

Output SHA-256:
...
```

This becomes extremely useful for reproducibility.

---

# 15. Provenance

**Provenance (the history showing where an evidence item came from and how it became the current artifact).**

For example:

```text
Source HDD
   ↓
Forensic image
   ↓
Filesystem region
   ↓
Recovered fragments
   ↓
Recovered video
   ↓
Frame
   ↓
AI event
```

The investigator should be able to trace the final event backwards.

---

# 16. Example

Our UI could show:

```text
EVENT #1042

Person detected
Camera: CP-03
Time: 18:32:14

SOURCE
   ↓
Recovered Video #17
   ↓
Recovery Operation #08
   ↓
Forensic Image E001
   ↓
Original Evidence E001
```

This is powerful because the AI result isn't floating independently.

It is attached to its evidence source.

---

# 17. This connects directly to Requirement 7

Remember:

```text
Requirement 7
Hashing
```

gave us:

```text
Evidence:
SHA-256 = ABC...
```

Now:

```text
Requirement 9
Chain of custody
```

says:

```text
Who created this hash?
When?
For which evidence?
Where was the evidence?
Who had access?
What happened afterwards?
```

So:

```text
HASH
+
CHAIN OF CUSTODY
```

is significantly stronger than either alone.

---

# 18. Secure storage

Chain-of-custody records themselves need protection.

Imagine:

```text
Evidence
+
Chain-of-custody database
```

are both freely editable.

An unauthorized person could alter the history.

So we need:

* authentication
* authorization
* restricted access
* audit logs
* protected storage
* backups.

SWGDE's current guidance specifically says security is important for maintaining chain of custody and preventing unauthorized access or tampering, and recommends physical and logical controls. ([SWGDE - SWGDE][2])

---

# 19. Role-based access

**Role-based access control (permissions based on a user's assigned role).**

Example:

```text
Administrator
    ↓
manage users

Collector
    ↓
register evidence

Examiner
    ↓
analyse evidence

Reviewer
    ↓
review reports
```

An examiner shouldn't necessarily be able to:

```text
delete evidence
```

or:

```text
rewrite collection history.
```

---

# 20. Better architecture

```text
                    CASE
                     │
                     ▼
              EVIDENCE RECORD
                     │
       ┌─────────────┼──────────────┐
       ▼             ▼              ▼
    Device         Hashes       Collection
    metadata                    details
       │             │              │
       └─────────────┼──────────────┘
                     ▼
              CHAIN OF CUSTODY
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
     Transfers     Actions      Storage
        │            │            │
        └────────────┼────────────┘
                     ▼
                AUDIT LOG
```

---

# 21. Database design

For our prototype, a relational database is probably enough.

**Relational database (a database that stores structured information in related tables).**

Possible tables:

```text
cases
evidence
custodians
transfers
acquisitions
hashes
processing_events
artifacts
users
audit_logs
```

Example:

```text
evidence
---------
evidence_id
case_id
device_id
description
status
created_at
```

Then:

```text
transfers
---------
transfer_id
evidence_id
from_user
to_user
timestamp
reason
```

---

# 22. Why not blockchain?

This is where our project theme may tempt us.

We could theoretically store every custody event on a blockchain.

```text
Evidence
 ↓
Hash
 ↓
Blockchain transaction
 ↓
Immutable record
```

But that doesn't automatically make the system better.

NIST's digital-evidence preservation guidance discusses blockchain as a possible mechanism but also highlights the implementation overhead and the fact that it may not be justified for every evidence-management environment. ([NIST][3])

Therefore:

### Don't say:

> "Blockchain guarantees evidence integrity."

That's too simplistic.

Instead:

> "Cryptographic hashing and controlled audit records form the base integrity mechanism. A blockchain or other append-only ledger can be evaluated as an additional tamper-evident audit layer where the deployment environment justifies it."

Much better.

---

# 23. Could we use a hash chain instead?

Possibly.

A **hash chain (a sequence of records where each record incorporates the previous record's hash)** could make later modification easier to detect.

Example:

```text
Event 1
Hash = A

Event 2
Hash = Hash(Event2 + A)
       = B

Event 3
Hash = Hash(Event3 + B)
       = C
```

If Event 2 changes:

```text
B changes
 ↓
C becomes invalid
```

This is an interesting lightweight alternative to blockchain.

But again:

> **We should test it before claiming it as our chosen architecture.**

---

# 24. Digital signatures

Another option is:

**Digital signature (a cryptographic mechanism allowing a holder of a private key to sign data and allowing others to verify that signature).**

For example:

```text
Evidence manifest
      ↓
SHA-256
      ↓
Digital signature
```

This can help establish that the manifest was signed by an authorized key.

Potentially useful for:

```text
final evidence manifest
final report
custody record
```

But key management becomes another problem.

---

# 25. What industry does

Professional forensic platforms already implement evidence management and audit mechanisms.

The important point:

❌ We cannot claim chain of custody as our invention.

Instead:

> **We need to integrate established evidence-handling principles into a vendor-agnostic DVR/NVR workflow.**

This is exactly what the NTRO requirement demands.

---

# 26. India

India already has established digital-forensics and evidence-handling infrastructure.

The Ministry of Home Affairs' forensic modernization documentation includes digital-forensic capabilities and infrastructure requirements, demonstrating that digital evidence handling is already an operational forensic function rather than a theoretical requirement. ([SWGDE - SWGDE][4])

But we need to be careful:

> **Do not claim that a specific Indian forensic laboratory uses our proposed software architecture unless we find direct evidence.**

Our research can establish:

```text
India:
Digital forensics exists
+
forensic evidence handling exists
+
CCTVs are routinely used
```

without falsely claiming:

```text
India already uses our exact chain-of-custody architecture.
```

---

# 27. What should our system record?

I would divide it into five groups.

### A. Collection

```text
Evidence ID
Collector
Location
Date/time
Device state
Photos
Description
```

### B. Acquisition

```text
Acquisition method
Source device
Image type
Start/end
Errors
MD5
SHA-256
```

### C. Transfers

```text
From
To
Date/time
Location
Reason
```

### D. Processing

```text
Operation
Input
Output
Software
Version
Operator
Timestamp
Parameters
```

### E. Finalization

```text
Report
Final hashes
Reviewer
Export time
Final disposition
```

---

# 28. Proposed input → processing → output

## INPUT

```text
Case
+
Evidence
+
Users
+
Collection information
+
Hash information
+
Processing events
```

↓

## PROCESSING

```text
Register evidence
        ↓
Assign unique ID
        ↓
Record custody event
        ↓
Hash evidence
        ↓
Record transfer
        ↓
Record analysis
        ↓
Record derived artifacts
        ↓
Record reviewer
```

↓

## OUTPUT

```text
Complete evidence history
+
Audit trail
+
Evidence provenance
+
Integrity information
+
Custody report
```

---

# 29. Example final record

```text
CASE: NTRO-001

EVIDENCE: E001

Source:
CP Plus NVR

Collected:
24-Aug-2026 10:32

Collector:
User-001

Initial state:
Powered off

Acquisition:
Forensic image

MD5:
XXXXXXXX

SHA-256:
YYYYYYYY

Transferred:
User-001 → Examiner-002

Time:
24-Aug-2026 14:18

Processing:
Filesystem parsing

Operator:
Examiner-002

Processing:
Video recovery

Output:
REC-017

Output SHA-256:
ZZZZZZZZ

Reviewed:
Reviewer-001
```

A judge can follow the story.

---

# 30. What happens if someone tries to edit it?

Suppose:

```text
Transfer T002
```

was originally:

```text
Examiner A → Examiner B
```

Someone changes it to:

```text
Examiner A → Examiner C
```

The system should ideally:

```text
NOT overwrite T002
```

Instead:

```text
Original record preserved
+
modification attempt recorded
+
authorized correction workflow
```

This is much better than allowing direct editing.

---

# 31. Correction vs deletion

Real systems need corrections.

Suppose the collector entered:

```text
10:32
```

but it should have been:

```text
10:23
```

We should not simply edit the old record invisibly.

Better:

```text
Original:
10:32

Correction:
10:23

Corrected by:
User X

Reason:
Entry error

Time corrected:
...
```

That preserves history.

---

# 32. Audit log

**Audit log (a chronological record of system actions).**

Example:

```text
10:32 User A created E001
10:34 User A uploaded evidence metadata
10:35 User A calculated SHA-256
14:18 User B received E001
15:02 User B opened E001
15:45 User B started recovery
16:21 User B exported REC-017
```

This is different from the formal custody record but supports it.

---

# 33. Round 1 prototype

We don't need a complete forensic laboratory management system.

Build:

```text
CASE CREATION
     ↓
EVIDENCE REGISTRATION
     ↓
TRANSFER
     ↓
HASH
     ↓
ANALYSIS EVENT
     ↓
EXPORT
```

Then show:

### Screen 1

```text
CASE
NTRO-001
```

### Screen 2

```text
Evidence:
E001

CP Plus NVR
```

### Screen 3

```text
Chain of Custody

10:32
Collected by A

14:18
Transferred A → B

15:02
Analysis started
```

### Screen 4

```text
SHA-256
ABCDEF...

Integrity:
VERIFIED
```

That's enough to demonstrate the concept.

---

# 34. Stronger demo

This would be even better:

1. Create evidence.
2. Generate hash.
3. Transfer evidence.
4. Perform an analysis operation.
5. Export recovered video.
6. Show the full timeline.
7. Click the recovered video.
8. Show its source.
9. Show its hash.
10. Show who processed it.

So:

```text
Recovered Video
       ↓
Source
       ↓
Forensic Image
       ↓
Evidence ID
       ↓
Custody History
```

That connects the entire system.

---

# 35. Judge question: "Why do you need chain of custody?"

Answer:

> **Because integrity and handling history are different. A hash can show that data has changed since the hash was established, but it does not record who collected, transferred, accessed or processed the evidence. Chain-of-custody records provide that history.**

Supported directly by SWGDE's guidance separating hashing from chain-of-custody documentation. ([SWGDE - SWGDE][1])

---

# 36. Judge question: "Can blockchain replace chain of custody?"

Answer:

> **No. Blockchain can provide a tamper-evident record of transactions, but it does not replace the underlying evidence collection procedure, identification of custodians, physical handling records, acquisition documentation or forensic examination records.**

---

# 37. Judge question: "Can the investigator edit the chain?"

Answer:

> **Authorized corrections may be necessary, but the original record should not be silently overwritten. Corrections should generate a new audit event recording who made the change, when and why.**

This is our proposed system behavior and should be presented as such, not as an existing universal standard.

---

# 38. Judge question: "What if someone steals the database?"

Answer:

Our architecture should separate:

```text
Evidence storage
+
metadata
+
custody records
+
authentication
+
backups
```

and restrict access.

We can also protect important manifests using:

```text
SHA-256
+
digital signatures
```

or potentially:

```text
hash chain / append-only ledger
```

depending on testing.

SWGDE explicitly recommends physical and logical security controls for evidence and forensic images. ([SWGDE - SWGDE][2])

---

# 39. Judge question: "Does chain of custody make evidence legally admissible?"

**No.**

This is another claim we must avoid.

Our software can:

```text
support
document
preserve
validate
```

the evidence-handling process.

It cannot guarantee:

> "This evidence is legally admissible."

Legal admissibility depends on jurisdiction, procedure, authentication, circumstances and other factors.

NIST's preservation guidance treats preservation and evidence management as technical/operational concerns rather than making blanket legal-admissibility guarantees. ([NIST][3])

---

# 40. Existing vs our project

| Capability                     | Already exists? | Our position     |
| ------------------------------ | --------------: | ---------------- |
| Chain-of-custody documentation |               ✅ | Implement        |
| Evidence inventory             |               ✅ | Implement        |
| Evidence IDs                   |               ✅ | Implement        |
| Transfer records               |               ✅ | Implement        |
| Custodian records              |               ✅ | Implement        |
| Acquisition records            |               ✅ | Integrate        |
| Hash records                   |               ✅ | Integrate        |
| Audit logs                     |               ✅ | Implement        |
| Role-based access              |               ✅ | Implement        |
| Evidence provenance            |       ✅ concept | Integrate deeply |
| Blockchain audit trail         |       ✅ concept | Optional         |
| Chain of custody as novelty    |               ❌ | **Do not claim** |

---

# 41. What is actually important for SIH26150?

The individual technology isn't novel.

The interesting engineering problem is **connecting it to the multi-vendor forensic pipeline**.

For example:

```text
CP Plus HDD
     ↓
Acquisition
     ↓
Hash
     ↓
Parser
     ↓
Recovery
     ↓
Recovered video
     ↓
Hash
     ↓
AI analysis
     ↓
Event
     ↓
Report
```

Every stage retains:

```text
Evidence ID
+
source
+
operator
+
time
+
processing history
+
hash
```

So the investigator doesn't just get:

```text
video.mp4
```

They get:

```text
video.mp4
   │
   ├── source evidence
   ├── acquisition
   ├── recovery method
   ├── hash
   ├── analyst
   ├── processing history
   └── custody history
```

That is the architecture we should be aiming for.

---

# 42. Requirement 9 — Final verdict

### What NTRO asks

**Maintain chain-of-custody records.**

### Is this already solved?

**Yes.**

There are established digital-forensics practices and standards/guidance for it. SWGDE's current guidance explicitly covers chain-of-custody documentation, evidence inventories, transfers, custodians, collection notes and security. ([SWGDE - SWGDE][1])

### Is it novel?

**No.**

Do not claim it.

### What should we build?

A chain-of-custody subsystem tightly connected to our DVR/NVR evidence pipeline:

```text
Evidence
 ↓
Unique ID
 ↓
Collection
 ↓
Acquisition
 ↓
Hash
 ↓
Transfer
 ↓
Processing
 ↓
Recovery
 ↓
Analysis
 ↓
Derived evidence
 ↓
Report
```

### Most important principle

> **Never silently rewrite evidence history.**

Every important action should create a traceable record.

---

## Clean sources

**SWGDE — Best Practices for Digital Evidence Collection, current guidance**
[https://www.swgde.org/documents/published-complete-listing/18-f-002-best-practices-for-digital-evidence-collection/](https://www.swgde.org/documents/published-complete-listing/18-f-002-best-practices-for-digital-evidence-collection/)

**SWGDE — Best Practices for Digital Evidence Collection 18-F-002-2.0**
[https://www.swgde.org/documents/published-complete-listing/18-f-002-2-0/](https://www.swgde.org/documents/published-complete-listing/18-f-002-2-0/)

**SWGDE — Best Practices for Computer Forensic Acquisitions**
[https://www.swgde.org/17-f-002/](https://www.swgde.org/17-f-002/)

**NIST — Digital Evidence Preservation: Considerations for Evidence Handlers**
[https://www.nist.gov/publications/digital-evidence-preservation-considerations-evidence-handlers](https://www.nist.gov/publications/digital-evidence-preservation-considerations-evidence-handlers)

**NIST — Full NISTIR 8387 PDF**
[https://nvlpubs.nist.gov/nistpubs/ir/2022/NIST.IR.8387.pdf](https://nvlpubs.nist.gov/nistpubs/ir/2022/NIST.IR.8387.pdf)

---

## Pipeline status

```text
1.  Evidence Acquisition                 ✓
2.  Device / Model Identification       ✓
3.  Filesystem / Format Parsing         ✓
4.  Video / Metadata Extraction         ✓
5.  Deleted / Damaged Recovery          ✓
6.  Timestamp Normalization             ✓
7.  Cross-Camera Correlation            ✓
8.  Hashing / Integrity Validation      ✓
9.  Chain of Custody                    ✓ ← JUST COMPLETED
10. Standardized Reporting              → NEXT
11. AI-Based Video Analytics
12. Multi-Vendor / OEM Support
```

**Next: Requirement 10 — Standardized Forensic Reporting.**

[1]: https://www.swgde.org/documents/published-complete-listing/18-f-002-best-practices-for-digital-evidence-collection/?utm_source=chatgpt.com "Best Practices for Digital Evidence Collection - SWGDE"
[2]: https://www.swgde.org/documents/published-complete-listing/18-f-002-2-0/?utm_source=chatgpt.com "Best Practices for Digital Evidence Collection - SWGDE"
[3]: https://www.nist.gov/publications/digital-evidence-preservation-considerations-evidence-handlers?utm_source=chatgpt.com "Digital Evidence Preservation: Considerations for Evidence Handlers | NIST"
[4]: https://www.swgde.org/documents/published-by-committee/forensics/?utm_source=chatgpt.com "Forensics - SWGDE"

# Requirement 10 — Standardized Forensic Reporting

This is the requirement where everything we have done so far becomes a **usable forensic result**.

NTRO asks for:

* standardized reporting
* comprehensive forensic reports
* validation reports
* user documentation
* final project documentation

The important point is that the report is **not just a PDF containing screenshots**.

It needs to explain:

> **What evidence was received → what was done → what was recovered → how it was validated → what the examiner concluded.**

SWGDE's forensic-reporting requirements say a digital/multimedia forensic examination report should document the case, purpose, submitted evidence, processes, results, supporting data, conclusions where applicable, evidence disposition, and authorization. It also says results should be understandable to a layperson. ([SWGDE - SWGDE][1])

---

# 1. Why NTRO needs this

Imagine our system successfully recovers:

```text
RECOVERED_VIDEO_017.mp4
```

That's not enough.

An investigator needs to know:

```text
Where did this come from?
Which DVR?
Which camera?
Which storage?
Was it deleted?
How was it recovered?
Was the recovery successful?
Was the timestamp changed?
What was the original timestamp?
What hash does the output have?
Who performed the analysis?
What software version was used?
Can someone reproduce it?
```

The report is where all of that becomes one understandable record.

---

# 2. The complete pipeline

Our architecture now becomes:

```text
DVR/NVR
   ↓
Acquisition
   ↓
Device identification
   ↓
Filesystem parsing
   ↓
Video recovery
   ↓
Timestamp normalization
   ↓
Cross-camera analysis
   ↓
Integrity validation
   ↓
Chain of custody
   ↓
REPORT
```

The report is therefore the **final presentation layer for the forensic investigation**.

---

# 3. What goes INTO the reporting layer?

The reporting engine receives information from practically every previous module.

```text
Evidence information
        │
Acquisition information
        │
Device information
        │
Filesystem findings
        │
Recovered recordings
        │
Metadata
        │
Timeline
        │
Cross-camera events
        │
AI results
        │
Hashes
        │
Chain of custody
        │
Processing logs
        │
        ▼
   REPORT GENERATOR
```

---

# 4. What comes OUT?

Potential outputs:

```text
PDF forensic report
HTML report
CSV evidence table
JSON machine-readable report
Evidence manifest
Recovered video files
Timeline
Hash manifest
Chain-of-custody record
```

For the SIH prototype, the most important visible output is probably:

> **A standardized forensic investigation report.**

---

# 5. What does "standardized" actually mean?

It does **not** necessarily mean:

> Everyone in the world must use exactly the same PDF design.

SWGDE explicitly says its minimum report elements do not prescribe a specific format; organizations may define their own format. ([SWGDE - SWGDE][1])

For us, standardized means:

```text
Same information structure
+
same terminology
+
same evidence fields
+
same processing records
+
same validation fields
```

regardless of whether the source was:

```text
CP Plus
Hikvision
Dahua
Uniview
Matrix
...
```

---

# 6. This is where our multi-vendor architecture matters

Imagine two investigations.

### Investigation A

```text
CP Plus
```

Output from parser:

```text
CP Plus recording
camera = 03
timestamp = ...
```

### Investigation B

```text
Hikvision
```

Output:

```text
Hikvision recording
channel = 03
time = ...
```

The internal formats are different.

But our reporting layer should produce:

```text
Evidence ID
Camera
Original timestamp
Normalized timestamp
Recording
Recovery status
Hash
Confidence
Source
```

The report doesn't care how complicated the vendor-specific parser was.

---

# 7. The normalized evidence model

This is one of the most useful design decisions in the project.

Instead of every vendor producing completely different output:

```text
CP Plus → weird proprietary structure
Hikvision → different structure
Dahua → different structure
```

we convert them into a common representation.

Example:

```text
EvidenceRecord

Vendor
Model
Camera ID
Recording ID
Original timestamp
Normalized timestamp
Duration
Video format
Resolution
Recovery status
Source location
Hash
Confidence
```

Then:

```text
Vendor Parser
     ↓
Normalized Evidence Record
     ↓
Report
```

This is a major architectural advantage.

It does **not** mean normalized reporting itself is novel. The engineering value is making it work across the proprietary inputs required by this PS.

---

# 8. What should the report contain?

A good report structure would be:

```text
1. Case information
2. Examination request
3. Evidence inventory
4. Device information
5. Acquisition details
6. Integrity / hashes
7. Processing performed
8. Recovered recordings
9. Metadata
10. Timeline
11. Cross-camera findings
12. AI analysis
13. Validation
14. Limitations
15. Conclusions
16. Chain of custody
17. Evidence disposition
18. Appendices
```

This maps very well to established forensic reporting guidance.

SWGDE's minimum requirements specifically include case identifier, request details, evidence identification, processes/results, conclusions where appropriate, disposition and authorization. ([SWGDE - SWGDE][1])

---

# 9. Section 1 — Case information

Example:

```text
FORENSIC VIDEO EXAMINATION REPORT

Case ID:
CASE-2026-001

Evidence ID:
E001

Examiner:
Varun

Organization:
[Organization]

Date:
24 August 2026

Report Version:
1.0
```

The report should have a unique case identifier.

---

# 10. Section 2 — Examination request

The report should answer:

```text
Why was this evidence examined?
```

Example:

> Determine whether surveillance recordings from the supplied DVR contain footage corresponding to the requested time period and recover relevant recordings where possible.

SWGDE specifically requires the report to identify the purpose and scope of the examination and details of the request. ([SWGDE - SWGDE][1])

---

# 11. Section 3 — Evidence inventory

Example:

| Evidence ID | Type | Vendor  | Model | Serial | Storage  |
| ----------- | ---- | ------- | ----- | ------ | -------- |
| E001        | NVR  | CP Plus | X     | XXXXX  | 1 TB HDD |

The report should uniquely identify each submitted/collected item.

SWGDE recommends information such as make, model, serial number, markings and hash values where applicable. ([SWGDE - SWGDE][1])

---

# 12. Section 4 — Device information

Our system should automatically populate:

```text
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
```

But:

> **If something cannot be reliably identified, report "Not determined" rather than guessing.**

This is important for our project.

---

# 13. Section 5 — Acquisition

The report should explain:

```text
What was acquired?
How was it acquired?
When?
By whom?
What method?
Was acquisition complete?
Were errors encountered?
```

Example:

```text
Acquisition method:
Forensic disk imaging

Image:
CASE001.E01

Start:
10:32:14

End:
13:51:08

Unreadable sectors:
12

Status:
PARTIAL
```

This is much better than:

```text
Acquisition successful
```

because it exposes limitations.

---

# 14. Section 6 — Hashes

Example:

```text
Evidence:
E001

MD5:
A1B2C3...

SHA-256:
8F92...

Verification:
PASSED
```

This connects directly to Requirement 8.

---

# 15. Section 7 — Processing history

The report should explain what the system actually did.

Example:

```text
10:40
Device identified as CP Plus

10:45
Filesystem analysis started

11:12
Recording index reconstructed

11:37
Deleted recording candidates identified

12:01
Video fragments reconstructed

12:14
Timestamp normalization performed

12:31
Cross-camera correlation performed
```

This is extremely useful for reproducibility.

SWGDE says documentation should describe the processes performed sufficiently that a similarly trained analyst could replicate the techniques and reach a comparable conclusion. ([SWGDE - SWGDE][2])

---

# 16. Section 8 — Recovered recordings

Example:

```text
Recording ID:
REC-017

Camera:
03

Original timestamp:
18:32:14

Normalized timestamp:
18:31:58

Duration:
00:02:31

Recovery:
Fragment reconstruction

Recovery confidence:
Medium

SHA-256:
XXXX
```

This is where our recovery engine becomes visible to the investigator.

---

# 17. Section 9 — Metadata

Metadata might include:

```text
Camera ID
Channel
Timestamp
Frame rate
Resolution
Codec
Duration
File size
Recording mode
Motion event
Audio presence
```

But:

> We should only report fields that were actually extracted.

If a proprietary format doesn't expose something:

```text
Not available
```

not:

```text
Unknown → guessed.
```

---

# 18. Section 10 — Timeline

The report could contain:

```text
18:30:02
Person enters Camera 01

18:30:09
Person appears Camera 02

18:30:17
Person enters Camera 03

18:31:02
Person exits Camera 04
```

This gives investigators an immediate understanding of the incident.

---

# 19. Section 11 — Cross-camera findings

The report should distinguish:

### Observed

```text
Person detected in Camera 01.
```

### Correlated

```text
Camera 01 and Camera 02 events are temporally and spatially compatible.
```

### Inferred

```text
The events may represent the same person's movement.
```

This distinction is important.

Do **not** output:

> "The suspect definitely moved from Camera 1 to Camera 2."

unless the evidence genuinely establishes that.

---

# 20. Section 12 — AI analysis

Example:

```text
Object:
Person

Camera:
03

Timestamp:
18:31:14

Detection confidence:
0.91

Frame:
XXXX
```

If using face analysis:

```text
Face detected
```

rather than automatically:

```text
Person identified as X
```

unless a validated identification workflow exists.

---

# 21. Section 13 — Validation

This is extremely important.

The report needs to answer:

> **How do we know our result is correct?**

Example:

```text
Expected recording:
10

Recovered:
10

Correctly reconstructed:
9

Partially reconstructed:
1

Incorrect:
0
```

Then:

```text
Recovery success:
90%
```

But this number must come from an actual controlled experiment.

We cannot invent it.

SWGDE explicitly recommends validation/verification of tools and processes and says organizations should have procedures for technical review and performance verification. ([SWGDE - SWGDE][2])

---

# 22. Validation should not just mean "software ran"

Bad:

```text
✓ Tool executed successfully
```

Good:

```text
Known test evidence:
20 recordings

Expected:
20

Recovered:
19

Correct:
18

Partial:
1
Incorrect:
0
```

Then we can calculate measurable performance.

---

# 23. Section 14 — Limitations

This section is mandatory for a serious forensic report.

Example:

```text
Limitations

• Camera clock offset could not be independently verified.
• 12 storage sectors were unreadable.
• Two recovered recordings contained missing fragments.
• Face detection failed on low-resolution frames.
• Vendor format was only partially understood.
```

This makes the report more credible.

---

# 24. Why limitations matter

A forensic report isn't supposed to make the system look perfect.

If we say:

> "100% accurate under all conditions."

a technically knowledgeable judge can destroy the claim immediately.

Instead:

> "The system successfully reconstructed X of Y recordings under the tested conditions. Failure cases included..."

That's much stronger.

---

# 25. Section 15 — Conclusions

The conclusion should be based on evidence.

Example:

> Three recordings corresponding to the requested period were recovered. Two were fully reconstructed and one contained missing fragments. The recovered files were verified using SHA-256. Camera 2 and Camera 3 events were temporally compatible with the investigated sequence.

Not:

> "The suspect definitely committed the crime."

The software should report forensic findings, not make unsupported legal conclusions.

---

# 26. Section 16 — Chain of custody

The report can include:

```text
E001

24 Aug 10:32
Collected by A

24 Aug 14:18
Transferred A → B

24 Aug 15:02
Analysis started

24 Aug 18:22
Analysis completed
```

This connects Requirement 9 directly into the final report.

---

# 27. Section 17 — Evidence disposition

**Disposition (what ultimately happened to the evidence).**

For example:

```text
Original HDD:
Returned to agency

Forensic image:
Retained

Recovered videos:
Retained

Temporary working files:
Deleted according to SOP
```

SWGDE's reporting requirements specifically include disposition of original and derivative works. ([SWGDE - SWGDE][1])

---

# 28. Section 18 — Appendices

Possible appendices:

```text
A. Evidence inventory
B. Hash manifest
C. Acquisition log
D. Chain-of-custody history
E. Recovered recordings
F. Timeline
G. Screenshots
H. Processing logs
I. Validation results
J. Tool/version information
```

---

# 29. The report should be machine-readable too

A PDF is useful for humans.

But our system should ideally also produce structured data.

Example:

```json
{
  "case_id": "CASE001",
  "evidence_id": "E001",
  "vendor": "CP Plus",
  "camera": "03",
  "original_timestamp": "...",
  "normalized_timestamp": "...",
  "recovery_status": "partial",
  "sha256": "..."
}
```

Why?

Because another system could consume it later.

This helps with:

* databases
* automated analysis
* cross-case search
* dashboards
* interoperability.

This is our proposed engineering enhancement, not an explicit NTRO requirement.

---

# 30. PDF generation technology

Possible approaches:

### HTML → PDF

Generate:

```text
HTML
 ↓
PDF
```

Advantages:

* easy formatting
* tables
* images
* CSS
* reproducible templates.

### ReportLab

Python library for generating PDFs.

### LibreOffice / headless office

Useful for document-based workflows.

### LaTeX

Very strong for complex document formatting but more cumbersome.

We should choose after testing.

The important point:

> **The report engine should be deterministic.**

Same evidence + same report template + same data should produce substantially the same report.

---

# 31. Why deterministic reporting matters

Imagine running analysis twice.

If the report randomly changes:

```text
field order
timestamps
evidence IDs
results
```

that's bad.

Instead:

```text
Case data
   ↓
Structured evidence model
   ↓
Template
   ↓
Report
```

The report should be generated from structured data, not manually assembled.

---

# 32. Report template

We can define:

```text
CASE REPORT TEMPLATE
```

with fixed sections:

```text
1. Case
2. Request
3. Evidence
4. Acquisition
5. Integrity
6. Processing
7. Findings
8. Timeline
9. AI analysis
10. Validation
11. Limitations
12. Conclusion
13. Custody
14. Disposition
```

Then every vendor follows the same structure.

---

# 33. Vendor independence

This is one of the strongest reasons for standardized reporting.

Without our platform:

```text
CP Plus tool
→ one report

Hikvision tool
→ different report

Dahua tool
→ another report
```

With our architecture:

```text
CP Plus
     \
Hikvision
      \
Dahua ------→ NORMALIZED EVIDENCE → STANDARD REPORT
      /
Uniview
     /
Matrix
```

That directly supports the vendor-agnostic goal of the PS.

---

# 34. Existing solutions already do this

This is important.

**Standardized forensic reporting is NOT novel.**

Commercial forensic products already generate reports.

And SWGDE's guidance explicitly notes that many forensic tools have built-in reporting functionality, while also warning that tool-generated reports may not document the full scope of an examination. ([SWGDE - SWGDE][1])

So:

❌ Don't say:

> "Our innovation is automated forensic reports."

That already exists.

Our engineering contribution is:

> **Integrating standardized reporting with the complete multi-vendor DVR/NVR forensic workflow and preserving the evidence lineage behind each finding.**

Even that should be presented as our proposed architecture, not as an unverified novelty claim.

---

# 35. The report should expose the source of every finding

This is one of the strongest design ideas we have.

Suppose the report says:

```text
18:32:14
Person detected
```

Clicking the result should ideally show:

```text
Source:
Camera 03

Recording:
REC-017

Frame:
18324

Recovered from:
E001.E01

Storage region:
XXXX

Recovery method:
Fragment reconstruction

Evidence SHA-256:
XXXX
```

Now:

```text
Finding
  ↓
Video
  ↓
Recovery
  ↓
Forensic image
  ↓
Original evidence
```

is traceable.

---

# 36. Evidence-linked reporting

This is what I would make a major architectural principle.

Every important result should have:

```text
SOURCE
+
PROCESS
+
RESULT
+
VALIDATION
```

Example:

```text
SOURCE
CP Plus HDD

PROCESS
CP Plus parser

RESULT
Recovered video

VALIDATION
SHA-256 + controlled test
```

Then:

```text
AI detection
```

also has:

```text
SOURCE FRAME
+
MODEL
+
VERSION
+
CONFIDENCE
```

---

# 37. Round 1 demo

This is one of the easiest requirements to demonstrate convincingly.

Start with:

```text
CP Plus evidence
```

Then click:

**Generate Report**

The system produces:

```text
FORENSIC EXAMINATION REPORT

CASE-001

Evidence:
CP Plus NVR

Acquisition:
Completed

SHA-256:
XXXX

Recovered recordings:
12

Timeline:
...

Cross-camera events:
...

AI findings:
...

Limitations:
...

Chain of custody:
...

Validation:
...

Conclusion:
...
```

This is visually impressive **without being fake AI**.

---

# 38. Better demo: compare two vendors

This would be stronger.

Input:

```text
CP Plus
+
Hikvision
```

The internal formats are different.

But output:

```text
STANDARD FORENSIC REPORT
```

contains the same fields.

Show:

```text
CP Plus
     ↓
CP Plus adapter
     ↓
Normalized evidence
     ↘
       STANDARD REPORT
     ↗
Normalized evidence
     ↑
Hikvision adapter
     ↑
Hikvision
```

That demonstrates the actual purpose of SIH26150.

---

# 39. Judge question: "Why do you need a standardized report?"

Answer:

> **Because different DVR vendors expose evidence differently. A standardized report gives investigators a consistent structure for acquisition information, recovered recordings, timestamps, hashes, processing history, findings and limitations regardless of the source vendor.**

---

# 40. Judge question: "Why not just export the vendor's report?"

Answer:

> **Vendor reports can document their own tool's output, but our objective is a common forensic workflow across multiple vendors. The report therefore needs to preserve a consistent evidence model and processing history across different vendor adapters.**

This is consistent with SWGDE's observation that tool-generated reports may not document the complete examination. ([SWGDE - SWGDE][1])

---

# 41. Judge question: "Can your report prove the evidence is genuine?"

Answer:

> **No. The report documents the acquisition, integrity checks, processing and findings. Authenticity and legal admissibility depend on the complete evidence-handling process and applicable procedures.**

---

# 42. Judge question: "Can an AI result be included as a fact?"

Answer:

> **The system should distinguish an automated analytical result from an established forensic conclusion. AI outputs should include the model, version, confidence and source evidence so the examiner can review the underlying material.**

This is especially important for forensic video analysis.

---

# 43. Judge question: "What happens if the recovery was incomplete?"

Answer:

The report should explicitly state:

```text
Recovery status:
PARTIAL

Recovered:
X

Missing:
Y

Reason:
Unreadable sectors / fragmented data / corrupted metadata
```

Never hide it.

---

# 44. Judge question: "Can another examiner reproduce your result?"

Our answer should be:

> **That is a design requirement. The report records the evidence identifier, acquisition details, processing operations, software/version, parameters, source artifacts, hashes and validation results so another trained examiner can understand and reproduce the workflow as far as the available evidence permits.**

SWGDE specifically emphasizes documentation sufficient for another similarly trained analyst to replicate the techniques and reach a comparable conclusion. ([SWGDE - SWGDE][2])

---

# 45. What we should actually build

For Round 1:

### Minimum

```text
Case creation
        ↓
Evidence registration
        ↓
Acquisition information
        ↓
Hash information
        ↓
Recovered videos
        ↓
Timeline
        ↓
Chain of custody
        ↓
PDF report
```

### Better

Add:

```text
Validation results
+
AI findings
+
cross-camera events
+
limitations
```

### Full SIH

Add:

```text
multi-vendor normalized evidence
+
automated processing logs
+
recovery provenance
+
AI analysis
+
complete standardized reporting
```

---

# 46. What should NOT be claimed

Do not say:

❌ "Our report is legally admissible."

❌ "Our report guarantees evidence authenticity."

❌ "Our reporting system is novel."

❌ "Our PDF proves the suspect's identity."

❌ "Our system eliminates the need for forensic investigators."

Instead:

✅ "Our system standardizes the documentation of forensic processing."

✅ "The report preserves evidence provenance and processing history."

✅ "The system exposes hashes and validation results."

✅ "The report distinguishes findings from limitations."

---

# 47. Requirement 10 — final verdict

### What NTRO asks

**Standardized forensic reporting**, including comprehensive reports and supporting documentation.

### Is it already solved?

**Yes.**

Commercial forensic tools and established forensic guidance already support reporting.

### Is automated reporting novel?

**No.**

Do not claim it.

### What should we build?

A reporting layer that converts:

```text
Vendor-specific evidence
+
forensic processing
+
recovery
+
timestamps
+
cross-camera analysis
+
AI results
+
hashes
+
chain of custody
```

into:

```text
ONE STANDARDIZED,
TRACEABLE,
EVIDENCE-LINKED REPORT
```

### The strongest architectural principle

> **Every important finding in the report should be traceable back to the evidence and the processing step that produced it.**

That is what makes our report useful rather than just attractive.

---

## Clean sources

**SWGDE — Requirements for Report Writing in Digital and Multimedia Forensics**
[https://www.swgde.org/documents/published-complete-listing/18-q-002-swgde-requirements-for-report-writing-in-digital-and-multimedia-forensics/](https://www.swgde.org/documents/published-complete-listing/18-q-002-swgde-requirements-for-report-writing-in-digital-and-multimedia-forensics/) ([SWGDE - SWGDE][1])

**SWGDE — Best Practices for Digital Forensic Video Analysis**
[https://www.swgde.org/documents/published-complete-listing/18-v-001-best-practices-for-digital-forensic-video-analysis/](https://www.swgde.org/documents/published-complete-listing/18-v-001-best-practices-for-digital-forensic-video-analysis/) ([SWGDE - SWGDE][2])

**SWGDE — Best Practices for Digital Evidence Collection**
[https://www.swgde.org/documents/published-complete-listing/18-f-002-best-practices-for-digital-evidence-collection/](https://www.swgde.org/documents/published-complete-listing/18-f-002-best-practices-for-digital-evidence-collection/) ([SWGDE - SWGDE][3])

**SWGDE — Current published documents**
[https://www.swgde.org/documents/current-documents/](https://www.swgde.org/documents/current-documents/) ([SWGDE - SWGDE][4])

---

## Pipeline status

```text
1.  Evidence Acquisition                 ✓
2.  Device / Model Identification       ✓
3.  Filesystem / Format Parsing         ✓
4.  Video / Metadata Extraction         ✓
5.  Deleted / Damaged Recovery          ✓
6.  Timestamp Normalization             ✓
7.  Cross-Camera Correlation            ✓
8.  Hashing / Integrity Validation      ✓
9.  Chain of Custody                    ✓
10. Standardized Reporting              ✓ ← JUST COMPLETED
11. AI-Based Video Analytics            → NEXT
12. Multi-Vendor / OEM Support
```

**Next: Requirement 11 — AI-Based Video Analytics: face detection, object detection and motion detection.**

[1]: https://www.swgde.org/documents/published-complete-listing/18-q-002-swgde-requirements-for-report-writing-in-digital-and-multimedia-forensics/?utm_source=chatgpt.com "SWGDE Requirements for Report Writing in Digital and Multimedia Forensics - SWGDE"
[2]: https://www.swgde.org/documents/published-complete-listing/18-v-001-best-practices-for-digital-forensic-video-analysis/?utm_source=chatgpt.com "Best Practices for Digital Forensic Video Analysis - SWGDE"
[3]: https://www.swgde.org/documents/published-complete-listing/18-f-002-best-practices-for-digital-evidence-collection/?utm_source=chatgpt.com "Best Practices for Digital Evidence Collection - SWGDE"
[4]: https://www.swgde.org/documents/current-documents/?utm_source=chatgpt.com "Published – Complete Listing - SWGDE"

# Requirement 11 — AI-Based Video Analytics

NTRO explicitly asks the system to perform:

* **Face detection**
* **Object detection**
* **Motion detection**

This is the most visible part of the project, but it is **not the forensic foundation**.

The important distinction:

> **Our forensic core tells us what the evidence contains and where it came from. AI helps investigators search and interpret large amounts of recovered video faster.**

SWGDE's forensic-video guidance treats video analysis as a broader forensic process involving technical examination, timeline reconstruction, frame analysis, clarification, comparison and interpretation. It also stresses that processing must be documented and reproducible, and that AI/automated results should not simply be treated as unquestionable conclusions. ([SWGDE - SWGDE][1])

---

# 1. What NTRO actually asks

The PS specifically mentions:

```text
AI-based analytics
    │
    ├── Face detection
    ├── Object detection
    └── Motion detection
```

The important word is **analytics**.

NTRO is not simply asking:

> "Put an AI model on a CCTV video."

It wants these capabilities as part of a **forensic investigation platform**.

That changes how we should design them.

---

# 2. Why AI is needed

Imagine an investigation has:

```text
20 cameras
×
30 days
×
24 hours
```

Manually watching everything is extremely expensive in time.

The investigator might instead ask:

> "Show me every period where a person appeared near Camera 7 between 18:00 and 22:00."

Or:

> "Show me vehicles appearing across Cameras 2, 3 and 4."

AI can reduce the amount of video the investigator needs to inspect.

It should therefore act as:

> **an evidence-search and analysis assistant.**

Not:

> **an automatic judge of what happened.**

---

# 3. Complete input → processing → output

Our AI pipeline should look like:

```text
Recovered / native video
        ↓
Video decoding
        ↓
Frame extraction
        ↓
Motion detection
        ↓
Object detection
        ↓
Object tracking
        ↓
Face detection
        ↓
Optional face analysis
        ↓
Temporal/event grouping
        ↓
Evidence-linked results
        ↓
Investigator review
```

The output is not simply:

```text
"Person detected"
```

It should be something like:

```text
Camera: CP-03
Time: 18:32:14
Object: Person
Confidence: 0.91
Frame: 18,324
Source: REC-017
```

---

# 4. Very important: Detection ≠ Identification

This distinction will matter enormously when judges question us.

### Object detection

> "There is a person in this frame."

### Face detection

> "There is a face in this frame."

### Face recognition

> "This face resembles person X."

These are different problems.

We should **not casually claim face recognition** just because NTRO asks for face detection.

---

# 5. Layer 1 — Video decoding

Before AI can analyze anything, we need frames.

```text
Recovered video
      ↓
Decoder
      ↓
Frames
```

A decoder converts compressed video data into images/frames that algorithms can process.

For example:

```text
H.264/H.265
      ↓
decoded frames
      ↓
AI model
```

This connects directly to our earlier video-extraction layer.

SWGDE specifically recommends understanding the native video structure and warns that unnecessary conversion/transcoding can alter visual characteristics or metadata. ([SWGDE - SWGDE][1])

---

# 6. Why we shouldn't blindly convert everything to MP4

This is an important forensic point.

Suppose:

```text
Original DVR recording
        ↓
Convert to MP4
        ↓
AI
```

The conversion may lose:

* metadata
* timing information
* original container information
* other technical properties.

SWGDE recommends using native formats where possible and documenting conversions; if conversion is necessary, the analyst should preserve relevant technical characteristics and document the process. ([SWGDE - SWGDE][1])

Therefore our architecture should be:

```text
ORIGINAL EVIDENCE
      ↓
preserved
      │
      ├────────→ forensic examination
      │
      └────────→ working copy
                       ↓
                  AI processing
```

AI operates on a **working copy**, not by modifying the original evidence.

---

# 7. Layer 2 — Frame extraction

A video might contain:

```text
25 frames/second
```

One minute:

```text
25 × 60 = 1,500 frames
```

One hour:

```text
90,000 frames
```

We don't necessarily need to run expensive AI inference on every frame.

**Inference (running a trained AI model on new data to produce a prediction).**

We can investigate:

```text
every frame
```

versus:

```text
every 2nd frame
```

versus:

```text
5 FPS
```

versus:

```text
motion-triggered frames
```

This becomes an actual engineering decision.

---

# 8. Motion detection

Motion detection answers:

> **"Did something change in this area of the video?"**

It does not necessarily tell us:

> "A person entered."

A simple approach is **frame differencing**.

**Frame differencing (comparing consecutive video frames to identify changed pixels).**

Example:

```text
Frame 1
   ↓
Frame 2
   ↓
Difference
   ↓
Motion region
```

SWGDE itself lists frame difference as a legitimate forensic video examination technique. ([SWGDE - SWGDE][1])

---

# 9. Basic motion algorithm

Suppose:

```text
Frame A
```

and:

```text
Frame B
```

We calculate:

```text
Difference = |A - B|
```

Then apply a threshold:

```text
Difference > threshold
        ↓
Motion
```

Then group nearby changed pixels into regions.

This can produce:

```text
Motion detected
x = 340
y = 120
width = 180
height = 300
```

---

# 10. Advantage of simple motion detection

It is:

* fast
* cheap
* easy to explain
* CPU-friendly
* doesn't require a trained model.

This is useful because we don't need expensive AI for every frame.

---

# 11. Problem with simple motion detection

It can trigger on:

* rain
* shadows
* lighting changes
* camera vibration
* trees
* reflections
* compression noise
* insects.

So:

```text
Motion ≠ Person
```

This is why motion detection and object detection should work together.

---

# 12. Better architecture

Instead of:

```text
Every frame
   ↓
Large AI model
```

we can investigate:

```text
Video
 ↓
Motion detection
 ↓
Motion found?
 ├── NO → skip
 └── YES
       ↓
 Object detection
```

This potentially reduces computation.

But:

> **We should benchmark this before claiming that it improves performance for our actual data.**

---

# 13. Object detection

Object detection answers:

> **"What objects are present and where are they?"**

For example:

```text
Person
Car
Motorcycle
Truck
Bicycle
```

Output:

```text
Person
confidence = 0.93
bounding box = [x1,y1,x2,y2]
```

**Bounding box (a rectangle marking where the detected object is located in the image).**

---

# 14. YOLO

One candidate is **YOLO (You Only Look Once)**.

YOLO is a family of real-time object-detection models.

The important point:

> We should not automatically choose YOLO simply because everyone knows it.

We need to compare it with alternatives such as:

* YOLO-family models
* Faster R-CNN
* SSD
* RT-DETR
* other modern detectors

and benchmark on our CCTV data.

---

# 15. Why YOLO is currently attractive

For our project, the main reasons to investigate YOLO are:

```text
Fast inference
+
large ecosystem
+
many pretrained models
+
easy deployment
+
GPU/CPU options
+
widely used object-detection tooling
```

But these are **reasons to test it**, not proof that it is automatically the best choice.

---

# 16. What we actually care about

For SIH, raw benchmark accuracy isn't enough.

We care about:

| Metric                   | Why                            |
| ------------------------ | ------------------------------ |
| Precision                | Avoid false detections         |
| Recall                   | Avoid missing relevant objects |
| FPS                      | Processing speed               |
| Memory                   | Hardware requirement           |
| Model size               | Deployment                     |
| Small-object performance | Distant CCTV targets           |
| Low-light performance    | Night recordings               |
| Occlusion performance    | People hidden behind objects   |
| CPU performance          | Offline forensic workstation   |
| GPU performance          | Faster investigations          |

---

# 17. CCTV is different from benchmark images

A model might perform very well on a standard dataset.

But our CCTV may contain:

```text
Low resolution
Night scenes
Compression
Motion blur
Camera angles
Rain
Occlusion
Distant people
Overexposure
Underexposure
Old cameras
Different lenses
```

Therefore:

> **We need to test the model on our actual CCTV recordings.**

This is where your access becomes extremely valuable.

---

# 18. Your available data

We currently have a very useful testing opportunity:

```text
CP Plus
5 cameras at home

TP-Link
2 cameras at home

Hikvision
college system

Xiaomi
friend's system
```

Plus potentially:

```text
Other vendors
friends
public datasets
online samples
```

This gives us multiple camera sources.

But we must distinguish:

> **Camera/video diversity**

from:

> **DVR filesystem diversity.**

A Xiaomi video export does not prove we can parse a Xiaomi DVR filesystem.

It is still useful for **AI/video-analysis testing**.

---

# 19. Object tracking

Detection tells us:

```text
Frame 1:
Person A
```

Frame 2:

```text
Person B
```

But how do we know they are the same person?

We use **tracking (linking detections across consecutive frames to estimate the same object's movement).**

Example:

```text
Frame 1
Person → ID 7

Frame 2
Person → ID 7

Frame 3
Person → ID 7
```

Now we can build:

```text
Track ID 7
18:32:10 → 18:33:47
```

---

# 20. Why tracking matters to our project

Because NTRO also asks for:

> **event correlation across cameras.**

Tracking helps us create:

```text
Camera 1
Track 17
    ↓
Camera 2
Track 04
    ↓
Camera 3
Track 11
```

But be careful.

A track ID from Camera 1 and a track ID from Camera 2 do **not automatically mean the same physical person**.

---

# 21. Cross-camera identity is harder

Suppose:

```text
Camera 1
Person wearing red shirt
```

then:

```text
Camera 2
Person wearing red shirt
```

Could be the same person.

But it could also be another person.

Therefore we need:

```text
timestamp
+
camera geometry
+
direction
+
appearance
+
location
+
time gap
```

and potentially a **re-identification model**.

**Person re-identification (matching the same person across different cameras using visual characteristics).**

---

# 22. This is where we should be careful

Don't tell judges:

> "Our AI tracks suspects across all cameras."

That is far too strong.

Better:

> "Our system generates candidate cross-camera associations using temporal and visual evidence, which can then be reviewed by the investigator."

Much more defensible.

---

# 23. Face detection

Face detection is:

```text
Video frame
    ↓
Face detector
    ↓
Face bounding boxes
```

Example:

```text
Face #1
x = 420
y = 130
width = 85
height = 90
confidence = 0.94
```

Again:

**Detection ≠ identification.**

---

# 24. Why face detection is useful

The investigator could search:

> "Show me frames containing faces."

Instead of watching:

```text
6 hours
```

they review:

```text
120 relevant clips
```

This is an **investigative acceleration** function.

---

# 25. Face recognition is a separate problem

If we eventually add:

```text
Face
 ↓
Embedding
 ↓
Database comparison
 ↓
Candidate identity
```

that's face recognition.

**Face embedding (a numerical representation of facial characteristics used for comparison).**

This introduces much greater issues:

* accuracy
* demographic performance
* low-resolution faces
* pose
* lighting
* legal/privacy issues
* false matches
* threshold selection.

NTRO specifically says **face detection**, so we should not make face recognition a core requirement unless we have a strong reason.

---

# 26. Face detection vs face recognition

|                      | Face detection     | Face recognition         |
| -------------------- | ------------------ | ------------------------ |
| Question             | Is a face present? | Whose face is it?        |
| Output               | Bounding box       | Identity/candidate match |
| Complexity           | Lower              | Higher                   |
| Risk                 | Lower              | Higher                   |
| NTRO explicitly asks | **Yes**            | No                       |
| Round 1 priority     | **High**           | Low                      |

This is an important scope-control decision.

---

# 27. Motion + object + face together

Our architecture can combine them:

```text
                    VIDEO
                      │
                      ▼
                 FRAME ENGINE
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
       Motion      Objects       Faces
       detector    detector      detector
          │           │           │
          └───────────┼───────────┘
                      ▼
                EVENT ENGINE
                      │
                      ▼
             TIMELINE / SEARCH
                      │
                      ▼
              INVESTIGATOR
```

This is much more useful than three unrelated AI buttons.

---

# 28. Event generation

Instead of storing millions of individual detections:

```text
Person
Person
Person
Person
Person
...
```

we group them into events.

Example:

```text
EVENT 001

Camera:
CP-03

Start:
18:32:10

End:
18:33:47

Objects:
Person × 2
Vehicle × 1

Motion:
Detected

Faces:
3 detected
```

This dramatically improves usability.

---

# 29. Event storage

A structured event could look like:

```text
Event ID:
EV-001

Evidence:
E001

Recording:
REC-017

Camera:
03

Start:
18:32:10

End:
18:33:47

Object:
Person

Track:
T07

AI model:
Model-X

Model version:
1.2

Confidence:
0.91
```

Now the AI result is linked to forensic evidence.

---

# 30. This connects to our reporting layer

Remember Requirement 10?

The report can say:

```text
18:32:10–18:33:47
Camera 03

Person detected
Confidence: 0.91
```

Then:

```text
Source:
REC-017

SHA-256:
XXXX

Evidence:
E001
```

That gives us:

```text
AI result
 ↓
Video
 ↓
Recovered recording
 ↓
Forensic image
 ↓
Original DVR
```

This is much more defensible than a standalone AI dashboard.

---

# 31. AI results must be reproducible

SWGDE explicitly says processing should be documented sufficiently that another similarly trained analyst can reproduce the techniques and evaluate the result. ([SWGDE - SWGDE][1])

Therefore store:

```text
Model name
Model version
Weights/version
Inference settings
Input video
Frame number
Timestamp
Confidence threshold
Hardware/software environment
```

At minimum for our prototype.

---

# 32. Model versioning

Suppose:

```text
2026:
YOLO model A
```

produces:

```text
Person confidence = 0.83
```

Later:

```text
YOLO model B
```

produces:

```text
Person confidence = 0.94
```

If we don't record the model version, the result isn't reproducible.

Therefore:

```text
Model:
X

Version:
Y

Parameters:
Z
```

should be attached to every AI processing run.

---

# 33. Confidence is NOT certainty

If:

```text
confidence = 0.95
```

that does **not** mean:

> "95% chance this is definitely a person."

It is a model-specific confidence score, and its interpretation depends on the model and calibration.

So our UI should avoid wording such as:

```text
95% certainty
```

and use:

```text
Model confidence: 0.95
```

---

# 34. False positives

**False positive (the system reports something that is not actually present).**

Example:

```text
Shadow
 ↓
AI
 ↓
Person detected
```

This is dangerous if investigators blindly trust it.

Therefore the system should allow:

```text
AI result
     ↓
Review
     ↓
Confirmed / Rejected
```

---

# 35. False negatives

**False negative (the system fails to detect something that is actually present).**

Example:

```text
Person
 ↓
night-time CCTV
 ↓
AI
 ↓
no detection
```

This is why:

> **AI should assist the investigator, not replace the underlying video examination.**

---

# 36. Low-resolution problem

This is particularly important for CCTV.

Suppose a face is:

```text
40 × 40 pixels
```

A sophisticated model cannot magically recover information that was never captured.

Therefore:

```text
AI cannot create missing evidence.
```

Image enhancement can sometimes improve visibility, but it cannot guarantee recovery of genuine identity information.

SWGDE's video-analysis guidance emphasizes understanding the original recording characteristics and documenting processing; it also warns that enhancement and processing must be evaluated rather than assumed to reveal truth. ([SWGDE - SWGDE][1])

---

# 37. Night-time problem

Example:

```text
Day
Person → easy detection

Night
Person → difficult detection
```

We should test:

* day
* night
* indoor
* outdoor
* low-light
* backlit
* rain
* crowded scenes.

This becomes part of our validation dataset.

---

# 38. Camera diversity

Our own data lets us test:

```text
CP Plus
TP-Link
Hikvision
Xiaomi
```

This is useful because different cameras can produce different:

* resolution
* compression
* frame rates
* lighting
* field of view
* codecs.

But again:

> This validates the **AI layer**, not proprietary DVR filesystem support.

---

# 39. Recent forensic guidance is actually moving in this direction

The current SWGDE video guidance has been updated to explicitly cover modern forensic video-analysis workflows, including technical preparation, metadata analysis, timeline reconstruction, frame analysis, clarification, video recovery, validation, documentation and reporting. ([SWGDE - SWGDE][1])

The important takeaway:

> AI should be integrated into a controlled forensic workflow rather than treated as an independent magic classifier.

---

# 40. Candidate technology stack

A reasonable **candidate** architecture is:

```text
Video
 ↓
FFmpeg / decoder
 ↓
OpenCV / frame processing
 ↓
Motion detection
 ↓
Object detector
 ↓
Tracker
 ↓
Face detector
 ↓
Event engine
 ↓
Database
 ↓
Report
```

But remember:

**Candidate ≠ final selection.**

We still need to benchmark the alternatives before committing.

---

# 41. Technology decision: motion detection

### Option A — Frame differencing

Simple.

```text
Frame A
 ↓
Frame B
 ↓
difference
```

**Advantages**

* Fast
* Simple
* No training
* Easy to explain

**Disadvantages**

* Lighting changes
* Shadows
* Camera movement
* Noise

### Option B — Background subtraction

**Background subtraction (estimating a relatively stable background and identifying pixels that differ from it).**

Better for some fixed-camera environments.

But it still has:

* shadows
* lighting changes
* dynamic backgrounds.

### Our current position

**Test both.**

Don't claim one is superior until we benchmark them on our CCTV.

---

# 42. Technology decision: object detection

Candidates:

```text
YOLO-family
Faster R-CNN
SSD
RT-DETR
```

We should evaluate:

```text
Accuracy
FPS
CPU performance
GPU performance
small objects
night scenes
model size
deployment complexity
```

For SIH, a model that is slightly less accurate but runs reliably offline may be better than a huge model requiring expensive hardware.

---

# 43. Technology decision: tracking

Candidates include:

* SORT
* Deep SORT
* ByteTrack
* BoT-SORT

**SORT (Simple Online and Realtime Tracking)** uses motion and association.

**Deep SORT** adds appearance information.

**ByteTrack** improves association by using high- and lower-confidence detections.

For our project, tracking should primarily provide:

```text
continuous object trajectories
```

rather than claiming identity.

---

# 44. Technology decision: face detection

Candidates can include:

* RetinaFace
* MTCNN
* SCRFD
* YOLO-based face detectors.

Again:

> Benchmark on our CCTV.

The key metric isn't just benchmark accuracy.

We care about:

```text
small faces
low-light faces
side profiles
occlusion
CPU/GPU performance
```

---

# 45. A major risk: AI becomes the entire project

This is something I strongly recommend we avoid.

Bad architecture:

```text
CCTV
 ↓
YOLO
 ↓
Dashboard
```

That looks like hundreds of hackathon projects.

Our architecture is:

```text
DVR/NVR
 ↓
Forensic acquisition
 ↓
Evidence preservation
 ↓
Vendor parsing
 ↓
Recovery
 ↓
Timeline
 ↓
AI analytics
 ↓
Validation
 ↓
Chain of custody
 ↓
Standardized report
```

AI is **one layer**.

That is exactly how we should present it.

---

# 46. What is actually novel here?

Again, don't claim:

❌ "AI object detection is novel."

❌ "Face detection is novel."

❌ "Motion detection is novel."

❌ "YOLO is novel."

They are established technologies.

The engineering opportunity is:

> **Use established video analytics as an evidence-linked analysis layer inside the multi-vendor forensic workflow requested by NTRO.**

And even that should be described as our proposed integration architecture, not as a guaranteed research novelty.

---

# 47. Round 1 — what we should actually demonstrate

We don't need to build a perfect AI system.

A credible demo could be:

```text
CP Plus / TP-Link video
       ↓
Frame extraction
       ↓
Motion detection
       ↓
Object detection
       ↓
Person/vehicle detection
       ↓
Tracking
       ↓
Timeline
       ↓
Evidence-linked result
       ↓
Report
```

Then show:

```text
Camera 03
18:32:10–18:33:47

Person detected
Vehicle detected

Source:
REC-017

Evidence:
E001
```

That is enough to demonstrate the architecture.

---

# 48. What we should test before PPT claims

At minimum:

### Test 1 — Normal daytime

```text
person
vehicle
```

### Test 2 — Night

```text
person
vehicle
```

### Test 3 — Multiple people

```text
3–5 people
```

### Test 4 — Partial occlusion

```text
person partly hidden
```

### Test 5 — Low resolution

```text
distant person
```

### Test 6 — Motion

```text
static scene
moving person
moving vehicle
```

### Test 7 — Camera differences

```text
CP Plus
TP-Link
Hikvision
Xiaomi
```

This gives us evidence for the technology choice.

---

# 49. Metrics

We should record:

```text
Detection precision
Detection recall
FPS
Processing time
CPU usage
GPU usage
Memory
False positives
False negatives
```

For tracking:

```text
ID switches
track continuity
tracking failures
```

For motion:

```text
true motion events
false motion events
```

Don't just say:

> "It worked."

Measure it.

---

# 50. Judge question: "Why use AI?"

Answer:

> **Because large surveillance investigations can contain hours or days of video across multiple cameras. AI can automatically locate candidate objects, faces and motion events so investigators can focus their examination on relevant portions instead of manually reviewing every frame. The AI results remain linked to the source evidence and require human review.**

---

# 51. Judge question: "Why not manually inspect the video?"

Answer:

> **Manual inspection remains important for forensic interpretation, but it does not scale well when evidence contains many cameras and long recording periods. Our AI layer is intended to reduce the search space, not replace the examiner.**

---

# 52. Judge question: "Why YOLO?"

Don't answer:

> "Because YOLO is fast."

Too weak.

Better:

> **"YOLO is one candidate because it provides a strong combination of real-time inference, pretrained models and practical deployment options. We will compare it against alternatives using our own CCTV data, particularly low-light, low-resolution and multi-camera footage, before finalizing the model."**

That is technically defensible.

---

# 53. Judge question: "What if the AI is wrong?"

Answer:

> **"The AI result is treated as an analytical lead, not as an unquestionable forensic conclusion. We preserve the source recording and frame, record the model and confidence, and allow the examiner to review the underlying evidence."**

This aligns with forensic-video guidance that interpretation must be supported by the examination and limitations must be communicated. ([SWGDE - SWGDE][1])

---

# 54. Judge question: "Can AI identify the suspect?"

Answer:

> **"Not from the detection module alone. Detection tells us that a face or person is present. Identification is a separate problem requiring additional methodology and validation. Our SIH requirement is primarily face, object and motion analytics, so we are not treating detection as identity determination."**

Excellent distinction to make.

---

# 55. Judge question: "What if the video is low quality?"

Answer:

> **"The system cannot recover information that was never captured. We can apply controlled enhancement or processing where appropriate, but the original evidence remains preserved and the report records the limitations. Low-resolution and low-light performance will be part of our validation."**

---

# 56. Judge question: "Does AI alter the evidence?"

Answer:

> **"The original evidence is preserved. AI operates on a working copy or extracted representation. Every processing operation is recorded, and the resulting artifact is separately identified and hashed."**

This follows the forensic principle of preserving the original while documenting processing on working copies. ([SWGDE - SWGDE][1])

---

# 57. Judge question: "Why do you need tracking?"

Answer:

> **"Object detection gives us independent detections per frame. Tracking links detections across frames so we can represent a continuous movement event and build timelines. We do not treat a tracker ID as proof of a person's identity across different cameras."**

---

# 58. Judge question: "Why not use cloud AI?"

For a forensic platform, a strong argument is:

```text
Evidence
 ↓
Sensitive
 ↓
Offline/local processing
```

Potential advantages:

* privacy
* no internet dependency
* predictable environment
* evidence stays inside investigation infrastructure
* easier reproducibility.

But:

> This should be treated as an architectural preference, not an absolute rule. Specific deployments may have different requirements.

---

# 59. Requirement 11 — final verdict

### What NTRO asks

**AI-based analytics including face, object and motion detection.**

### Are these technologies already solved?

**Yes.**

None of these individual technologies is novel.

### Should we still use them?

**Absolutely.**

Because NTRO explicitly asks for them.

The mistake would be making AI the entire project.

### Our role for AI

```text
FORENSIC CORE
       ↓
Recovered evidence
       ↓
AI ANALYTICS
       ↓
Searchable events
       ↓
Human examination
       ↓
Evidence-linked report
```

### Most important principle

> **AI should reduce the investigator's search workload while preserving the original evidence and making every automated finding traceable back to its source.**

---

## Key clean sources

**SWGDE — Best Practices for Digital Forensic Video Analysis**
[https://www.swgde.org/documents/published-complete-listing/18-v-001-2-0/](https://www.swgde.org/documents/published-complete-listing/18-v-001-2-0/) ([SWGDE - SWGDE][2])

**SWGDE — Current Video Forensics Documents**
[https://www.swgde.org/documents/published-by-committee/video/](https://www.swgde.org/documents/published-by-committee/video/) ([SWGDE - SWGDE][3])

**SWGDE — Best Practices for Digital Video Authentication**
[https://www.swgde.org/23-v-001/](https://www.swgde.org/23-v-001/) ([SWGDE - SWGDE][4])

**SWGDE — Requirements for Report Writing**
[https://www.swgde.org/documents/published-complete-listing/18-q-002-swgde-requirements-for-report-writing-in-digital-and-multimedia-forensics/](https://www.swgde.org/documents/published-complete-listing/18-q-002-swgde-requirements-for-report-writing-in-digital-and-multimedia-forensics/) ([SWGDE - SWGDE][5])

---

## Pipeline status

```text
1.  Evidence Acquisition                 ✓
2.  Device / Model Identification       ✓
3.  Filesystem / Format Parsing         ✓
4.  Video / Metadata Extraction         ✓
5.  Deleted / Damaged Recovery          ✓
6.  Timestamp Normalization             ✓
7.  Cross-Camera Correlation            ✓
8.  Hashing / Integrity Validation      ✓
9.  Chain of Custody                    ✓
10. Standardized Reporting              ✓
11. AI-Based Video Analytics            ✓ ← JUST COMPLETED
12. Multi-Vendor / OEM Support          → NEXT
```

**Next: Requirement 12 — Multi-Vendor / OEM Support.** This is arguably the most important requirement for SIH26150 because it ties together the entire reason NTRO wants a unified platform.

[1]: https://www.swgde.org/documents/published-complete-listing/18-v-001-best-practices-for-digital-forensic-video-analysis/?utm_source=chatgpt.com "Best Practices for Digital Forensic Video Analysis - SWGDE"
[2]: https://www.swgde.org/documents/published-complete-listing/18-v-001-2-0/?utm_source=chatgpt.com "Best Practices for Digital Forensic Video Analysis - SWGDE"
[3]: https://www.swgde.org/documents/published-by-committee/video/?utm_source=chatgpt.com "Video - SWGDE"
[4]: https://www.swgde.org/23-v-001/?utm_source=chatgpt.com "Best Practices for Digital Video Authentication - SWGDE"
[5]: https://www.swgde.org/documents/published-complete-listing/18-q-002-swgde-requirements-for-report-writing-in-digital-and-multimedia-forensics/?utm_source=chatgpt.com "SWGDE Requirements for Report Writing in Digital and Multimedia Forensics - SWGDE"

# Requirement 12 — Multi-Vendor / OEM Support

This is the **core requirement that gives SIH26150 its reason to exist**.

NTRO is not asking for:

> "A tool that can analyze one CP Plus DVR."

It specifically wants a **multi-vendor, vendor-agnostic forensic platform**.

The PS names:

* Dahua Technology
* CP Plus
* Honeywell Security
* HIKVISION
* TP-Link
* Godrej
* Uniview
* Matrix
* and other commonly used platforms

and expects support for **at least 5–6 major DVR/NVR OEMs**.

The reason is real: NIST has documented that CCTV/DVR systems use numerous vendor-specific formats and that differences in equipment and export formats make evidence collection costly and time-consuming. ([NIST][1])

---

# 1. The problem in one picture

Without our system:

```text
CP Plus DVR
   ↓
CP Plus-specific method/tool

Hikvision DVR
   ↓
Hikvision-specific method/tool

Dahua DVR
   ↓
Dahua-specific method/tool

Uniview DVR
   ↓
Uniview-specific method/tool
```

The investigator has to understand multiple systems.

NTRO wants:

```text
                 CP Plus
                    │
                 Hikvision
                    │
                  Dahua
                    │
                 Uniview
                    │
                  Matrix
                    │
                 Godrej
                    │
                 TP-Link
                    │
                 Honeywell
                    │
                    ▼
          ┌─────────────────────┐
          │  OUR FORENSIC TOOL  │
          └─────────────────────┘
                    │
                    ▼
        STANDARDIZED WORKFLOW
                    │
                    ▼
       STANDARDIZED EVIDENCE
                    │
                    ▼
          STANDARDIZED REPORT
```

That's the fundamental architecture.

---

# 2. What "vendor-agnostic" actually means

**Vendor-agnostic (designed so the investigator does not need a completely different workflow for each manufacturer).**

It does **NOT** mean:

> "One universal parser magically understands every DVR."

That is unrealistic.

Different manufacturers may use:

* different filesystems
* different partitions
* different metadata
* different indexes
* different storage layouts
* different video containers
* different timestamp structures
* different firmware versions
* different camera/channel mappings.

NIST has specifically documented the lack of a common export standard and the resulting interoperability problem. ([NIST][1])

---

# 3. The correct architecture

The most sensible design is an:

## Adapter architecture

**Adapter (a vendor-specific software module that translates one vendor's data into the platform's common format).**

```text
                 INPUT
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
   CP Plus     Hikvision     Dahua
   Adapter      Adapter      Adapter
       │           │           │
       └───────────┼───────────┘
                   ▼
          NORMALIZED EVIDENCE
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
    Recovery    Timeline       AI
       │           │           │
       └───────────┼───────────┘
                   ▼
             REPORTING
```

The vendor-specific complexity stays near the input.

The rest of the system remains common.

---

# 4. Why this architecture matters

Imagine we add CP Plus support.

We write:

```text
CPPlusAdapter
```

It converts:

```text
CP Plus proprietary data
```

into:

```text
NormalizedRecording
```

Then the recovery engine doesn't need to understand CP Plus.

Same for:

```text
HikvisionAdapter
DahuaAdapter
UniviewAdapter
MatrixAdapter
```

This gives us:

```text
Vendor-specific layer
        ↓
Common internal representation
        ↓
Common forensic processing
```

That is much more scalable than rewriting the entire application for every vendor.

---

# 5. What should a vendor adapter actually do?

A vendor adapter might contain:

```text
Device identification
Filesystem detection
Partition interpretation
Metadata parsing
Recording index parsing
Timestamp extraction
Camera/channel mapping
Video container identification
Fragment mapping
Recovery rules
```

Its output should be standardized.

For example:

```text
Vendor:
CP Plus

Model:
XYZ

Camera:
03

Recording:
R001

Start:
18:32:10

End:
18:33:47

Video location:
sector XXXXX

Codec:
H.264

Metadata:
...

Recovery status:
...
```

---

# 6. The normalized evidence model

This becomes one of the most important parts of our software.

Instead of:

```text
CP Plus output
```

being completely different from:

```text
Hikvision output
```

we define a common structure.

For example:

```text
Recording
├── evidence_id
├── vendor
├── model
├── camera_id
├── start_time
├── end_time
├── timezone
├── codec
├── resolution
├── source_location
├── recovery_status
├── metadata
└── hash
```

Every adapter fills the fields it can reliably determine.

---

# 7. Missing information

This is extremely important.

Suppose CP Plus exposes:

```text
Camera ID
Timestamp
Codec
```

but Hikvision exposes:

```text
Camera ID
Timestamp
Codec
GPS
```

We should **not invent GPS information for CP Plus**.

Instead:

```text
GPS:
Not available
```

or:

```text
Not determined
```

The normalized model must allow missing fields.

---

# 8. Why this is difficult

The difficult part isn't writing:

```text
if vendor == CP_PLUS:
```

The difficult part is discovering what the DVR actually stores.

Magnet's own documentation gives us excellent evidence of this difficulty.

If Magnet Witness encounters an unsupported DVR filesystem, it can ask the user to generate a **DVR Profiler Report** containing physical media structure, filesystem/partition information and a small amount of data. Magnet explains that this information helps its team identify and implement support for previously unseen DVRs. ([Magnet Forensics][2])

That is extremely important for us.

Even a major commercial forensic vendor doesn't simply claim:

> "Every DVR is automatically supported."

---

# 9. Existing global industry solution — Magnet Witness

One of the strongest existing commercial examples is:

[Magnet Witness](https://www.magnetforensics.com/products/magnet-witness/?utm_source=chatgpt.com)

Magnet says Witness can:

* acquire video from multiple sources
* access native/proprietary formats
* directly acquire surveillance DVR hard drives
* recover deleted or partially overwritten video
* work with damaged DVRs
* review multiple video sources
* export evidence. ([Magnet Forensics][3])

Magnet previously described DVR Examiner/Witness as supporting **over 50 native DVR file formats**. ([Magnet Forensics][4])

So again:

> **Multi-vendor forensic analysis already exists commercially.**

We must not claim otherwise.

---

# 10. But there is an important weakness

Look at Magnet's own workflow.

If a DVR is not recognized:

```text
DVR
 ↓
Magnet Witness
 ↓
Unrecognized filesystem
 ↓
DVR Profiler
 ↓
Sample / structural information
 ↓
Vendor support development
```

That means support is not automatically universal.

Magnet explicitly says that the more information supplied about an unfamiliar DVR's make/model/identifiers, the more likely they are to find a similar model to test. ([Magnet Forensics][2])

This is useful evidence for our research because it confirms a practical reality:

> **New vendor/model support can require reverse engineering and real sample hardware.**

---

# 11. Another global solution — Amped

Another major forensic-video company is:

[Amped FIVE](https://ampedsoftware.com/five?utm_source=chatgpt.com)

Amped says FIVE supports the majority of formats from CCTV/DVR systems and continuously adds proprietary formats based on user requests and submitted samples. ([Amped Software][5])

Its DVRConv product similarly handles proprietary CCTV/DVR formats and says unsupported files can be submitted to Amped for analysis and possible future support. ([Amped Software][6])

This is another very important finding:

```text
Unsupported format
       ↓
Submit sample
       ↓
Reverse engineering
       ↓
New decoder/demuxer
       ↓
Software update
```

This is essentially a **vendor-support expansion pipeline**.

---

# 12. Amped gives us an even better lesson

Amped's recent releases continue adding proprietary formats.

For example, its May 2026 update added handling for Panasonic N3R/N3A formats and described its continuing development of proprietary forensic demuxers, extractors and decoders based partly on user-submitted files. ([Amped Blog][7])

A **demuxer (software that separates different streams from a container or multiplexed data source)** is particularly relevant to our architecture.

This tells us:

> Proprietary CCTV formats remain an active engineering problem even in mature commercial forensic products.

---

# 13. This is important for our PPT

Do NOT say:

> "Existing tools cannot support multiple vendors."

A judge can immediately mention Magnet or Amped.

Instead say:

> **"Multi-vendor forensic capability exists commercially, but proprietary formats and new variants continue to require vendor-specific support and ongoing reverse engineering. Our architecture therefore uses modular vendor adapters and a normalized evidence model rather than assuming a universal parser."**

That is much harder to attack.

---

# 14. Why not simply use Magnet Witness?

This is probably one of the strongest questions we will get.

### Judge:

> "Magnet already does this. Why are you building it?"

We should not answer:

> "Because Magnet doesn't support multiple vendors."

That is demonstrably false.

Instead:

> **"Commercial tools already provide substantial DVR forensic capabilities. Our objective is not to claim that DVR recovery itself is new. The SIH requirement specifically calls for a platform covering the named OEM ecosystem, including Indian-market vendors, within a standardized workflow. We are investigating where publicly documented support is incomplete and where a modular, auditable, locally deployable architecture can provide additional coverage and validation."**

And then we must actually prove the coverage gap.

---

# 15. Another critical point: public support lists are incomplete

This was one of our earlier findings.

Magnet does not publicly expose a complete, exhaustive list mapping every named SIH vendor/model/firmware combination to support.

And Magnet's own profiler workflow demonstrates that unsupported systems exist.

Amped similarly says that users can submit unsupported formats for analysis and future support. ([Magnet Forensics][2])

Therefore:

### We should NOT say:

> "Magnet doesn't support CP Plus."

unless we have direct evidence.

### We can say:

> "Public documentation does not allow us to verify support for every CP Plus model/firmware combination."

That's defensible.

---

# 16. Vendor support isn't binary

This is a major conceptual improvement.

Don't think:

```text
CP Plus = supported
```

Think:

```text
CP Plus
 ├── Model A
 │    ├── Firmware 1 → supported
 │    └── Firmware 2 → unknown
 │
 ├── Model B
 │    └── unknown
 │
 └── Model C
      └── supported
```

This is much closer to reality.

---

# 17. Firmware matters

**Firmware (the software built into the DVR/NVR that controls its hardware and recording functions).**

A vendor may have:

```text
Model X
Firmware A
```

and:

```text
Model X
Firmware B
```

with different storage behavior.

Therefore our system should record:

```text
Vendor
Model
Firmware
Hardware revision
```

before claiming parser compatibility.

---

# 18. Why our own hardware is extremely useful

This is where your situation becomes genuinely useful.

You have:

```text
5 CP Plus cameras / NVR
2 TP-Link cameras
```

You can potentially access:

```text
Hikvision
```

from college.

And:

```text
Xiaomi
```

from your friend.

Plus potentially other systems.

This means we can begin creating a **controlled compatibility test environment**.

---

# 19. But don't confuse cameras with DVRs

This is critical.

Your:

```text
TP-Link camera
```

doesn't automatically give us:

```text
TP-Link DVR filesystem
```

Similarly:

```text
Xiaomi camera recording
```

doesn't prove:

```text
Xiaomi NVR parser
```

For Requirement 12, we need to know:

```text
What device stores the recording?
How is it stored?
What storage medium?
What filesystem?
What recording structure?
```

An exported MP4 is useful for AI testing.

It isn't enough for proprietary filesystem research.

---

# 20. Our testing strategy

For every vendor we can access:

### Step 1

Record device information.

```text
Vendor
Model
Firmware
Serial
Storage
Camera type
DVR/NVR/hybrid
```

### Step 2

Capture normal recordings.

### Step 3

Export using the normal interface.

### Step 4

If legally and technically appropriate, obtain the underlying storage/image for research.

### Step 5

Create a forensic image.

### Step 6

Identify partitions/filesystem.

### Step 7

Document proprietary structures.

### Step 8

Attempt extraction.

### Step 9

Compare recovered data against known ground truth.

### Step 10

Feed normalized output into the common pipeline.

---

# 21. Ground truth

**Ground truth (the known correct answer used to evaluate a system).**

This is extremely important.

Suppose we deliberately record:

```text
Camera 1
18:00–18:10
```

and then test recovery.

We know exactly what should exist.

So:

```text
Expected:
10 minutes
```

versus:

```text
Recovered:
9m 42s
```

Now we can measure performance.

Without ground truth, saying:

> "Our parser successfully recovered the video."

is weak.

---

# 22. Vendor compatibility matrix

We should eventually maintain something like:

| Vendor    | Model | Firmware | Storage | Parser | Metadata | Recovery | Timestamp | Status        |
| --------- | ----- | -------- | ------- | ------ | -------- | -------- | --------- | ------------- |
| CP Plus   | X     | X        | HDD     | ✓      | ✓        | ?        | ✓         | Tested        |
| TP-Link   | X     | X        | ?       | ?      | ?        | ?        | ?         | Investigating |
| Hikvision | X     | X        | HDD     | ✓      | ✓        | ?        | ✓         | Tested        |
| Dahua     | X     | X        | HDD     | ?      | ?        | ?        | ?         | Research      |
| Uniview   | X     | X        | HDD     | ?      | ?        | ?        | ?         | Research      |

This is far more meaningful than:

> "Supports 6 vendors."

---

# 23. What should happen when a vendor is unknown?

This is where we can learn from Magnet's DVR Profiler.

Our system could have:

```text
UNKNOWN DEVICE
      ↓
Collect device metadata
      ↓
Identify storage
      ↓
Fingerprint filesystem
      ↓
Generate compatibility profile
      ↓
Assign adapter
      ↓
Human review
```

**Fingerprint (a set of technical characteristics used to recognize a particular storage or data structure).**

---

# 24. Proposed "Vendor Adapter SDK"

This could become one of our stronger engineering ideas.

Instead of hard-coding every vendor into the core application:

```text
Core
 │
 ├── CP Plus plugin
 ├── Hikvision plugin
 ├── Dahua plugin
 ├── Uniview plugin
 └── Matrix plugin
```

Each adapter follows the same interface.

For example:

```text
identify()
acquire()
parse_filesystem()
extract_metadata()
extract_recordings()
recover()
normalize()
```

Then adding a vendor becomes:

```text
Create adapter
       ↓
Implement interface
       ↓
Run validation suite
       ↓
Register adapter
```

---

# 25. Why this is better than one giant parser

Bad:

```text
GiantParser.py
 ├── CP Plus
 ├── Hikvision
 ├── Dahua
 ├── Matrix
 ├── Uniview
 ├── ...
```

Every change risks breaking another vendor.

Better:

```text
Core Engine
     │
 ├── CPPlusAdapter
 ├── HikvisionAdapter
 ├── DahuaAdapter
 ├── UniviewAdapter
 └── MatrixAdapter
```

Each can be tested independently.

---

# 26. Adapter interface

A conceptual interface could be:

```text
VendorAdapter

detect(source)
get_device_info(source)
parse_storage(source)
list_recordings(source)
extract_metadata(recording)
recover(recording)
normalize(recording)
```

Every adapter returns the same data model.

---

# 27. But this is NOT magic

If a vendor uses a completely undocumented filesystem:

```text
Unknown DVR
      ↓
Adapter
      ↓
?????
```

We cannot simply write:

```text
parse()
```

and expect it to work.

We may need:

```text
binary analysis
+
hex inspection
+
filesystem research
+
controlled recordings
+
firmware analysis
+
reverse engineering
```

That is where the real technical difficulty lies.

---

# 28. Binary analysis

**Binary analysis (examining raw machine-readable data to understand how information is structured).**

For example:

```text
HDD
 ↓
hexadecimal data
 ↓
identify repeating structures
 ↓
find headers
 ↓
find timestamps
 ↓
find indexes
 ↓
map recordings
```

This is potentially one of the hardest parts of our project.

---

# 29. Why controlled recording helps

Suppose we know:

```text
18:00:00
Camera 1
```

Then:

```text
18:05:00
Camera 1
```

We inspect the storage.

If we can identify corresponding structures:

```text
timestamp
camera ID
recording boundary
```

we can start understanding the format.

Then we change one controlled variable:

```text
Camera 1 → Camera 2
```

and inspect the storage again.

This is essentially differential analysis.

**Differential analysis (comparing two controlled versions of data to determine which bytes/structures changed).**

---

# 30. This is where your hardware gives us an advantage

We can potentially create experiments like:

### Experiment A

```text
Record 1 minute
```

### Experiment B

```text
Record 2 minutes
```

Compare storage.

### Experiment C

```text
Camera 1 only
```

### Experiment D

```text
Camera 2 only
```

### Experiment E

```text
Change DVR clock
```

Compare metadata.

### Experiment F

```text
Delete recording
```

Then image the storage and investigate what remains.

This is far more valuable than simply downloading MP4 files.

---

# 31. Existing commercial products prove this approach is practical

Magnet's DVR Profiler asks for information about:

* drive architecture
* filesystem
* partition type
* file structure
* small samples of physical media.

That is essentially a structured version of the same investigative process. ([Magnet Forensics][2])

Amped similarly relies on submitted samples when new proprietary formats need to be analyzed. ([Amped Software][6])

So our planned research methodology is grounded in how real forensic vendors deal with unknown formats.

---

# 32. Multi-vendor does not mean "all vendors at once"

NTRO asks for:

> **at least five to six major OEMs.**

We should therefore prioritize.

A realistic progression:

### Stage 1

```text
CP Plus
Hikvision
```

because you have potential physical access.

### Stage 2

```text
TP-Link
```

if the relevant recording/storage system is accessible.

### Stage 3

```text
Dahua
Uniview
Matrix
```

through accessible hardware/images or controlled datasets.

### Stage 4

```text
Honeywell
Godrej
```

depending on availability.

---

# 33. Why CP Plus should be first

You have:

```text
5 CP Plus cameras
+
CP Plus NVR
```

That makes CP Plus our strongest experimental starting point.

We can potentially test:

```text
normal
deleted
fragmented
damaged
timestamp
multi-camera
```

conditions.

This is much better than choosing a vendor because it appears in the PS.

---

# 34. Why Hikvision should be second

Hikvision is explicitly named by NTRO.

It is also heavily represented in existing research and forensic tooling.

Therefore it is useful as a benchmark vendor.

We can compare:

```text
Our implementation
vs
existing research/tools
```

and determine whether we reproduce known results.

This is excellent for validation.

---

# 35. Why TP-Link is interesting

You have:

```text
2 TP-Link cameras
```

but we need to determine exactly what recording/storage architecture they use.

If the cameras use:

```text
SD card
cloud
NVR
VIGI NVR
```

those are different research targets.

So:

> **TP-Link hardware availability is confirmed, but forensic-storage relevance still needs to be established for the exact devices.**

---

# 36. Xiaomi

Same principle.

Your friend's Xiaomi footage is useful for:

```text
AI
video decoding
metadata
timestamp
```

but not automatically proof of:

```text
Xiaomi DVR/NVR filesystem support.
```

Also, Xiaomi isn't one of the named SIH OEMs.

Therefore it is a useful **additional test source**, not a priority vendor.

---

# 37. What about cloud cameras?

This is another reason our architecture should not accidentally become too broad.

SWGDE has separate guidance for cloud video acquisition because remotely stored video introduces different acquisition problems. ([SWGDE - SWGDE][8])

So:

```text
DVR HDD
```

and:

```text
Cloud CCTV
```

should not be treated as the same acquisition path.

For SIH26150:

> **Focus first on DVR/NVR storage.**

Cloud support can be an extension.

---

# 38. What happens after adding a vendor?

This is the key scalability mechanism.

```text
New vendor
    ↓
Adapter
    ↓
Normalized evidence
    ↓
Existing:
  recovery
  timeline
  AI
  hashing
  chain of custody
  reporting
```

We don't rebuild those modules.

That is the whole reason for the architecture.

---

# 39. Vendor compatibility testing

Each adapter should pass a common test suite.

For example:

```text
TEST-01
Device identification

TEST-02
Filesystem identification

TEST-03
Recording enumeration

TEST-04
Metadata extraction

TEST-05
Timestamp extraction

TEST-06
Normal recording recovery

TEST-07
Deleted recording recovery

TEST-08
Fragment reconstruction

TEST-09
Hash verification

TEST-10
Normalized output
```

Then:

```text
CP Plus → 8/10
Hikvision → 9/10
Dahua → 7/10
```

This is much more scientifically useful than claiming:

> "Supported."

---

# 40. Compatibility status should have levels

I strongly recommend:

### Level 0 — Unknown

```text
No parser
No validation
```

### Level 1 — Identified

```text
Device/filesystem recognized
```

### Level 2 — Extractable

```text
Recordings + metadata extracted
```

### Level 3 — Recoverable

```text
Deleted/fragmented recovery tested
```

### Level 4 — Validated

```text
Ground-truth testing completed
```

### Level 5 — Production candidate

```text
Extensive validation
```

This is much more honest.

---

# 41. Why this is powerful in a judge presentation

Instead of saying:

> "We support six vendors."

we can show:

```text
                    Vendor Support

CP Plus      █████ Validated
Hikvision    █████ Validated
Dahua        ████░ Tested
Uniview      ███░░ Partial
Matrix       ██░░░ Parser prototype
TP-Link      █░░░░ Research
```

And explain exactly what each level means.

That looks technically serious.

---

# 42. What is the real challenge?

Not:

> "Can we decode six videos?"

The real challenge is:

```text
Different storage structures
          ↓
Different evidence representations
          ↓
Different recovery mechanisms
          ↓
ONE standardized forensic model
```

That is the architectural problem.

---

# 43. What is already solved?

Let's be brutally honest.

### Already exists:

```text
DVR forensic acquisition
Vendor-specific parsing
Multi-vendor forensic software
Video extraction
Deleted recovery
Video analysis
Reporting
Evidence management
```

Magnet and Amped demonstrate this clearly. ([Magnet Forensics][3])

### Therefore:

**Multi-vendor DVR forensics as a general concept is NOT novel.**

---

# 44. Then why does SIH still ask for it?

Because the PS is not necessarily saying:

> "Nobody has ever built this."

It is asking NTRO's desired capability:

> **a unified forensic platform covering the relevant OEM ecosystem and standardizing acquisition, recovery, analysis, validation and reporting.**

And NIST independently identifies the same interoperability problem in CCTV evidence. ([NIST][1])

So our job is to implement a defensible solution to the **specific scope NTRO has defined**, not pretend the underlying concept was invented by us.

---

# 45. The biggest potential weakness in our project

This is the elephant in the room.

A judge can say:

> **"Why don't you just use Magnet Witness?"**

We need an evidence-backed answer.

Possible directions:

### A. Coverage

Demonstrate specific named OEM/model combinations that existing public documentation does not verify.

### B. Indigenous/local deployment

Investigate whether agencies requiring controlled/on-premise workflows have constraints around commercial foreign tools.

But **do not claim this is a gap without evidence.**

### C. Open architecture

Provide a modular adapter architecture where the organization can add its own parser.

### D. Validation transparency

Provide compatibility levels and reproducible vendor test datasets.

### E. Specific Indian-market coverage

Especially CP Plus and other vendors relevant to the Indian ecosystem.

But again:

> **This has to be demonstrated, not asserted.**

---

# 46. Round 1 — what we should actually show

We absolutely do **not** need six complete production-grade parsers tomorrow.

Instead:

### Demonstrate the architecture

```text
CP Plus
   ↓
Adapter
   ↓
Normalized evidence
   ↓
Common forensic engine
   ↓
Report
```

Then:

```text
Hikvision
   ↓
Adapter concept/prototype
   ↓
Same normalized structure
```

And show:

```text
Vendor Adapter Interface
```

plus the compatibility matrix.

---

# 47. Strong Round-1 demo

If we can actually make this work:

```text
CP Plus recording
       ↓
Identify
       ↓
Extract
       ↓
Normalize
       ↓
AI
       ↓
Hash
       ↓
Chain of custody
       ↓
Report
```

Then select:

```text
Hikvision
```

and show that the **same downstream pipeline** handles it.

That proves the architecture.

---

# 48. What we should not promise

Don't say:

> "We will support all eight vendors."

unless we have a credible implementation plan and access.

Better:

> **"Our architecture is designed for eight OEMs, with five to six prioritized for initial implementation and validation."**

That directly matches the SIH expectation without pretending everything already works.

---

# 49. What about new vendors?

This is where our proposed system could become genuinely useful.

```text
Unknown DVR
     ↓
Device profiling
     ↓
Storage fingerprint
     ↓
Adapter development
     ↓
Validation dataset
     ↓
Compatibility level
     ↓
Deployment
```

The system itself could record:

```text
Adapter version
Vendor
Model
Firmware
Parser version
Validation status
```

That makes support maintainable.

---

# 50. What about new firmware?

We should treat it as a new compatibility target.

```text
CP Plus
Model X
Firmware 1.0
    ↓
Validated

Firmware 1.1
    ↓
Needs validation
```

This is far more realistic than:

```text
CP Plus = supported forever.
```

---

# 51. What about analog/IP/hybrid?

SWGDE explicitly distinguishes:

* stand-alone embedded DVR
* NVR
* hybrid digital recorder
* PC-based systems
* server-based systems. ([SWGDE - SWGDE][9])

So NTRO's broad DVR/NVR scope can involve very different architectures.

Our device identification layer should therefore determine:

```text
Recorder type
```

before choosing the acquisition path.

---

# 52. Proposed acquisition branching

```text
                 DEVICE
                    │
                    ▼
             DEVICE IDENTIFIER
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
      DVR          NVR         Hybrid
       │            │            │
       ▼            ▼            ▼
  Acquisition   Acquisition   Acquisition
       │            │            │
       └────────────┼────────────┘
                    ▼
             COMMON EVIDENCE
```

This is supported by established DVR acquisition guidance, which recognizes multiple recorder architectures and notes that direct hard-drive acquisition may be appropriate when normal export isn't feasible. ([SWGDE - SWGDE][9])

---

# 53. A critical insight from NIST

NIST's work on CCTV interoperability is basically saying:

```text
Many vendors
     ↓
Many formats
     ↓
Different export mechanisms
     ↓
Conversion
     ↓
Potential metadata/quality loss
     ↓
Investigation delays
```

NIST's proposed interoperability work aims specifically to improve evidence sharing between CCTV/DVR owners and law enforcement and reduce the problems created by vendor-specific exports. ([NIST][1])

That is remarkably aligned with NTRO's underlying motivation.

---

# 54. Requirement 12 — final architecture

Putting everything together:

```text
                    DVR / NVR
                        │
                        ▼
               DEVICE IDENTIFICATION
                        │
                        ▼
                VENDOR ADAPTER
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
    CP Plus         Hikvision         Dahua
    Adapter          Adapter          Adapter
        │               │               │
        └───────────────┼───────────────┘
                        ▼
               NORMALIZED EVIDENCE
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
       Recovery      Timeline         AI
          │             │             │
          └─────────────┼─────────────┘
                        ▼
                    VALIDATION
                        │
                        ▼
                 CHAIN OF CUSTODY
                        │
                        ▼
                     REPORT
```

This is the architecture I would put in the PPT.

---

# 55. Requirement 12 — final verdict

### What NTRO asks

A **vendor-agnostic platform** supporting at least **5–6 major DVR/NVR OEMs**, explicitly naming eight vendors.

### Does a solution already exist?

**Yes.**

Commercial platforms such as Magnet Witness and Amped provide substantial multi-format/multi-vendor forensic capabilities. ([Magnet Forensics][3])

### Does that mean NTRO's problem is fake?

**No.**

NIST independently documents the underlying interoperability problem, and even commercial vendors maintain ongoing processes for adding unsupported proprietary formats. ([NIST][1])

### Is "multi-vendor support" itself novel?

**No.**

Do not claim it.

### What should we build?

```text
Vendor-specific adapters
          ↓
Normalized evidence representation
          ↓
Shared forensic engine
          ↓
Shared validation
          ↓
Shared AI
          ↓
Shared chain of custody
          ↓
Shared standardized reporting
```

### What is our biggest technical challenge?

> **Reliable normalization and validation across genuinely different proprietary DVR/NVR storage structures, models and firmware versions.**

### What is our strongest practical advantage?

**You actually have hardware/data access.**

```text
CP Plus × 5
TP-Link × 2
Hikvision → college
Xiaomi → friend
+ potential additional vendors
```

That lets us move from:

> "We think this architecture should work."

to:

> **"We can build controlled test datasets and measure whether it works."**

That is a huge difference.

---

# The complete NTRO pipeline is now covered

We've now gone through all **12 functional requirement groups**:

```text
1.  Evidence Acquisition                 ✓
2.  Device / Model Identification       ✓
3.  Filesystem / Format Parsing         ✓
4.  Video / Metadata Extraction         ✓
5.  Deleted / Damaged Recovery          ✓
6.  Timestamp Normalization             ✓
7.  Cross-Camera Correlation            ✓
8.  Hashing / Integrity Validation      ✓
9.  Chain of Custody                    ✓
10. Standardized Reporting              ✓
11. AI-Based Video Analytics            ✓
12. Multi-Vendor / OEM Support          ✓
```

But **this does NOT mean our research is finished**.

The next step should actually be more valuable for your PPT and project:

## Turn these 12 requirements into the actual technical stack

For each one, we now need to answer:

```text
NTRO requirement
        ↓
Best existing approach
        ↓
Best global industry implementation
        ↓
Indian implementation
        ↓
Alternatives
        ↓
Technology we should choose
        ↓
Why
        ↓
What we need to test
        ↓
What we can honestly claim in PPT
```

And especially for the technologies we have repeatedly mentioned — **forensic imaging, E01/DD, filesystem parsing, FFmpeg, binary analysis, recovery, timestamp handling, tracking, AI models, databases, hashing, audit logs and report generation** — we should now do the **technology-by-technology decision research**.

That is the part that will let you answer the judge's:

> **"Why did you choose this technology instead of the alternatives?"**

without bluffing.

[1]: https://www.nist.gov/programs-projects/digital-video-exchange-standards?utm_source=chatgpt.com "Digital Video Exchange Standards | NIST"
[2]: https://www.magnetforensics.com/blog/what-is-dvr-profiler/?utm_source=chatgpt.com "What is DVR Profiler? - Magnet Forensics"
[3]: https://www.magnetforensics.com/products/magnet-witness/?utm_source=chatgpt.com "Magnet Witness - Magnet Forensics"
[4]: https://www.magnetforensics.com/blog/introducting-magnet-witness/?utm_source=chatgpt.com "Introducing Magnet Witness - Magnet Forensics"
[5]: https://ampedsoftware.com/five?utm_source=chatgpt.com "Amped FIVE | Forensic Image and Video Enhancement"
[6]: https://ampedsoftware.com/dvrconv?utm_source=chatgpt.com "Amped DVRConv | Automatic CCTV/DVR Converter"
[7]: https://blog.ampedsoftware.com/2026/05/20/amped-five-update-40823?utm_source=chatgpt.com "Amped FIVE Update: New Formats, Assistant Automation, More"
[8]: https://www.swgde.org/documents/published-complete-listing/17-v-003-swgde-best-practices-for-digital-and-multimedia-evidence-video-acquisition-from-cloud-storage/?utm_source=chatgpt.com "SWGDE Best Practices for Digital & Multimedia Evidence Video Acquisition from Cloud Storage - SWGDE"
[9]: https://www.swgde.org/documents/published-complete-listing/17-v-002-swgde-best-practices-for-data-acquisition-from-digital-video-recorders/?utm_source=chatgpt.com "SWGDE Best Practices for Data Acquisition from Digital Video Recorders - SWGDE"


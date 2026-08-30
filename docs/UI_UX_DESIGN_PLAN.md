# 24FPS — UI/UX Design Plan

## 1. Product Structure

The application will follow a simple role-based flow:

```text
┌─────────────────┐
│   LANDING PAGE  │
└────────┬────────┘
         ↓
┌─────────────────┐
│      LOGIN      │
└────────┬────────┘
         ↓
    Authentication
         │
    ┌────┴────┐
    ↓         ↓
┌────────┐ ┌────────┐
│ POLICE │ │ ADMIN  │
│   UI   │ │   UI   │
└────────┘ └────────┘
```

The **Police interface** is focused on investigation and evidence.

The **Admin interface** is focused on system management, access control and monitoring.

---

# 2. Visual Identity

## 2.1 Brand Elements

```text
┌─────────────────────────────────────────────┐
│ 24FPS                                  CBI │
└─────────────────────────────────────────────┘
```

* 24FPS team logo
* CBI logo
* Logos appear consistently across the landing and login experience.

---

# 3. Landing / Hero Page

## 3.1 Layout

```text
┌─────────────────────────────────────────────────────┐
│  24FPS                                      CBI     │
│                                                     │
│                                                     │
│        EVERY FRAME                                  │
│        TELLS A STORY.                               │
│                                                     │
│        Acquire. Recover. Analyze.                   │
│        Verify. Report.                              │
│                                                     │
│                                                     │
│                                      ┌────────────┐ │
│                                      │   ENTER    │ │
│                                      │  PLATFORM →│ │
│                                      └────────────┘ │
└─────────────────────────────────────────────────────┘
```

### Design

* Full-screen red background
* Large black headline
* White supporting text
* Yellow CTA button
* 24FPS logo at top-left
* CBI logo at top-right
* Subtle forensic/evidence texture in the background
* Single CTA: **ENTER PLATFORM →**
* CTA positioned at the lower-right

---

# 4. Hero Content

### Main Heading

> **EVERY FRAME
> TELLS A STORY.**

### Supporting Text

> **Acquire. Recover. Analyze. Verify. Report.**

### CTA

> **ENTER PLATFORM →**

The CTA opens the login page.

---

# 5. Login Page

The login page will use a **clean coding-platform-inspired layout**, similar in simplicity to LeetCode.

```text
┌─────────────────────────────────────────────────────┐
│  24FPS                                      CBI     │
│                                                     │
│                                                     │
│                 ┌───────────────────┐               │
│                 │                   │               │
│                 │  User ID          │               │
│                 │  [_____________]  │               │
│                 │                   │               │
│                 │  Password         │               │
│                 │  [_____________]  │               │
│                 │                   │               │
│                 │  [ AUTHENTICATE ] │               │
│                 │                   │               │
│                 └───────────────────┘               │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Design

* Same 24FPS + CBI logos as hero
* Application-style black/white appearance
* User ID inside the login box
* Password inside the login box
* Single **AUTHENTICATE** button
* Authentication button uses a distinct color to separate it from the normal application palette
* No additional account-management elements

### Authentication Flow

```text
POLICE ID
    ↓
POLICE DASHBOARD

ADMIN ID
    ↓
ADMIN DASHBOARD
```

---

# 6. Application Design System

The actual application uses a restrained professional interface.

## Color Modes

```text
              APPLICATION
                  │
          ┌───────┴───────┐
          ↓               ↓
       DARK MODE       LIGHT MODE
```

### Dark Mode

* Dark/black background
* Lighter panels
* White text
* Yellow accent

### Light Mode

* White/light background
* Black text
* Yellow accent

---

# 7. Application Color Semantics

| Color      | Purpose                                          |
| ---------- | ------------------------------------------------ |
| Yellow     | Primary action, selection, important information |
| Green      | Verified, successful, operational                |
| Red        | Alert, failure, restricted access                |
| White/Gray | Normal interface information                     |

Yellow remains the primary application accent.

---

# 8. Typography

### Primary Typeface

**IBM Plex Sans**

Used for:

* Headings
* Navigation
* Buttons
* Descriptions
* Tables

### Technical Typeface

**IBM Plex Mono**

Used for:

```text
CASE-2026-001
EVID-00042
18:43:02
8A3F...92BC
```

This separates technical forensic information from normal UI text.

---

# 9. Cards and Containers

* Slightly rounded corners
* Approximately 4–6px radius
* Clean borders
* Minimal shadows
* Professional rather than heavily rounded
* No excessive pill-shaped components

---

# 10. Icons

Use clean **outline-style icons** throughout the application.

Examples:

```text
Cases       → Folder
Evidence    → File
Acquisition → Download
Recovery    → Restore
Timeline    → Clock
AI          → Scan
Integrity   → Shield
Reports     → Document
Settings    → Gear
```

---

# 11. Police Interface

The Police interface is designed as an **investigator's workspace**.

The primary focus is:

```text
RECENT ACTIVITY
      ↓
MY CASES
      ↓
CASE
      ↓
EVIDENCE
      ↓
FORENSIC ANALYSIS
```

---

# 12. Police Initial Dashboard

Immediately after login, the officer sees **recent investigation updates**.

```text
┌──────────────────────────────────────────────────────────┐
│ ☰   RECENT UPDATES                                       │
├──────────────┬───────────────────────────────────────────┤
│ SEARCH       │                                           │
│ [_________]  │       RECENT INVESTIGATION UPDATES        │
│              │                                           │
│ MY CASES     │   Ravi uploaded Evidence E-014            │
│              │   Arjun completed recovery on E-011       │
│ CASE-001     │   AI analysis completed for Camera 03    │
│ CASE-002     │   Priya added timeline event              │
│ CASE-003     │                                           │
│ CASE-004     │                                           │
└──────────────┴───────────────────────────────────────────┘
```

---

# 13. Police Dashboard — Left Panel

The left side contains:

### Search

```text
[ Search cases... ]
```

### Assigned Cases

```text
CASE-001
CASE-002
CASE-003
CASE-004
```

Only cases available to the logged-in investigator are shown.

Selecting a case opens its investigation workspace.

---

# 14. Recent Investigation Updates

The large right-side area shows activity from the investigation team.

Example:

```text
08:42   Ravi uploaded new evidence
        CASE-001 · EVID-014

08:37   Arjun completed recovery
        EVID-011

08:31   Priya added timeline event
        CASE-001

08:24   AI analysis completed
        CAMERA-03
```

This represents multiple team members working on the same investigation.

---

# 15. Police Case Workspace

Selecting a case changes the interface into a dedicated case workspace.

```text
┌─────────────────────────────────────────────────────────┐
│ ☰     CASE-2026-001                                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ CASE OVERVIEW | EVIDENCE | ACQUISITION | RECOVERY       │
│ TIMELINE | AI | INTEGRITY | REPORT                      │
│                                                         │
│                 CASE CONTENT                            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

The case sections are accessed through the top navigation.

---

# 16. Case Navigation

The case navigation contains:

```text
CASE OVERVIEW
EVIDENCE
ACQUISITION
RECOVERY
TIMELINE
AI
INTEGRITY
REPORT
```

Navigation controls and movement-related controls are kept toward the **left side**.

---

# 17. WhatsApp-Style Case Sidebar

The case list is hidden when working inside a case.

A **☰ menu** opens the left sidebar.

```text
┌─────────────────────┐
│ CASES               │
│                     │
│ Search              │
│ [____________]      │
│                     │
│ CASE-001            │
│ CASE-002            │
│ CASE-003            │
│ CASE-004            │
│                     │
│                     │
│                     │
│─────────────────────│
│ Recent Updates      │
└─────────────────────┘
```

### Sidebar behavior

* Case list is scrollable
* Sidebar content can contain many cases
* Bottom section remains fixed
* **Recent Updates** remains accessible at the bottom
* Clicking **Recent Updates** returns to the initial activity view

---

# 18. Case Overview

The case overview will provide the main investigation context.

Potential structure:

```text
CASE-2026-001
CCTV Theft Investigation

STATUS: ACTIVE
CLEARANCE: L1

┌─────────────────────────────────────────┐
│ ACQUISITION → RECOVERY → ANALYSIS →    │
│ VERIFICATION → REPORT                   │
└─────────────────────────────────────────┘
```

It acts as the starting point for the selected investigation.

---

# 19. Evidence Interface

Evidence uses a **table + preview** layout.

```text
┌─────────────────────────┬──────────────────────────────┐
│ EVIDENCE                │ SELECTED EVIDENCE            │
│                         │                              │
│ EVID-011                │        VIDEO PREVIEW         │
│ EVID-012                │                              │
│ EVID-013                │                              │
│ EVID-014  ←             │ Metadata                     │
│ EVID-015                │ Recovery                     │
│                         │ Integrity                    │
└─────────────────────────┴──────────────────────────────┘
```

### Left

* Evidence list
* Evidence IDs
* Status
* Selection

### Right

* Video/evidence preview
* Metadata
* Recovery information
* Integrity information

---

# 20. CCTV Viewer

The CCTV viewer uses:

**Main video + camera selection strip**

```text
┌───────────────────────────────────────────────┐
│                                               │
│                  CAMERA 03                    │
│                                               │
│              ┌───────────────┐                │
│              │               │                │
│              │ VIDEO PLAYER  │                │
│              │               │                │
│              └───────────────┘                │
│                                               │
├───────────────────────────────────────────────┤
│ CAM 01 │ CAM 02 │ CAM 03 │ CAM 04 │ CAM 05 │
└───────────────────────────────────────────────┘
```

### Interaction

* Main video shows selected camera
* Camera strip allows switching cameras
* Current camera is highlighted
* Camera selection updates the primary viewer

---

# 21. Acquisition

The acquisition interface follows:

```text
SOURCE
   ↓
ACQUISITION
   ↓
VERIFICATION
```

Example:

```text
Vendor: CP Plus
Device: NVR
Storage: HDD
Channels: 5

[ BEGIN ACQUISITION ]
```

During processing:

```text
Reading source...

██████████████░░░░░░ 72%

Calculating evidence hash...
```

---

# 22. Recovery

Recovery focuses on recovered and fragmented recordings.

```text
┌─────────────────────────────────────────────────────┐
│ EVIDENCE RECOVERY                                   │
│                                                     │
│ 428 RECORDINGS    391 RECOVERED    24 FRAGMENTED   │
│                                  13 DELETED        │
│                                                     │
│ REC-00342                                           │
│ Camera 03 · 18:42:13–18:46:51                     │
│ Fragmented                                          │
│ Recovery Confidence: 84%                            │
│                                                     │
│ [ REVIEW EVIDENCE ]                                 │
└─────────────────────────────────────────────────────┘
```

---

# 23. Timeline

The timeline provides a multi-camera chronological view.

```text
             18:00       18:30       19:00

CAM 01       ███████████████

CAM 02             █████████████

CAM 03       █████████

CAM 04                    ███████████

CAM 05                         █████████
```

Events can be selected to inspect the corresponding evidence.

---

# 24. AI Analysis

The AI screen combines the video with analysis results.

```text
┌──────────────────────────┬───────────────────────────┐
│                          │ AI ANALYSIS               │
│                          │                           │
│                          │ Detection                 │
│       VIDEO              │ Person        94%         │
│                          │ Vehicle       89%         │
│                          │                           │
│                          │ Search                    │
│                          │ [ person with red shirt ] │
│                          │                           │
│                          │ Results                   │
│                          │ 12:43:21                  │
│                          │ 13:02:44                  │
│                          │ 14:18:03                  │
└──────────────────────────┴───────────────────────────┘
```

### Interactions

* AI detections displayed alongside video
* Search for relevant objects/events
* Detection results are clickable
* Selecting a timestamp jumps the video to that point

---

# 25. Integrity

Evidence integrity combines hash verification with provenance.

```text
EVID-001

SHA-256
8A3F...92BC

INTEGRITY
✓ VERIFIED

ACQUIRED
   ↓
RECOVERED
   ↓
ANALYZED
   ↓
EXPORTED
```

The interface can also provide access to the audit trail.

---

# 26. Reports

The report interface provides a forensic report generation workflow.

```text
REPORT CONTENT

✓ Case Information
✓ Evidence Details
✓ Acquisition
✓ Recovery Findings
✓ Timeline
✓ AI-Assisted Findings
✓ Integrity Verification
✓ Chain of Custody

[ GENERATE REPORT ]
```

The generated report will be presented through a report/PDF-style preview.

---

# 27. Clearance Model

The Police interface will always show the logged-in investigator's clearance.

```text
P-1042
INVESTIGATOR
CLEARANCE L1
```

### Levels

```text
L1
Assigned Evidence
       ↓
L2
Team / Case Evidence
       ↓
L3
All Evidence
```

### Access behavior

If an investigator attempts to access evidence outside their authorization:

```text
┌──────────────────────────────────────┐
│          ACCESS RESTRICTED           │
│                                      │
│ EVID-024                             │
│                                      │
│ Required Clearance: L2              │
│ Your Clearance: L1                  │
│                                      │
│ This evidence is outside your        │
│ authorization scope.                 │
│                                      │
│              [ RETURN ]              │
└──────────────────────────────────────┘
```

---

# 28. Admin Interface

The Admin interface will function as a:

> **System Monitoring + Investigation Management + Access Control workspace**

It will be separate from the investigator-focused Police interface.

---

# 29. Admin Dashboard

The Admin dashboard will provide an overall command-center view.

```text
┌──────────────────────────────────────────────────────┐
│ SYSTEM STATUS                         27 AUG 08:52   │
├──────────────────────────────────────────────────────┤
│                                                      │
│ ACTIVE CASES   EVIDENCE    USERS       ALERTS        │
│     127          1482        86           03          │
│                                                      │
├──────────────────────────┬───────────────────────────┤
│ SYSTEM SERVICES          │ SECURITY                  │
│                          │                           │
│ API          ● ONLINE    │ Integrity      142 ✓     │
│ PostgreSQL   ● ONLINE    │ Access Alerts    02      │
│ ML Engine    ● ONLINE    │ Failed Login     01      │
│ FFmpeg       ● ONLINE    │                           │
├──────────────────────────┴───────────────────────────┤
│ ACTIVE CASES          │ RECENT ACTIVITY              │
└──────────────────────────────────────────────────────┘
```

---

# 30. Admin System Monitoring

Backend/software services will be represented as operational components.

```text
API              ● ONLINE
PostgreSQL       ● ONLINE
ML ENGINE        ● ONLINE
FFMPEG           ● ONLINE
STORAGE          ● ONLINE
```

Additional information can include:

* Service status
* Processing load
* Failed jobs
* Storage capacity
* Recent system events

---

# 31. Admin Case Management

Admin can view all cases rather than only assigned cases.

```text
CASE ID       STATUS       OFFICERS       CLEARANCE

CASE-001      Active          3               L2
CASE-002      Review          2               L1
CASE-003      Active          4               L3
```

---

# 32. Admin User Management

Admin can manage investigators.

```text
USER       ROLE             CLEARANCE      CASES

P-1042     Investigator       L1             2
P-1098     Investigator       L1             1
P-0871     Team Lead          L2             4
A-0001     Director           L3            All
```

Actions include:

* Add user
* Assign case
* Change clearance
* Revoke access

---

# 33. Admin Access Matrix

The access matrix visually represents evidence/case permissions.

```text
             CASE-001   CASE-002   CASE-003

P-1042           ✓          —          —

P-1098           ✓          ✓          —

P-0871           ✓          ✓          ✓

A-0001           ✓          ✓          ✓
```

This provides an immediate visual representation of the clearance system.

---

# 34. Admin Audit Log

The Admin can view global system activity.

```text
12:41:08   P-1042
           Viewed EVID-001

12:39:21   P-0871
           Assigned P-1098 to CASE-001

12:32:14   SYSTEM
           SHA-256 verification completed

12:28:42   P-1042
           Started evidence analysis
```

---

# 35. Admin Security Events

Security-specific events are separated from normal activity.

```text
ACCESS DENIED
P-1098 attempted access to EVID-009
Required: L2
User: L1

INTEGRITY ALERT
Evidence hash mismatch detected

UNUSUAL ACTIVITY
Multiple failed authentication attempts
```

---

# 36. Admin Integrity Monitoring

Global evidence integrity:

```text
EVIDENCE INTEGRITY

VERIFIED       142
PENDING          3
FLAGGED          1
```

Flagged evidence can be opened for investigation.

---

# 37. Admin AI / ML Monitoring

The Admin can monitor the AI service rather than performing the investigation itself.

```text
AI ENGINE

MODEL
YOLO

STATUS
● ONLINE

INFERENCE QUEUE
03

PROCESSED TODAY
1,284

FAILED JOBS
02
```

---

# 38. Admin Storage Monitoring

```text
EVIDENCE STORAGE

Used          6.8 TB
Available     3.2 TB
Cases           127
Evidence      1,482
```

---

# 39. Navigation Philosophy

The Police and Admin interfaces deliberately have different priorities.

```text
POLICE
────────────────────────
Recent Updates
     ↓
My Cases
     ↓
Evidence
     ↓
Analysis
     ↓
Verification
     ↓
Report
```

```text
ADMIN
────────────────────────
System Status
     ↓
Cases
     ↓
Users
     ↓
Access Control
     ↓
Security
     ↓
Infrastructure
```

---

# 40. Overall User Journey

```text
                    24FPS
                      │
                      ↓
              ┌──────────────┐
              │ LANDING PAGE │
              └──────┬───────┘
                     │
                     ↓
              ┌──────────────┐
              │    LOGIN     │
              └──────┬───────┘
                     │
             ┌───────┴───────┐
             ↓               ↓
       ┌───────────┐   ┌───────────┐
       │  POLICE   │   │   ADMIN   │
       └─────┬─────┘   └─────┬─────┘
             │               │
             ↓               ↓
      Recent Updates    System Status
             │               │
             ↓               ↓
         My Cases         All Cases
             │               │
             ↓               ↓
       Case Workspace    Users / Access
             │               │
             ↓               ↓
          Evidence       Security
             │               │
             ↓               ↓
        Acquisition     Infrastructure
             │
             ↓
          Recovery
             │
             ↓
          Timeline
             │
             ↓
        AI Analysis
             │
             ↓
          Integrity
             │
             ↓
           Report
```

# 41. Core Design Principle

The entire UI should communicate one distinction:

> **Police interface = investigate the evidence.**

> **Admin interface = manage the platform and authorization.**

The frontend can use **realistic placeholder data and simulated interactions** while maintaining the appearance and workflow of the intended 24FPS forensic platform.
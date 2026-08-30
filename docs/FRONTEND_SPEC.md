# SIH26150 Frontend Design & Implementation Specification

## 1. Project Overview

Build a complete, premium, modern frontend prototype for the SIH26150 forensic investigation platform.

This frontend is currently a **standalone demonstration prototype**. The backend is still under development, so the frontend must work completely using local mock data and simulated API behavior.

The purpose of this frontend is to demonstrate to judges, faculty, and evaluators what the final SIH26150 forensic system will look and feel like.

The application should NOT look like a basic college CRUD project.

It should look like a professional forensic investigation and evidence analysis platform used by law enforcement, digital forensic investigators, and technical analysts.

The UI must communicate:

- Technical sophistication
- Forensic precision
- Evidence integrity
- Investigation workflow
- AI-assisted analysis
- Security
- Chain of custody
- Advanced video and media analysis

The overall quality target is:

> A polished commercial-grade forensic intelligence platform, not a student dashboard.

---

# 2. Core Design Philosophy

The frontend should follow these principles:

1. Dark-first professional interface.
2. Minimal unnecessary decoration.
3. Dense but organized information.
4. Important forensic information should be visually prominent.
5. The UI should feel technical without becoming confusing.
6. Every screen should have a clear purpose.
7. Avoid excessive gradients, glassmorphism, neon effects, and random animations.
8. Use subtle motion only where it improves understanding.
9. Prefer structured layouts over oversized cards.
10. Use visual hierarchy to guide attention.
11. The application must be usable as a realistic desktop forensic workstation.
12. Desktop is the primary target.
13. Responsive design is still required for smaller screens.

The design should feel like a combination of:

- Professional forensic software
- Cybersecurity dashboard
- Video intelligence platform
- Investigation management system
- AI-assisted analysis workspace

Do NOT make it look like:

- A generic admin dashboard
- A cryptocurrency dashboard
- A gaming interface
- A colorful SaaS landing page
- A basic Bootstrap student project

---

# 3. Technology Stack

Use the following unless the existing frontend project configuration requires otherwise.

## Core

- React
- TypeScript
- Vite

## Styling

Use Tailwind CSS.

Create reusable design tokens through Tailwind configuration or CSS variables.

## UI Components

Prefer high-quality reusable primitives.

Possible choices:

- shadcn/ui
- Radix UI
- Lucide icons

Do not add unnecessary UI libraries.

## Charts

Use:

- Recharts

Charts should be meaningful and connected to forensic concepts.

## State

Because this is currently a frontend-only prototype:

- Use React state where sufficient.
- Use local mock data.
- Simulate asynchronous loading where useful.
- Keep mock data separate from UI components.

Do NOT build a complex state architecture unnecessarily.

---

# 4. Frontend-Only Mode

The backend is NOT ready for integration.

Therefore:

- Do not require backend connectivity.
- Do not require a running API.
- Do not create broken fetch calls to nonexistent backend endpoints.
- Do not make the application unusable without a server.

Instead create a service abstraction.

Example structure:

src/
├── components/
├── pages/
├── layouts/
├── hooks/
├── services/
│   ├── mockApi.ts
│   └── types.ts
├── data/
│   └── mockData.ts
├── lib/
├── utils/
├── App.tsx
└── main.tsx

All UI components should consume data through service functions where practical.

Example conceptual pattern:

```ts
getCases()
getCaseById()
getEvidence()
getEvidenceById()
getDevices()
getRecordings()
getAnalysisResults()
```

For now these functions return mock data.

Later they should be easy to replace with real backend API calls.

---

# 5. Application Name

Use:

## 24FPS

Subtitle:

### Digital Forensic Intelligence Platform

Alternative small branding:

```text
24FPS
FORENSIC INTELLIGENCE SYSTEM
```

The logo should be minimal and professional.

Do not create a cartoon logo.

---

# 6. Main Application Layout

The application should use a professional three-level structure.

## Left Sidebar

Persistent navigation.

Contains:

- Logo
- Main navigation
- Investigation section
- Analysis section
- System section
- User profile area at bottom

Suggested navigation:

### MAIN

- Overview
- Cases
- Evidence
- Devices

### ANALYSIS

- Media Analysis
- Timeline
- Integrity
- AI Insights

### SYSTEM

- Activity
- Reports
- Settings

The active navigation item should be visually clear but subtle.

Use:

- Accent background
- Thin indicator
- Icon emphasis

Avoid giant colorful buttons.

---

# 7. Top Header

The main content area should contain a top header.

Header should include:

- Breadcrumb or current page title
- Case context when relevant
- Global search
- Notification icon
- System status indicator
- User profile

Example:

```text
Investigations / CASE-2026-014
```

Right side:

```text
Search evidence...
System Secure
Notifications
User Avatar
```

The system status should subtly indicate:

```text
SYSTEM OPERATIONAL
```

Use green only as a restrained status color.

---

# 8. Main Dashboard

Route:

```text
/
```

Title:

# Investigation Overview

The dashboard should immediately look impressive.

It should provide a high-level overview of the investigation environment.

---

## Dashboard Top Metrics

Show important metrics.

Example:

### Active Cases

12

Subtitle:

```text
3 requiring attention
```

### Registered Evidence

248

Subtitle:

```text
+18 this week
```

### Analyzed Recordings

1,426

Subtitle:

```text
92% successfully processed
```

### Integrity Status

99.8%

Subtitle:

```text
All critical evidence verified
```

Do not use excessively large cards.

Use compact but premium metric cards.

---

## Investigation Activity

Show recent activity.

Example events:

```text
10:42 AM
SHA-256 verification completed
Evidence: EVID-00482

10:31 AM
New CCTV recording registered
Device: DVR-UNIT-03

10:12 AM
AI anomaly detected
Recording: CAM-04-2026-08-21

09:58 AM
Case status updated
CASE-2026-014
```

Use a vertical activity timeline.

---

## Case Distribution

Show a professional chart.

Possible data:

- Active
- Under Analysis
- Review Required
- Closed

Use a restrained color palette.

---

## Evidence Integrity Overview

Show:

- Verified
- Pending
- Failed
- Warning

Include a small visual indicator.

Example:

```text
VERIFIED        226
PENDING          18
WARNING           3
FAILED            1
```

---

## Recent Investigations

Show a compact table.

Columns:

- Case ID
- Case Name
- Priority
- Evidence
- Status
- Last Updated

Example:

```text
CASE-2026-014
Highway Incident Investigation
HIGH
24 Evidence
ACTIVE
2 minutes ago
```

Clicking a row should navigate to the case details page.

---

# 9. Cases Page

Route:

```text
/cases
```

Title:

# Investigations

Provide:

- Search
- Status filter
- Priority filter
- Date filter
- Sort

Main content should be a professional data table.

Columns:

- Case ID
- Case Name
- Lead Investigator
- Priority
- Evidence Count
- Status
- Created
- Updated

Status examples:

- Draft
- Active
- Under Review
- Closed

Priority:

- Low
- Medium
- High
- Critical

Use restrained badges.

Do NOT make every status extremely colorful.

---

## Create Case

Button:

```text
+ New Investigation
```

Open a modal or slide-over panel.

Fields:

- Case ID
- Case Name
- Description
- Priority
- Lead Investigator

The UI should simulate successful case creation using mock state.

---

# 10. Case Details Page

Route:

```text
/cases/:caseId
```

This is one of the most important screens.

The top should show:

```text
CASE-2026-014

Highway Incident Investigation
```

Include:

- Status
- Priority
- Lead Investigator
- Created Date
- Last Updated

Actions:

- Add Evidence
- Generate Report
- Case Settings

---

## Case Navigation Tabs

Use tabs:

- Overview
- Evidence
- Devices
- Timeline
- Analysis
- Activity

---

## Overview Tab

Show:

### Case Summary

Description of the investigation.

### Investigation Statistics

- Evidence
- Devices
- Recordings
- Alerts

### Investigation Progress

A visual progress indicator.

Example:

```text
Evidence Registration      COMPLETE
Integrity Verification     COMPLETE
Media Processing          IN PROGRESS
AI Analysis               IN PROGRESS
Final Review              PENDING
```

### Evidence Summary

Compact list of recent evidence.

### Device Map

Optional conceptual visualization of device relationships.

---

# 11. Evidence Page

Route:

```text
/evidence
```

This page should feel highly forensic.

Main table:

Columns:

- Evidence ID
- Case
- Source Type
- File
- Size
- SHA-256 Status
- MD5 Status
- Registration Time
- Status

Example:

```text
EVID-00482
CASE-2026-014
Forensic Image
highway_dvr.img
128.4 GB
VERIFIED
VERIFIED
Today 10:21
ACTIVE
```

Provide:

- Search
- Filter
- Case filter
- Source type filter
- Integrity status filter

---

# 12. Evidence Details Page

Route:

```text
/evidence/:evidenceId
```

This should be a premium forensic inspection interface.

---

## Evidence Header

Show:

```text
EVID-00482

Highway DVR Forensic Image
```

Status:

```text
INTEGRITY VERIFIED
```

Actions:

- Verify Hash
- Generate Manifest
- View Chain of Custody
- Export Metadata

---

## Evidence Information

Display:

- Evidence ID
- Case
- Source Type
- Original Source
- File Size
- Registration Date
- Registered By
- Current Status

---

## Integrity Section

Prominently display:

### SHA-256

Full value.

Example:

```text
a4f91c8d6e...
```

### MD5

Full value.

Example:

```text
f12a9e...
```

Status:

```text
VERIFIED
```

Include copy buttons.

---

## Integrity Verification History

Timeline:

```text
2026-08-26 10:21
SHA-256 verified successfully

2026-08-26 10:20
MD5 verified successfully

2026-08-26 10:18
Evidence registered
```

---

## Evidence Manifest

Show a structured JSON-like preview.

Example:

```json
{
  "evidence_id": "EVID-00482",
  "hashes": {
    "sha256": "...",
    "md5": "..."
  },
  "generated_at": "..."
}
```

Do not require actual cryptographic functionality beyond mock data.

---

# 13. Devices Page

Route:

```text
/devices
```

Display connected or registered forensic devices.

Examples:

- CCTV DVR
- NVR
- Camera
- Storage Device
- Mobile Device
- Forensic Image Source

Each device card or table row should show:

- Device ID
- Type
- Manufacturer
- Model
- Status
- Storage
- Last Activity

Device status:

- Online
- Offline
- Analyzing
- Error

---

## Device Details

Include:

- Device metadata
- Associated evidence
- Recordings
- Storage information
- Acquisition history

---

# 14. Media Analysis Page

Route:

```text
/analysis
```

This should be one of the visually strongest pages.

Layout:

Left:

- Recording list
- Filters

Center:

- Large video preview area

Right:

- AI analysis panel
- Metadata
- Detection summary

Since no real backend exists, use:

- Placeholder video
- Mock playback
- Simulated timeline
- Generated detection events

---

## Video Player

Create a professional analysis workspace.

Controls:

- Play/Pause
- Current timestamp
- Playback speed
- Volume
- Fullscreen

Below:

### Forensic Timeline

Show events such as:

```text
00:02:18
Person detected

00:04:32
Vehicle detected

00:05:11
Abnormal movement detected

00:08:45
License plate visible
```

The user should be able to click an event and jump to that simulated timestamp.

---

# 15. AI Analysis Panel

Show:

# AI Analysis

Include:

### Detection Summary

```text
Persons Detected
12

Vehicles Detected
8

Anomalies
3

Important Events
7
```

---

## Detection Timeline

Show events across the recording timeline.

Possible categories:

- Person
- Vehicle
- Object
- Motion
- Anomaly

Use subtle category colors.

---

## AI Confidence

Example:

```text
Person Detection
98.4%

Vehicle Detection
94.2%

Anomaly Detection
87.1%
```

---

# 16. AI Insights Page

Route:

```text
/insights
```

This page should feel like an intelligent forensic assistant.

Show insight cards.

Examples:

### Suspicious Activity

```text
Unusual vehicle movement detected between 22:14 and 22:18.
```

Confidence:

92%

---

### Evidence Correlation

```text
Recording CAM-04 appears temporally correlated with device DVR-UNIT-03.
```

---

### Investigation Recommendation

```text
Review evidence EVID-00491 for potential connection to the detected vehicle.
```

Include:

- Confidence
- Related evidence
- Related recordings
- Timestamp

Do not pretend the AI actually analyzed anything.

Clearly label all analysis as:

```text
Demo Analysis
```

when appropriate.

---

# 17. Timeline Page

Route:

```text
/timeline
```

Create a visual investigation timeline.

Events include:

- Evidence registered
- Device discovered
- Recording acquired
- Hash verified
- AI event detected
- Analysis completed

The timeline should support:

- Zoom concept
- Filtering
- Event categories

This is primarily a visual prototype.

---

# 18. Integrity Page

Route:

```text
/integrity
```

This page should focus on forensic trust.

Main sections:

### Overall Integrity Score

Example:

```text
99.8%
```

### Verification Summary

- SHA-256 verified
- MD5 verified
- Pending verification
- Failed verification

### Recent Verification Activity

### Integrity Alerts

Example:

```text
WARNING
Evidence EVID-00471 requires re-verification.
```

---

# 19. Activity Page

Route:

```text
/activity
```

Show system-wide forensic activity.

Each event should include:

- Timestamp
- User
- Action
- Resource
- Result

Examples:

```text
10:42:21
admin
VERIFIED HASH
EVID-00482
SUCCESS
```

Use a dense professional audit-log table.

---

# 20. Reports Page

Route:

```text
/reports
```

Display generated forensic reports.

Examples:

- Case Summary Report
- Evidence Integrity Report
- Media Analysis Report
- Timeline Report

Status:

- Ready
- Generating
- Draft

Clicking a report can open a polished preview panel.

No actual PDF generation is required.

---

# 21. Settings Page

Route:

```text
/settings
```

Include:

### General

- Application name
- Time zone
- Language

### Evidence Storage

- Evidence Root
- Artifact Root
- Report Root

Display these as mock configuration.

### Appearance

- Dark mode
- Compact mode
- Accent color

Do not build complicated settings persistence unless simple local storage is used.

---

# 22. Mock Data Requirements

Create realistic mock data.

Minimum:

- 8 cases
- 25 evidence records
- 10 devices
- 20 recordings
- 30 activity events
- Multiple AI analysis events
- Multiple integrity verification events

Data should be internally consistent.

For example:

If:

```text
CASE-2026-014
```

contains:

```text
EVID-00482
```

then evidence detail pages should correctly reference that case.

If a device owns recordings, those relationships should also remain consistent.

Do not generate random unrelated data on every render.

Use static mock datasets.

---

# 23. Loading States

Include realistic loading states.

Use:

- Skeletons
- Progress indicators
- Empty states

Do not use excessive spinning loaders.

Example:

```text
Loading evidence metadata...
```

---

# 24. Empty States

Create polished empty states.

Example:

```text
No Evidence Registered

This investigation currently has no registered evidence.

[ Register Evidence ]
```

---

# 25. Error States

Create simulated error components.

Example:

```text
Unable to verify evidence integrity.

The verification service is currently unavailable.

[ Retry ]
```

---

# 26. Notifications

Implement toast notifications.

Examples:

```text
Evidence registered successfully.

SHA-256 verification completed.

Report generation started.

Analysis completed.
```

---

# 27. Animation Guidelines

Animations should be subtle.

Use motion for:

- Page transitions
- Sidebar interaction
- Hover feedback
- Modal transitions
- Timeline interactions
- Loading states

Avoid:

- Excessive floating effects
- Bouncing cards
- Constant glowing
- Large dramatic animations
- Slow transitions

The application should feel fast.

---

# 28. Color System

Primary interface:

- Near-black background
- Dark panels
- Slightly lighter borders
- High-contrast text

Suggested conceptual palette:

Background:

```text
#09090B
```

Surface:

```text
#111113
```

Elevated Surface:

```text
#18181B
```

Border:

```text
#27272A
```

Primary Text:

```text
#F4F4F5
```

Secondary Text:

```text
#A1A1AA
```

Accent:

A restrained cyan or electric blue.

Example:

```text
#22D3EE
```

Status colors:

Success:

Green

Warning:

Amber

Critical:

Red

Information:

Blue

Do not overuse accent colors.

Most of the interface should remain neutral.

---

# 29. Typography

Use a clean modern sans-serif.

Possible:

- Inter
- Geist

Use monospaced typography for:

- Evidence IDs
- Hashes
- Device IDs
- Timestamps
- Technical metadata

Example:

```text
SHA-256
a4f91c8d6e0b...
```

This should feel forensic and technical.

---

# 30. Responsive Requirements

Primary target:

Desktop:

```text
1440px and above
```

Must also work on:

- 1280px
- Tablet
- Mobile

On smaller screens:

- Collapse sidebar.
- Keep tables horizontally scrollable when necessary.
- Prioritize important information.
- Avoid simply shrinking everything.

---

# 31. Accessibility

Include:

- Keyboard navigation where practical
- Visible focus states
- Accessible contrast
- Proper labels
- Semantic buttons
- Tooltips for icon-only controls

---

# 32. Component Architecture

Create reusable components.

Suggested:

```text
components/
├── layout/
│   ├── Sidebar
│   ├── Header
│   └── PageContainer
│
├── dashboard/
│   ├── MetricCard
│   ├── ActivityFeed
│   ├── IntegritySummary
│   └── CaseChart
│
├── evidence/
│   ├── EvidenceTable
│   ├── EvidenceHeader
│   ├── HashCard
│   ├── VerificationTimeline
│   └── ManifestViewer
│
├── analysis/
│   ├── VideoWorkspace
│   ├── AnalysisTimeline
│   ├── DetectionPanel
│   └── AIInsights
│
├── common/
│   ├── EmptyState
│   ├── LoadingState
│   ├── ErrorState
│   ├── StatusBadge
│   └── PageHeader
```

Do not put the entire application in a few massive files.

---

# 33. Routing

Implement routing for:

```text
/
/cases
/cases/:caseId
/evidence
/evidence/:evidenceId
/devices
/analysis
/insights
/timeline
/integrity
/activity
/reports
/settings
```

Navigation should work completely.

Even if some pages are prototype-level, no page should feel unfinished.

---

# 34. Demo Mode

Add a small indicator somewhere subtle:

```text
DEMO MODE
Mock forensic data
```

This should not dominate the interface.

The purpose is to make it clear that:

- Data is simulated.
- Backend integration is not currently active.

---

# 35. Backend Integration Preparation

Although the backend is currently unavailable, the frontend should be structured for future integration.

Avoid hardcoding mock data directly inside large UI components.

Instead use a structure like:

```text
components
    ↓
services
    ↓
mockApi.ts
```

Later:

```text
components
    ↓
services
    ↓
real API
```

The UI should require minimal modification when backend integration begins.

---

# 36. Important Demonstration Flow

The final prototype should support this presentation flow:

## Step 1

Open dashboard.

Show:

- Active investigations
- Evidence count
- Integrity status
- Recent activity

## Step 2

Open an investigation.

Show:

- Case details
- Evidence
- Investigation progress

## Step 3

Open evidence.

Show:

- Source metadata
- SHA-256
- MD5
- Verification history
- Manifest

## Step 4

Open media analysis.

Show:

- CCTV/video interface
- Detection timeline
- AI analysis

## Step 5

Open AI insights.

Show:

- Suspicious activity
- Evidence correlation
- Investigation recommendations

## Step 6

Open timeline.

Show:

- Complete forensic event history

This flow should look like a complete investigation lifecycle.

---

# 37. Implementation Order

Implement in this order.

## Phase A

Application shell:

- Tailwind
- Fonts
- Theme
- Sidebar
- Header
- Routing

## Phase B

Dashboard.

## Phase C

Cases.

## Phase D

Evidence.

## Phase E

Devices.

## Phase F

Media Analysis.

## Phase G

AI Insights.

## Phase H

Timeline.

## Phase I

Integrity.

## Phase J

Activity.

## Phase K

Reports and Settings.

## Final

Polish:

- Empty states
- Loading states
- Error states
- Responsive behavior
- Animation
- Consistency review

---

# 38. Quality Standard

Before considering the frontend complete:

- No broken routes.
- No console errors.
- No obviously unfinished placeholder pages.
- No inconsistent spacing.
- No random colors.
- No generic template appearance.
- No enormous empty areas.
- No excessive card usage.
- No duplicated component code where reusable components are appropriate.
- Mock data must remain consistent across pages.
- The application must look intentional and polished.

The frontend should feel like a real product prototype that could plausibly become the production SIH26150 forensic investigation platform.

---

# 39. Critical Restrictions

Do NOT:

- Implement backend functionality.
- Require a backend server.
- Create real forensic acquisition functionality.
- Create fake claims that real AI analysis occurred.
- Add blockchain.
- Add random futuristic visual effects.
- Add excessive gradients.
- Add unnecessary 3D effects.
- Build speculative backend APIs.
- Modify the backend project.
- Remove existing frontend configuration unless necessary.

The frontend must remain a standalone mock-data demonstration while being architecturally ready for future backend integration.

---

# 40. Final Goal

The finished result should allow a faculty member or SIH evaluator to open the application and immediately understand:

1. What the platform does.
2. How investigations are managed.
3. How evidence is registered.
4. How evidence integrity is maintained.
5. How devices and recordings are tracked.
6. How media is analyzed.
7. How AI-assisted insights could support investigators.
8. What the final SIH26150 platform is intended to become.

The experience should feel coherent from beginning to end.

Do not rush implementation by creating generic pages.

Build a consistent forensic investigation platform with a strong visual identity.

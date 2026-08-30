export type CasePriority = 'Low' | 'Medium' | 'High' | 'Critical'
export type CaseStatus = 'Draft' | 'Active' | 'Under Review' | 'Closed'

export interface ProgressStep {
  label: string
  status: 'Complete' | 'In Progress' | 'Pending'
}

export interface Case {
  id: string
  name: string
  description: string
  priority: CasePriority
  status: CaseStatus
  leadInvestigator: string
  createdAt: string
  updatedAt: string
  progress: ProgressStep[]
}

export type SourceType =
  | 'Forensic Image'
  | 'CCTV Recording'
  | 'Mobile Extraction'
  | 'Document'
  | 'Photograph'
  | 'Audio Recording'

export type HashStatus = 'Verified' | 'Pending' | 'Failed' | 'Warning'
export type EvidenceStatus = 'Active' | 'Archived' | 'Flagged'

export interface VerificationEvent {
  timestamp: string
  label: string
  algorithm: 'SHA-256' | 'MD5' | null
  result: 'Success' | 'Failure'
}

export type BlockchainAnchorStatus = 'Demo Verified' | 'Pending Anchor' | 'Not Anchored'

/**
 * A frontend-only, clearly-labeled SIMULATION of a blockchain evidence
 * anchor. No blockchain transaction of any kind occurs — this exists purely
 * to visually represent the concept for demo purposes.
 */
export interface BlockchainAnchor {
  status: BlockchainAnchorStatus
  fingerprint: string
  referenceId: string
  anchoredAt: string | null
}

export type CustodyStage = 'Received' | 'Acquired' | 'Hashed' | 'Processed' | 'Recovered' | 'Analyzed' | 'Verified' | 'Exported'

export interface CustodyEvent {
  stage: CustodyStage
  timestamp: string
  actor: string
  action: string
  result: 'Success' | 'Warning' | 'Failure'
}

export interface Evidence {
  id: string
  caseId: string
  sourceType: SourceType
  fileName: string
  originalSource: string
  fileSize: number
  sha256: string
  md5: string
  sha256Status: HashStatus
  md5Status: HashStatus
  registeredAt: string
  registeredBy: string
  status: EvidenceStatus
  verificationHistory: VerificationEvent[]
  blockchainAnchor: BlockchainAnchor
  custodyLog: CustodyEvent[]
}

export type DeviceType =
  | 'CCTV DVR'
  | 'NVR'
  | 'Camera'
  | 'Storage Device'
  | 'Mobile Device'
  | 'Forensic Image Source'

export type DeviceStatus = 'Online' | 'Offline' | 'Analyzing' | 'Error'

export interface Device {
  id: string
  type: DeviceType
  manufacturer: string
  model: string
  firmware: string
  serialNumber: string
  channelCount: number
  cameraCount: number
  identificationMethod: string
  identificationConfidence: number
  status: DeviceStatus
  storageTotal: number
  storageUsed: number
  lastActivity: string
  caseId: string
  acquisitionHistory: { timestamp: string; action: string }[]
}

export type DetectionCategory = 'Person' | 'Vehicle' | 'Object' | 'Motion' | 'Anomaly'
export type ReviewStatus = 'Unreviewed' | 'Confirmed' | 'Dismissed'

export interface DetectionEvent {
  timestampSeconds: number
  category: DetectionCategory
  label: string
  confidence: number
  reviewStatus: ReviewStatus
}

export type RecordingType = 'Continuous' | 'Motion-Triggered' | 'Scheduled' | 'Manual Export'
export type ExtractionStatus = 'Extracted' | 'Partially Extracted' | 'Failed'

export interface Recording {
  id: string
  deviceId: string
  caseId: string
  cameraChannel: string
  durationSeconds: number
  resolution: string
  fps: number
  codec: string
  container: string
  recordingType: RecordingType
  extractionStatus: ExtractionStatus
  fileSize: number
  recordedAt: string
  /** Original device-reported start time, preserved verbatim — never overwritten by normalization. */
  originalTimezone: string
  normalizedStartAt: string
  timestampOffset: string
  normalizationMethod: string
  aiModel: string
  aiModelVersion: string
  detectionEvents: DetectionEvent[]
}

export type ActivityResult = 'Success' | 'Failure' | 'Warning'

export interface ActivityEvent {
  id: string
  timestamp: string
  user: string
  action: string
  resource: string
  resourceId: string
  result: ActivityResult
  caseId?: string
}

export type InsightType = 'Suspicious Activity' | 'Evidence Correlation' | 'Investigation Recommendation'

export interface AIInsight {
  id: string
  type: InsightType
  title: string
  description: string
  confidence: number
  relatedEvidence: string[]
  relatedRecordings: string[]
  timestamp: string
  caseId: string
}

export type TimelineEventCategory =
  | 'Evidence Registered'
  | 'Device Discovered'
  | 'Recording Acquired'
  | 'Hash Verified'
  | 'AI Event Detected'
  | 'Analysis Completed'
  | 'Case Update'

export interface TimelineEvent {
  id: string
  timestamp: string
  category: TimelineEventCategory
  title: string
  description: string
  caseId: string
  resourceId?: string
}

export interface IntegrityAlert {
  id: string
  severity: 'Warning' | 'Critical'
  message: string
  evidenceId: string
  timestamp: string
}

export type ReportType = 'Case Summary' | 'Evidence Integrity' | 'Media Analysis' | 'Timeline' | 'Full Forensic Report'
export type ReportStatus = 'Ready' | 'Generating' | 'Draft'

export interface Report {
  id: string
  name: string
  type: ReportType
  caseId: string
  status: ReportStatus
  generatedAt: string | null
  summary: string
}

// ---------------------------------------------------------------------------
// Acquisition & filesystem/format analysis
// ---------------------------------------------------------------------------

export type AcquisitionStatus = 'Pending' | 'In Progress' | 'Completed' | 'Warning' | 'Failed'
export type AcquisitionMethod =
  | 'Live Logical Acquisition'
  | 'Physical Image'
  | 'Vendor SDK Export'
  | 'Network Stream Capture'
  | 'Manual File Export'

export interface FilesystemPartition {
  name: string
  sizeBytes: number
  type: string
  status: 'Recognized' | 'Partial' | 'Unrecognized'
}

export interface FilesystemAnalysis {
  detectedFormat: string
  vendorStructure: string
  parserUsed: string
  parsingStatus: 'Success' | 'Partial' | 'Failed'
  partitions: FilesystemPartition[]
  recognizedStructures: string[]
  unsupportedStructures: string[]
  warnings: string[]
}

export interface AcquisitionJob {
  id: string
  caseId: string
  evidenceId: string
  deviceId: string
  vendor: string
  model: string
  firmware: string
  storageCapacity: number
  channelCount: number
  acquisitionMethod: AcquisitionMethod
  status: AcquisitionStatus
  progressPercent: number
  startedAt: string
  completedAt: string | null
  hashAlgorithm: 'SHA-256'
  hashResult: string | null
  warnings: string[]
  filesystem: FilesystemAnalysis
}

// ---------------------------------------------------------------------------
// Recovery
// ---------------------------------------------------------------------------

export type RecoveryItemStatus = 'Recovered' | 'Fragmented' | 'Deleted' | 'Damaged' | 'Unrecoverable'

export interface RecoveryItem {
  id: string
  cameraChannel: string
  timeRangeStart: string
  timeRangeEnd: string
  status: RecoveryItemStatus
  confidence: number
  sourceLocation: string
}

export interface RecoveryReport {
  id: string
  caseId: string
  evidenceId: string
  deviceId: string
  totalRecordings: number
  recovered: number
  fragmented: number
  deleted: number
  damaged: number
  unrecoverable: number
  confidencePercent: number
  method: string
  limitations: string[]
  items: RecoveryItem[]
}

// ---------------------------------------------------------------------------
// Cross-camera correlation
// ---------------------------------------------------------------------------

export interface CorrelationEvent {
  id: string
  caseId: string
  title: string
  description: string
  normalizedTimestamp: string
  cameraChannels: string[]
  recordings: string[]
  relatedEvidence: string[]
  confidence: number
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

export type ValidationStatus = 'Pass' | 'Warning' | 'Fail'

export interface ValidationCheck {
  id: string
  caseId: string
  category: string
  expected: string
  actual: string
  falsePositives: number
  falseNegatives: number
  accuracyPercent: number
  status: ValidationStatus
  notes: string
  groundTruthSource: string
}

// ---------------------------------------------------------------------------
// Multi-vendor normalization
// ---------------------------------------------------------------------------

export type VendorSupportLevel = 'Full' | 'Partial' | 'Experimental'

export interface VendorProfile {
  vendor: string
  adapter: string
  supportLevel: VendorSupportLevel
  supportedModels: string[]
  formatsSupported: string[]
  notes: string
}

// ---------------------------------------------------------------------------
// Admin console (mock only — no real authorization)
// ---------------------------------------------------------------------------

export interface SystemService {
  name: string
  status: 'Online' | 'Degraded' | 'Offline'
  loadPercent: number
  failedJobsToday: number
}

export type Clearance = 'L1' | 'L2' | 'L3'

export interface AdminUser {
  id: string
  name: string
  roleLabel: 'Investigator' | 'Team Lead' | 'Director' | 'Administrator'
  clearance: Clearance
  caseIds: string[]
}

export interface SecurityEvent {
  id: string
  timestamp: string
  type: 'Access Denied' | 'Integrity Alert' | 'Unusual Activity' | 'Login Failure'
  message: string
  severity: 'Warning' | 'Critical'
  actor: string
}

export interface AIServiceStatus {
  model: string
  version: string
  status: 'Online' | 'Degraded' | 'Offline'
  queueLength: number
  processedToday: number
  failedJobs: number
}

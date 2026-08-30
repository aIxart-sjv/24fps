import {
  ACQUISITION_JOBS,
  ACTIVITY,
  ADMIN_USERS,
  AI_INSIGHTS,
  AI_SERVICE_STATUSES,
  CASES,
  CORRELATION_EVENTS,
  DEVICES,
  EVIDENCE,
  INTEGRITY_ALERTS,
  RECORDINGS,
  RECOVERY_REPORTS,
  REPORTS,
  SECURITY_EVENTS,
  SYSTEM_SERVICES,
  TIMELINE_EVENTS,
  VALIDATION_CHECKS,
  VENDOR_PROFILES,
} from '@/data/mockData'
import type {
  ActivityEvent,
  AcquisitionJob,
  AdminUser,
  AIInsight,
  AIServiceStatus,
  Case,
  CorrelationEvent,
  Device,
  Evidence,
  IntegrityAlert,
  Recording,
  RecoveryReport,
  Report,
  SecurityEvent,
  SourceType,
  SystemService,
  TimelineEvent,
  ValidationCheck,
  VendorProfile,
} from './types'

/**
 * Mock API layer. Every function is async and resolves with a small
 * artificial delay, mirroring the shape a real backend client will have.
 * When the backend is ready, these bodies swap for fetch() calls — callers
 * do not change.
 *
 * List getters always return a fresh array copy rather than the live source
 * array. Components hold the resolved array in state; if a later create/update
 * call mutated the same array in place (e.g. via unshift), every component
 * already holding that reference would silently gain the new item too, and a
 * subsequent "prepend to state" update would then duplicate it.
 */

function delay<T>(value: T, ms = 350): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms))
}

export function getCases(): Promise<Case[]> {
  return delay([...CASES])
}

export function getCaseById(id: string): Promise<Case | undefined> {
  return delay(CASES.find((c) => c.id === id))
}

export function getEvidence(): Promise<Evidence[]> {
  return delay([...EVIDENCE])
}

export function getEvidenceById(id: string): Promise<Evidence | undefined> {
  return delay(EVIDENCE.find((e) => e.id === id))
}

export function getEvidenceByCase(caseId: string): Promise<Evidence[]> {
  return delay(EVIDENCE.filter((e) => e.caseId === caseId))
}

export function getDevices(): Promise<Device[]> {
  return delay([...DEVICES])
}

export function getDeviceById(id: string): Promise<Device | undefined> {
  return delay(DEVICES.find((d) => d.id === id))
}

export function getDevicesByCase(caseId: string): Promise<Device[]> {
  return delay(DEVICES.filter((d) => d.caseId === caseId))
}

export function getRecordings(): Promise<Recording[]> {
  return delay([...RECORDINGS])
}

export function getRecordingById(id: string): Promise<Recording | undefined> {
  return delay(RECORDINGS.find((r) => r.id === id))
}

export function getRecordingsByCase(caseId: string): Promise<Recording[]> {
  return delay(RECORDINGS.filter((r) => r.caseId === caseId))
}

export function getRecordingsByDevice(deviceId: string): Promise<Recording[]> {
  return delay(RECORDINGS.filter((r) => r.deviceId === deviceId))
}

export function getActivity(): Promise<ActivityEvent[]> {
  return delay([...ACTIVITY])
}

export function getActivityByCase(caseId: string): Promise<ActivityEvent[]> {
  return delay(ACTIVITY.filter((a) => a.caseId === caseId))
}

export function getAIInsights(): Promise<AIInsight[]> {
  return delay([...AI_INSIGHTS])
}

export function getAIInsightsByCase(caseId: string): Promise<AIInsight[]> {
  return delay(AI_INSIGHTS.filter((i) => i.caseId === caseId))
}

export function getIntegrityAlerts(): Promise<IntegrityAlert[]> {
  return delay([...INTEGRITY_ALERTS])
}

export function getTimelineEvents(): Promise<TimelineEvent[]> {
  return delay([...TIMELINE_EVENTS])
}

export function getTimelineEventsByCase(caseId: string): Promise<TimelineEvent[]> {
  return delay(TIMELINE_EVENTS.filter((t) => t.caseId === caseId))
}

export function getReports(): Promise<Report[]> {
  return delay([...REPORTS])
}

export function getReportsByCase(caseId: string): Promise<Report[]> {
  return delay(REPORTS.filter((r) => r.caseId === caseId))
}

export function getReportById(id: string): Promise<Report | undefined> {
  return delay(REPORTS.find((r) => r.id === id))
}

export function getAcquisitionJobs(): Promise<AcquisitionJob[]> {
  return delay([...ACQUISITION_JOBS])
}

export function getAcquisitionJobsByCase(caseId: string): Promise<AcquisitionJob[]> {
  return delay(ACQUISITION_JOBS.filter((a) => a.caseId === caseId))
}

export function getAcquisitionJobByEvidence(evidenceId: string): Promise<AcquisitionJob | undefined> {
  return delay(ACQUISITION_JOBS.find((a) => a.evidenceId === evidenceId))
}

export function getRecoveryReports(): Promise<RecoveryReport[]> {
  return delay([...RECOVERY_REPORTS])
}

export function getRecoveryReportsByCase(caseId: string): Promise<RecoveryReport[]> {
  return delay(RECOVERY_REPORTS.filter((r) => r.caseId === caseId))
}

export function getCorrelationEvents(): Promise<CorrelationEvent[]> {
  return delay([...CORRELATION_EVENTS])
}

export function getCorrelationEventsByCase(caseId: string): Promise<CorrelationEvent[]> {
  return delay(CORRELATION_EVENTS.filter((c) => c.caseId === caseId))
}

export function getValidationChecks(): Promise<ValidationCheck[]> {
  return delay([...VALIDATION_CHECKS])
}

export function getValidationChecksByCase(caseId: string): Promise<ValidationCheck[]> {
  return delay(VALIDATION_CHECKS.filter((v) => v.caseId === caseId))
}

export function getVendorProfiles(): Promise<VendorProfile[]> {
  return delay([...VENDOR_PROFILES])
}

export function getSystemServices(): Promise<SystemService[]> {
  return delay([...SYSTEM_SERVICES])
}

export function getAdminUsers(): Promise<AdminUser[]> {
  return delay([...ADMIN_USERS])
}

export function getSecurityEvents(): Promise<SecurityEvent[]> {
  return delay([...SECURITY_EVENTS])
}

export function getAIServiceStatuses(): Promise<AIServiceStatus[]> {
  return delay([...AI_SERVICE_STATUSES])
}

let nextCaseNumber = 15

export function createCase(input: {
  name: string
  description: string
  priority: Case['priority']
  leadInvestigator: string
}): Promise<Case> {
  const id = `CASE-2026-${String(nextCaseNumber++).padStart(3, '0')}`
  const now = new Date().toISOString().slice(0, 19)
  const newCase: Case = {
    id,
    name: input.name,
    description: input.description,
    priority: input.priority,
    status: 'Draft',
    leadInvestigator: input.leadInvestigator,
    createdAt: now,
    updatedAt: now,
    progress: [
      { label: 'Evidence Registration', status: 'Pending' },
      { label: 'Integrity Verification', status: 'Pending' },
      { label: 'Media Processing', status: 'Pending' },
      { label: 'AI Analysis', status: 'Pending' },
      { label: 'Final Review', status: 'Pending' },
    ],
  }
  CASES.unshift(newCase)
  return delay(newCase, 500)
}

let nextEvidenceNumber = 500

export function createEvidence(input: {
  caseId: string
  fileName: string
  sourceType: SourceType
  originalSource: string
}): Promise<Evidence> {
  const id = `EVID-${String(nextEvidenceNumber++).padStart(5, '0')}`
  const now = new Date().toISOString().slice(0, 19)
  const evidence: Evidence = {
    id,
    caseId: input.caseId,
    sourceType: input.sourceType,
    fileName: input.fileName,
    originalSource: input.originalSource,
    fileSize: 0,
    sha256: '',
    md5: '',
    sha256Status: 'Pending',
    md5Status: 'Pending',
    registeredAt: now,
    registeredBy: 'admin',
    status: 'Active',
    verificationHistory: [{ timestamp: now, label: 'Evidence registered', algorithm: null, result: 'Success' }],
    blockchainAnchor: { status: 'Pending Anchor', fingerprint: '', referenceId: '', anchoredAt: null },
    custodyLog: [{ stage: 'Received', timestamp: now, actor: 'admin', action: 'Evidence received into custody and logged', result: 'Success' }],
  }
  EVIDENCE.unshift(evidence)
  return delay(evidence, 500)
}

export function updateCaseStatus(caseId: string, status: Case['status']): Promise<Case | undefined> {
  const index = CASES.findIndex((c) => c.id === caseId)
  if (index === -1) return delay(undefined, 400)
  const updated: Case = { ...CASES[index], status, updatedAt: new Date().toISOString().slice(0, 19) }
  CASES[index] = updated
  return delay(updated, 400)
}

let nextReportNumber = 1100

export function generateReport(caseId: string, caseName: string): Promise<Report> {
  const report: Report = {
    id: `RPT-${nextReportNumber++}`,
    name: `${caseName} — Case Summary`,
    type: 'Case Summary',
    caseId,
    status: 'Generating',
    generatedAt: null,
    summary: `Consolidated overview of case status, evidence registration, and investigation progress for ${caseId}.`,
  }
  REPORTS.unshift(report)
  return delay(report, 500)
}

export function verifyEvidenceHash(evidenceId: string): Promise<Evidence | undefined> {
  const index = EVIDENCE.findIndex((e) => e.id === evidenceId)
  if (index === -1) return delay(undefined, 900)
  const now = new Date().toISOString().slice(0, 19)
  const updated: Evidence = {
    ...EVIDENCE[index],
    sha256Status: 'Verified',
    md5Status: 'Verified',
    verificationHistory: [
      { timestamp: now, label: 'SHA-256 re-verified successfully', algorithm: 'SHA-256', result: 'Success' },
      { timestamp: now, label: 'MD5 re-verified successfully', algorithm: 'MD5', result: 'Success' },
      ...EVIDENCE[index].verificationHistory,
    ],
  }
  EVIDENCE[index] = updated
  return delay(updated, 900)
}

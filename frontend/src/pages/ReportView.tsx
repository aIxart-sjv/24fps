import { useEffect, useState } from 'react'
import { ChevronLeft, Download, ScanEye } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { StatusBadge } from '@/components/common/StatusBadge'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { CustodyTimeline } from '@/components/evidence/CustodyTimeline'
import { useToast } from '@/hooks/useToast'
import { formatBytes, formatDateTime } from '@/lib/utils'
import {
  getAcquisitionJobsByCase,
  getCaseById,
  getCorrelationEventsByCase,
  getDevicesByCase,
  getEvidenceByCase,
  getRecordingsByCase,
  getRecoveryReportsByCase,
  getReportById,
  getValidationChecksByCase,
} from '@/services/mockApi'
import type {
  AcquisitionJob,
  Case,
  CorrelationEvent,
  Device,
  Evidence,
  Recording,
  RecoveryReport,
  ValidationCheck,
} from '@/services/types'

interface ReportData {
  caseInfo: Case
  evidence: Evidence[]
  devices: Device[]
  acquisitionJobs: AcquisitionJob[]
  recordings: Recording[]
  recoveryReports: RecoveryReport[]
  correlationEvents: CorrelationEvent[]
  validationChecks: ValidationCheck[]
  reportName: string
  reportId: string
}

export function ReportView() {
  const { reportId } = useParams<{ reportId: string }>()
  const navigate = useNavigate()
  const { notify } = useToast()
  const [data, setData] = useState<ReportData | null | undefined>(undefined)

  useEffect(() => {
    if (!reportId) return
    ;(async () => {
      const report = await getReportById(reportId)
      if (!report) {
        setData(null)
        return
      }
      const [caseInfo, evidence, devices, acquisitionJobs, recordings, recoveryReports, correlationEvents, validationChecks] = await Promise.all([
        getCaseById(report.caseId),
        getEvidenceByCase(report.caseId),
        getDevicesByCase(report.caseId),
        getAcquisitionJobsByCase(report.caseId),
        getRecordingsByCase(report.caseId),
        getRecoveryReportsByCase(report.caseId),
        getCorrelationEventsByCase(report.caseId),
        getValidationChecksByCase(report.caseId),
      ])
      if (!caseInfo) {
        setData(null)
        return
      }
      setData({
        caseInfo,
        evidence,
        devices,
        acquisitionJobs,
        recordings,
        recoveryReports,
        correlationEvents,
        validationChecks,
        reportName: report.name,
        reportId: report.id,
      })
    })()
  }, [reportId])

  if (data === undefined) return <LoadingState label="Assembling forensic report..." />
  if (data === null) {
    return <ErrorState title="Report not found" description={`No report record exists for ${reportId}.`} onRetry={() => navigate('/reports')} />
  }

  const { caseInfo, evidence, devices, acquisitionJobs, recordings, recoveryReports, correlationEvents, validationChecks } = data
  const allDetections = recordings.flatMap((r) => r.detectionEvents.map((e) => ({ ...e, recordingId: r.id })))

  return (
    <>
      <div className="mb-4 flex items-center justify-between">
        <Link to="/reports" className="inline-flex items-center gap-1 text-xs text-fg-muted hover:text-fg">
          <ChevronLeft className="h-3.5 w-3.5" />
          Back to Reports
        </Link>
        <Button
          variant="primary"
          size="sm"
          onClick={() => notify('Report export started', { description: `${data.reportId}.pdf`, tone: 'success' })}
        >
          <Download className="h-4 w-4" />
          Export PDF (Demo)
        </Button>
      </div>

      <div className="rounded-lg border border-border bg-surface">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-md border border-accent/30 bg-accent/10">
              <ScanEye className="h-5 w-5 text-accent" />
            </div>
            <div>
              <p className="text-lg font-semibold text-fg">{data.reportName}</p>
              <p className="font-mono text-xs text-fg-subtle">
                {data.reportId} · Standardized Forensic Report · Generated {formatDateTime(new Date().toISOString().slice(0, 19))}
              </p>
            </div>
          </div>
          <Badge tone="accent">Demo / Simulated Data</Badge>
        </div>

        <div className="space-y-6 p-5">
          <Section title="1. Case Information">
            <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
              <F label="Case ID" value={caseInfo.id} mono />
              <F label="Case Name" value={caseInfo.name} />
              <F label="Priority" value={caseInfo.priority} />
              <F label="Status" value={caseInfo.status} />
              <F label="Lead Investigator" value={caseInfo.leadInvestigator} />
              <F label="Opened" value={formatDateTime(caseInfo.createdAt)} />
            </div>
            <p className="mt-3 text-sm text-fg-muted">{caseInfo.description}</p>
          </Section>

          <Section title="2. Evidence Details">
            <TableWrap>
              <thead>
                <tr className="border-b border-border text-left text-xs text-fg-subtle">
                  <th className="px-3 py-2 font-medium">Evidence ID</th>
                  <th className="px-3 py-2 font-medium">Source Type</th>
                  <th className="px-3 py-2 font-medium">File Name</th>
                  <th className="px-3 py-2 font-medium">Size</th>
                  <th className="px-3 py-2 font-medium">SHA-256</th>
                  <th className="px-3 py-2 font-medium">MD5</th>
                </tr>
              </thead>
              <tbody>
                {evidence.map((e) => (
                  <tr key={e.id} className="border-b border-border/60 last:border-0">
                    <td className="px-3 py-2 font-mono text-xs text-accent">{e.id}</td>
                    <td className="px-3 py-2 text-fg-muted">{e.sourceType}</td>
                    <td className="px-3 py-2 text-fg">{e.fileName}</td>
                    <td className="px-3 py-2 font-mono text-xs text-fg-subtle">{formatBytes(e.fileSize)}</td>
                    <td className="px-3 py-2"><StatusBadge status={e.sha256Status} /></td>
                    <td className="px-3 py-2"><StatusBadge status={e.md5Status} /></td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </Section>

          <Section title="3. Device Identification">
            <TableWrap>
              <thead>
                <tr className="border-b border-border text-left text-xs text-fg-subtle">
                  <th className="px-3 py-2 font-medium">Device</th>
                  <th className="px-3 py-2 font-medium">Vendor / Model</th>
                  <th className="px-3 py-2 font-medium">Firmware</th>
                  <th className="px-3 py-2 font-medium">Channels</th>
                  <th className="px-3 py-2 font-medium">ID Method</th>
                  <th className="px-3 py-2 font-medium">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {devices.map((d) => (
                  <tr key={d.id} className="border-b border-border/60 last:border-0">
                    <td className="px-3 py-2 font-mono text-xs text-accent">{d.id}</td>
                    <td className="px-3 py-2 text-fg">{d.manufacturer} {d.model}</td>
                    <td className="px-3 py-2 font-mono text-xs text-fg-muted">{d.firmware}</td>
                    <td className="px-3 py-2 text-fg-subtle">{d.channelCount}</td>
                    <td className="px-3 py-2 text-fg-muted">{d.identificationMethod}</td>
                    <td className="px-3 py-2 font-mono text-xs text-fg-subtle">{Math.round(d.identificationConfidence * 100)}%</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </Section>

          <Section title="4. Acquisition & Filesystem Findings">
            <div className="space-y-3">
              {acquisitionJobs.map((job) => (
                <div key={job.id} className="rounded-md border border-border p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-mono text-xs text-accent">{job.id} — {job.vendor} {job.model}</p>
                    <StatusBadge status={job.status} />
                  </div>
                  <p className="mt-1.5 text-xs text-fg-muted">
                    Method: {job.acquisitionMethod} · Format: {job.filesystem.detectedFormat} · Parser: {job.filesystem.parserUsed} · Parsing: {job.filesystem.parsingStatus}
                  </p>
                  {job.warnings.length > 0 && <p className="mt-1 text-xs text-warning">⚠ {job.warnings.join('; ')}</p>}
                </div>
              ))}
              {acquisitionJobs.length === 0 && <p className="text-xs text-fg-subtle">No acquisition jobs recorded for this case.</p>}
            </div>
          </Section>

          <Section title="5. Recovered Recordings">
            {recoveryReports.map((r) => (
              <div key={r.id} className="mb-3 rounded-md border border-border p-3 last:mb-0">
                <p className="font-mono text-xs text-fg-subtle">
                  {r.deviceId} — Total {r.totalRecordings} · Recovered {r.recovered} · Fragmented {r.fragmented} · Deleted {r.deleted} · Damaged {r.damaged} · Unrecoverable {r.unrecoverable}
                </p>
                <p className="mt-1 text-xs text-fg-muted">Method: {r.method} · Confidence: {r.confidencePercent}%</p>
                {r.limitations.length > 0 && <p className="mt-1 text-xs text-warning">Limitations: {r.limitations.join('; ')}</p>}
              </div>
            ))}
            {recoveryReports.length === 0 && <p className="text-xs text-fg-subtle">No recovery was required for this case.</p>}
          </Section>

          <Section title="6. Timestamps (Original & Normalized)">
            <TableWrap>
              <thead>
                <tr className="border-b border-border text-left text-xs text-fg-subtle">
                  <th className="px-3 py-2 font-medium">Recording</th>
                  <th className="px-3 py-2 font-medium">Original</th>
                  <th className="px-3 py-2 font-medium">Normalized (UTC)</th>
                  <th className="px-3 py-2 font-medium">Offset</th>
                </tr>
              </thead>
              <tbody>
                {recordings.map((r) => (
                  <tr key={r.id} className="border-b border-border/60 last:border-0">
                    <td className="px-3 py-2 font-mono text-xs text-accent">{r.id}</td>
                    <td className="px-3 py-2 font-mono text-xs text-fg-muted">{formatDateTime(r.recordedAt)} {r.originalTimezone}</td>
                    <td className="px-3 py-2 font-mono text-xs text-fg-muted">{formatDateTime(r.normalizedStartAt)}</td>
                    <td className="px-3 py-2 font-mono text-xs text-fg-subtle">{r.timestampOffset}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </Section>

          <Section title="7. Cross-Camera Correlation">
            {correlationEvents.map((c) => (
              <div key={c.id} className="mb-3 rounded-md border border-border p-3 last:mb-0">
                <p className="text-sm text-fg">{c.title}</p>
                <p className="mt-1 text-xs text-fg-muted">{c.description}</p>
                <p className="mt-1.5 font-mono text-[11px] text-fg-subtle">
                  {c.cameraChannels.join(', ')} · {formatDateTime(c.normalizedTimestamp)} UTC · Confidence {Math.round(c.confidence * 100)}%
                </p>
              </div>
            ))}
            {correlationEvents.length === 0 && <p className="text-xs text-fg-subtle">No cross-camera correlations identified for this case.</p>}
          </Section>

          <Section title="8. AI Findings (Demo Analysis)">
            <TableWrap>
              <thead>
                <tr className="border-b border-border text-left text-xs text-fg-subtle">
                  <th className="px-3 py-2 font-medium">Recording</th>
                  <th className="px-3 py-2 font-medium">Finding</th>
                  <th className="px-3 py-2 font-medium">Confidence</th>
                  <th className="px-3 py-2 font-medium">Review Status</th>
                </tr>
              </thead>
              <tbody>
                {allDetections.map((d, i) => (
                  <tr key={i} className="border-b border-border/60 last:border-0">
                    <td className="px-3 py-2 font-mono text-xs text-accent">{d.recordingId}</td>
                    <td className="px-3 py-2 text-fg">{d.label}</td>
                    <td className="px-3 py-2 font-mono text-xs text-fg-subtle">{(d.confidence * 100).toFixed(1)}%</td>
                    <td className="px-3 py-2"><StatusBadge status={d.reviewStatus} /></td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
            <p className="mt-2 text-[10px] uppercase tracking-wide text-fg-subtle">DEMO ANALYSIS — simulated inference, not real model output</p>
          </Section>

          <Section title="9. Hashes & Blockchain Anchoring">
            <TableWrap>
              <thead>
                <tr className="border-b border-border text-left text-xs text-fg-subtle">
                  <th className="px-3 py-2 font-medium">Evidence</th>
                  <th className="px-3 py-2 font-medium">SHA-256</th>
                  <th className="px-3 py-2 font-medium">MD5</th>
                  <th className="px-3 py-2 font-medium">Blockchain Anchor</th>
                </tr>
              </thead>
              <tbody>
                {evidence.map((e) => (
                  <tr key={e.id} className="border-b border-border/60 last:border-0">
                    <td className="px-3 py-2 font-mono text-xs text-accent">{e.id}</td>
                    <td className="px-3 py-2 truncate font-mono text-xs text-fg-muted">{e.sha256.slice(0, 16)}...</td>
                    <td className="px-3 py-2 truncate font-mono text-xs text-fg-muted">{e.md5.slice(0, 16)}...</td>
                    <td className="px-3 py-2"><StatusBadge status={e.blockchainAnchor.status} /></td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </Section>

          <Section title="10. Chain of Custody">
            <div className="space-y-5">
              {evidence.map((e) => (
                <div key={e.id}>
                  <p className="mb-2 font-mono text-xs text-accent">{e.id} — {e.fileName}</p>
                  <CustodyTimeline log={e.custodyLog} />
                </div>
              ))}
            </div>
          </Section>

          <Section title="11. Validation Results">
            <TableWrap>
              <thead>
                <tr className="border-b border-border text-left text-xs text-fg-subtle">
                  <th className="px-3 py-2 font-medium">Category</th>
                  <th className="px-3 py-2 font-medium">Accuracy</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Notes</th>
                </tr>
              </thead>
              <tbody>
                {validationChecks.map((v) => (
                  <tr key={v.id} className="border-b border-border/60 last:border-0">
                    <td className="px-3 py-2 text-fg">{v.category}</td>
                    <td className="px-3 py-2 font-mono text-xs text-fg-subtle">{v.accuracyPercent}%</td>
                    <td className="px-3 py-2"><StatusBadge status={v.status} /></td>
                    <td className="px-3 py-2 text-xs text-fg-muted">{v.notes}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </Section>

          <Section title="12. Limitations">
            <ul className="list-inside list-disc space-y-1 text-sm text-fg-muted">
              {recoveryReports.flatMap((r) => r.limitations).map((l, i) => (
                <li key={i}>{l}</li>
              ))}
              <li>All AI analysis, blockchain anchoring, and acquisition progress in this report are simulated for demonstration purposes.</li>
            </ul>
          </Section>

          <Section title="13. Examiner & Software Information">
            <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
              <F label="Lead Examiner" value={caseInfo.leadInvestigator} />
              <F label="Platform" value="24FPS Digital Forensic Intelligence Platform" />
              <F label="Report Type" value="Full Forensic Report" />
              <F label="Data Mode" value="Simulated / Demo" />
            </div>
          </Section>
        </div>
      </div>
    </>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

function TableWrap({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full min-w-[600px] text-sm">{children}</table>
    </div>
  )
}

function F({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="text-xs font-medium text-fg-subtle">{label}</p>
      <p className={mono ? 'mt-1 font-mono text-sm text-fg' : 'mt-1 text-sm text-fg'}>{value}</p>
    </div>
  )
}

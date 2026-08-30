import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { CheckCircle2, ChevronLeft, Circle, Clock, FilePlus2, FileText, HardDrive, Settings2 } from 'lucide-react'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs'
import { Button } from '@/components/ui/Button'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'
import { EvidenceTable } from '@/components/evidence/EvidenceTable'
import { DeviceTable } from '@/components/devices/DeviceTable'
import { DeviceDetailsPanel } from '@/components/devices/DeviceDetailsPanel'
import { TimelineView } from '@/components/timeline/TimelineView'
import { ActivityTable } from '@/components/activity/ActivityTable'
import { AddEvidenceDialog } from '@/components/cases/AddEvidenceDialog'
import { CaseSettingsDialog } from '@/components/cases/CaseSettingsDialog'
import { useToast } from '@/hooks/useToast'
import { cn, formatDate, formatRelativeTime } from '@/lib/utils'
import {
  getActivityByCase,
  getCaseById,
  getDevicesByCase,
  getEvidenceByCase,
  getRecordingsByCase,
  getTimelineEventsByCase,
  generateReport,
} from '@/services/mockApi'
import type {
  ActivityEvent,
  Case,
  Device,
  Evidence,
  Recording,
  TimelineEvent,
} from '@/services/types'
import { FileSearch } from 'lucide-react'

export function CaseDetails() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const { notify } = useToast()

  const [caseData, setCaseData] = useState<Case | null | undefined>(undefined)
  const [evidence, setEvidence] = useState<Evidence[]>([])
  const [devices, setDevices] = useState<Device[]>([])
  const [recordings, setRecordings] = useState<Recording[]>([])
  const [timeline, setTimeline] = useState<TimelineEvent[]>([])
  const [activity, setActivity] = useState<ActivityEvent[]>([])
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null)
  const [addEvidenceOpen, setAddEvidenceOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)

  useEffect(() => {
    if (!caseId) return
    getCaseById(caseId).then((c) => setCaseData(c ?? null))
    getEvidenceByCase(caseId).then(setEvidence)
    getDevicesByCase(caseId).then(setDevices)
    getRecordingsByCase(caseId).then(setRecordings)
    getTimelineEventsByCase(caseId).then(setTimeline)
    getActivityByCase(caseId).then(setActivity)
  }, [caseId])

  if (caseData === undefined) {
    return <LoadingState label="Loading case details..." />
  }

  if (caseData === null) {
    return (
      <ErrorState
        title="Case not found"
        description={`No investigation exists with ID ${caseId}.`}
        onRetry={() => navigate('/cases')}
      />
    )
  }

  async function handleGenerateReport() {
    if (!caseData) return
    await generateReport(caseData.id, caseData.name)
    notify('Report generation started', { description: `A case summary report is being generated for ${caseData.id}.`, tone: 'info' })
  }

  const alertCount = evidence.filter((e) => e.status === 'Flagged').length

  return (
    <>
      <Link to="/cases" className="mb-4 inline-flex items-center gap-1 text-xs text-fg-muted hover:text-fg">
        <ChevronLeft className="h-3.5 w-3.5" />
        Back to Investigations
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-sm text-fg-subtle">{caseData.id}</p>
          <h1 className="mt-1 text-xl font-semibold tracking-tight text-fg">{caseData.name}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-fg-muted">
            <StatusBadge status={caseData.status} />
            <StatusBadge status={caseData.priority} />
            <span>Lead: {caseData.leadInvestigator}</span>
            <span>Created {formatDate(caseData.createdAt)}</span>
            <span>Updated {formatRelativeTime(caseData.updatedAt)}</span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => setAddEvidenceOpen(true)}>
            <FilePlus2 className="h-4 w-4" />
            Add Evidence
          </Button>
          <Button variant="secondary" size="sm" onClick={handleGenerateReport}>
            <FileText className="h-4 w-4" />
            Generate Report
          </Button>
          <Button variant="outline" size="sm" onClick={() => setSettingsOpen(true)}>
            <Settings2 className="h-4 w-4" />
            Case Settings
          </Button>
        </div>
      </div>

      <Tabs defaultValue="overview" className="mt-6">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="evidence">Evidence ({evidence.length})</TabsTrigger>
          <TabsTrigger value="devices">Devices ({devices.length})</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="analysis">Analysis</TabsTrigger>
          <TabsTrigger value="activity">Activity</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="pt-5">
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader>
                <CardTitle>Case Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed text-fg-muted">{caseData.description}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Investigation Statistics</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-4">
                <Stat label="Evidence" value={evidence.length} />
                <Stat label="Devices" value={devices.length} />
                <Stat label="Recordings" value={recordings.length} />
                <Stat label="Alerts" value={alertCount} />
              </CardContent>
            </Card>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader>
                <CardTitle>Investigation Progress</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1">
                {caseData.progress.map((step) => (
                  <div key={step.label} className="flex items-center justify-between border-b border-border/60 py-2.5 last:border-0">
                    <div className="flex items-center gap-2.5">
                      {step.status === 'Complete' && <CheckCircle2 className="h-4 w-4 text-success" />}
                      {step.status === 'In Progress' && <Clock className="h-4 w-4 text-accent" />}
                      {step.status === 'Pending' && <Circle className="h-4 w-4 text-fg-subtle" />}
                      <span className="text-sm text-fg">{step.label}</span>
                    </div>
                    <span
                      className={cn(
                        'text-xs font-medium uppercase tracking-wide',
                        step.status === 'Complete' && 'text-success',
                        step.status === 'In Progress' && 'text-accent',
                        step.status === 'Pending' && 'text-fg-subtle',
                      )}
                    >
                      {step.status}
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Device Network</CardTitle>
              </CardHeader>
              <CardContent>
                {devices.length === 0 ? (
                  <p className="text-xs text-fg-subtle">No devices registered to this case.</p>
                ) : (
                  <div className="space-y-2.5">
                    {devices.map((d) => (
                      <div key={d.id} className="flex items-center gap-2.5 rounded-md border border-border bg-surface-elevated px-3 py-2">
                        <HardDrive className="h-3.5 w-3.5 shrink-0 text-fg-subtle" />
                        <span className="min-w-0 flex-1 truncate font-mono text-xs text-fg">{d.id}</span>
                        <StatusBadge status={d.status} />
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="mt-4">
            <CardHeader>
              <CardTitle>Evidence Summary</CardTitle>
            </CardHeader>
            <CardContent>
              {evidence.length === 0 ? (
                <EmptyState
                  icon={FileSearch}
                  title="No Evidence Registered"
                  description="This investigation currently has no registered evidence."
                  action={
                    <Button variant="secondary" size="sm" onClick={() => setAddEvidenceOpen(true)}>
                      Register Evidence
                    </Button>
                  }
                />
              ) : (
                <EvidenceTable evidence={evidence.slice(0, 5)} showCase={false} />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="evidence" className="pt-5">
          {evidence.length === 0 ? (
            <EmptyState
              icon={FileSearch}
              title="No Evidence Registered"
              description="This investigation currently has no registered evidence."
              action={
                <Button variant="secondary" size="sm" onClick={() => setAddEvidenceOpen(true)}>
                  Register Evidence
                </Button>
              }
            />
          ) : (
            <EvidenceTable evidence={evidence} showCase={false} />
          )}
        </TabsContent>

        <TabsContent value="devices" className="pt-5">
          {devices.length === 0 ? (
            <EmptyState icon={HardDrive} title="No Devices Registered" description="This investigation has no linked devices." />
          ) : (
            <DeviceTable devices={devices} onSelect={setSelectedDevice} />
          )}
        </TabsContent>

        <TabsContent value="timeline" className="pt-5">
          {timeline.length === 0 ? (
            <EmptyState title="No timeline events" description="No forensic events have been recorded for this case yet." />
          ) : (
            <div className="rounded-lg border border-border bg-surface p-5">
              <TimelineView events={timeline} />
            </div>
          )}
        </TabsContent>

        <TabsContent value="analysis" className="pt-5">
          {recordings.length === 0 ? (
            <EmptyState title="No recordings available" description="No CCTV or DVR recordings have been acquired for this case." />
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {recordings.map((r) => (
                <div key={r.id} className="rounded-lg border border-border bg-surface p-4">
                  <p className="font-mono text-xs text-accent">{r.id}</p>
                  <p className="mt-1 text-xs text-fg-subtle">{r.resolution} · {formatRelativeTime(r.recordedAt)}</p>
                  <p className="mt-2 text-sm text-fg">{r.detectionEvents.length} detection events</p>
                  {r.durationSeconds > 0 && (
                    <Link to={`/analysis?recording=${r.id}`}>
                      <Button variant="secondary" size="sm" className="mt-3 w-full">
                        Open in Media Analysis
                      </Button>
                    </Link>
                  )}
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="activity" className="pt-5">
          {activity.length === 0 ? (
            <EmptyState title="No activity recorded" description="No forensic activity has been logged for this case yet." />
          ) : (
            <ActivityTable events={[...activity].sort((a, b) => +new Date(b.timestamp) - +new Date(a.timestamp))} />
          )}
        </TabsContent>
      </Tabs>

      <DeviceDetailsPanel
        device={selectedDevice}
        evidence={selectedDevice ? evidence.filter((e) => e.originalSource === selectedDevice.id) : []}
        recordings={selectedDevice ? recordings.filter((r) => r.deviceId === selectedDevice.id) : []}
        onClose={() => setSelectedDevice(null)}
      />

      <AddEvidenceDialog
        open={addEvidenceOpen}
        onOpenChange={setAddEvidenceOpen}
        caseId={caseData.id}
        onCreated={(newEvidence) => setEvidence((prev) => [newEvidence, ...prev])}
      />

      <CaseSettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        caseData={caseData}
        onUpdated={(updated) => setCaseData(updated)}
      />
    </>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="font-mono text-2xl font-semibold tabular-nums text-fg">{value}</p>
      <p className="mt-0.5 text-xs text-fg-subtle">{label}</p>
    </div>
  )
}

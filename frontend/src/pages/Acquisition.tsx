import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { HardDriveDownload, AlertTriangle } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { StatusBadge } from '@/components/common/StatusBadge'
import { LoadingState } from '@/components/common/LoadingState'
import { EmptyState } from '@/components/common/EmptyState'
import { cn, formatBytes, formatDateTime, truncateHash } from '@/lib/utils'
import { getAcquisitionJobs } from '@/services/mockApi'
import type { AcquisitionJob } from '@/services/types'

export function Acquisition() {
  const [jobs, setJobs] = useState<AcquisitionJob[] | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    getAcquisitionJobs().then((data) => {
      setJobs(data)
      setSelectedId(data[0]?.id ?? null)
    })
  }, [])

  const selected = useMemo(() => jobs?.find((j) => j.id === selectedId) ?? null, [jobs, selectedId])

  if (!jobs) {
    return (
      <>
        <PageHeader title="Acquisition" description="Loading acquisition jobs..." />
        <LoadingState label="Loading acquisition jobs..." />
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="Acquisition"
        description="Source acquisition, hashing, and filesystem/format identification across vendor devices. All progress and status shown here is simulated."
      />

      {jobs.length === 0 ? (
        <EmptyState icon={HardDriveDownload} title="No acquisition jobs" description="No devices have been acquired yet." />
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[360px_1fr]">
          <div className="space-y-2">
            {jobs.map((job) => (
              <button
                key={job.id}
                onClick={() => setSelectedId(job.id)}
                className={cn(
                  'w-full rounded-lg border p-3 text-left transition-colors',
                  job.id === selectedId ? 'border-accent/50 bg-accent/5' : 'border-border bg-surface hover:bg-surface-elevated/60',
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-accent">{job.id}</span>
                  <StatusBadge status={job.status} />
                </div>
                <p className="mt-1.5 text-sm text-fg">
                  {job.vendor} {job.model}
                </p>
                <p className="mt-0.5 font-mono text-[11px] text-fg-subtle">{job.deviceId} · {job.caseId}</p>
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-elevated">
                  <div
                    className={cn(
                      'h-full rounded-full',
                      job.status === 'Failed' ? 'bg-critical' : job.status === 'Warning' ? 'bg-warning' : 'bg-accent',
                    )}
                    style={{ width: `${job.progressPercent}%` }}
                  />
                </div>
              </button>
            ))}
          </div>

          {selected && <AcquisitionDetail job={selected} />}
        </div>
      )}
    </>
  )
}

function AcquisitionDetail({ job }: { job: AcquisitionJob }) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Source</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
          <Field label="Device" value={job.deviceId} mono link={`/devices`} />
          <Field label="Case" value={job.caseId} mono link={`/cases/${job.caseId}`} />
          <Field label="Vendor" value={job.vendor} />
          <Field label="Model" value={job.model} mono />
          <Field label="Firmware" value={job.firmware} mono />
          <Field label="Storage Capacity" value={formatBytes(job.storageCapacity)} />
          <Field label="Channel Count" value={String(job.channelCount)} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Acquisition</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
            <Field label="Method" value={job.acquisitionMethod} />
            <div>
              <p className="text-xs font-medium text-fg-subtle">Status</p>
              <div className="mt-1.5">
                <StatusBadge status={job.status} />
              </div>
            </div>
            <Field label="Started" value={formatDateTime(job.startedAt)} />
            <Field label="Completed" value={job.completedAt ? formatDateTime(job.completedAt) : '—'} />
          </div>
          <div>
            <div className="mb-1.5 flex items-center justify-between text-xs text-fg-subtle">
              <span>Progress</span>
              <span className="font-mono">{job.progressPercent}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-surface-elevated">
              <div
                className={cn(
                  'h-full rounded-full',
                  job.status === 'Failed' ? 'bg-critical' : job.status === 'Warning' ? 'bg-warning' : 'bg-accent',
                )}
                style={{ width: `${job.progressPercent}%` }}
              />
            </div>
          </div>
          {job.warnings.length > 0 && (
            <div className="space-y-2">
              {job.warnings.map((w, i) => (
                <div key={i} className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning/5 p-2.5">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
                  <p className="text-xs text-fg-muted">{w}</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Verification</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Hash Algorithm" value={job.hashAlgorithm} />
          <div>
            <p className="text-xs font-medium text-fg-subtle">Evidence Hash</p>
            <p className="mt-1 truncate font-mono text-sm text-fg">{job.hashResult ? truncateHash(job.hashResult) : 'Not yet computed'}</p>
          </div>
          <Field label="Linked Evidence" value={job.evidenceId} mono link={`/evidence/${job.evidenceId}`} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Filesystem / Format Analysis</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Detected Format" value={job.filesystem.detectedFormat} />
            <Field label="Vendor Structure" value={job.filesystem.vendorStructure} />
            <Field label="Parser Used" value={job.filesystem.parserUsed} mono />
            <div>
              <p className="text-xs font-medium text-fg-subtle">Parsing Status</p>
              <div className="mt-1.5">
                <StatusBadge status={job.filesystem.parsingStatus} />
              </div>
            </div>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium text-fg-subtle">Storage Layout / Partitions</p>
            <div className="overflow-x-auto rounded-md border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-fg-subtle">
                    <th className="px-3 py-2 font-medium">Region</th>
                    <th className="px-3 py-2 font-medium">Type</th>
                    <th className="px-3 py-2 font-medium">Size</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {job.filesystem.partitions.map((p) => (
                    <tr key={p.name} className="border-b border-border/60 last:border-0">
                      <td className="px-3 py-2 text-fg">{p.name}</td>
                      <td className="px-3 py-2 font-mono text-xs text-fg-muted">{p.type}</td>
                      <td className="px-3 py-2 font-mono text-xs text-fg-muted">{formatBytes(p.sizeBytes)}</td>
                      <td className="px-3 py-2">
                        <StatusBadge status={p.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <p className="mb-1.5 text-xs font-medium text-fg-subtle">Recognized Structures</p>
              <div className="flex flex-wrap gap-1.5">
                {job.filesystem.recognizedStructures.map((s) => (
                  <Badge key={s} tone="success">
                    {s}
                  </Badge>
                ))}
              </div>
            </div>
            <div>
              <p className="mb-1.5 text-xs font-medium text-fg-subtle">Unsupported Structures</p>
              {job.filesystem.unsupportedStructures.length === 0 ? (
                <p className="text-xs text-fg-subtle">None — all structures recognized.</p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {job.filesystem.unsupportedStructures.map((s) => (
                    <Badge key={s} tone="critical">
                      {s}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          </div>

          {job.filesystem.warnings.length > 0 && (
            <div className="space-y-2">
              {job.filesystem.warnings.map((w, i) => (
                <div key={i} className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning/5 p-2.5">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
                  <p className="text-xs text-fg-muted">{w}</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function Field({ label, value, mono, link }: { label: string; value: string; mono?: boolean; link?: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-fg-subtle">{label}</p>
      <div className="mt-1">
        {link ? (
          <Link to={link} className="font-mono text-sm text-accent hover:underline">
            {value}
          </Link>
        ) : (
          <p className={mono ? 'font-mono text-sm text-fg' : 'text-sm text-fg'}>{value}</p>
        )}
      </div>
    </div>
  )
}

import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { LifeBuoy, AlertTriangle } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { StatusBadge } from '@/components/common/StatusBadge'
import { LoadingState } from '@/components/common/LoadingState'
import { EmptyState } from '@/components/common/EmptyState'
import { cn, formatDateTime } from '@/lib/utils'
import { getRecoveryReports } from '@/services/mockApi'
import type { RecoveryReport } from '@/services/types'

const BREAKDOWN: { key: keyof RecoveryReport; label: string; color: string }[] = [
  { key: 'recovered', label: 'Recovered', color: 'bg-success' },
  { key: 'fragmented', label: 'Fragmented', color: 'bg-warning' },
  { key: 'deleted', label: 'Deleted', color: 'bg-critical' },
  { key: 'damaged', label: 'Damaged', color: 'bg-critical' },
  { key: 'unrecoverable', label: 'Unrecoverable', color: 'bg-fg-subtle' },
]

export function Recovery() {
  const [reports, setReports] = useState<RecoveryReport[] | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    getRecoveryReports().then((data) => {
      setReports(data)
      setSelectedId(data[0]?.id ?? null)
    })
  }, [])

  const selected = useMemo(() => reports?.find((r) => r.id === selectedId) ?? null, [reports, selectedId])

  if (!reports) {
    return (
      <>
        <PageHeader title="Recovery" description="Loading recovery reports..." />
        <LoadingState label="Loading recovery reports..." />
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="Recovery"
        description="Deleted, fragmented, and damaged recording recovery. Recovery is simulated — incomplete recovery is shown, not hidden."
      />

      {reports.length === 0 ? (
        <EmptyState icon={LifeBuoy} title="No recovery reports" description="No recovery has been run yet." />
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {reports.map((r) => (
              <button
                key={r.id}
                onClick={() => setSelectedId(r.id)}
                className={cn(
                  'rounded-md border px-3 py-1.5 font-mono text-xs transition-colors',
                  r.id === selectedId
                    ? 'border-accent/50 bg-accent/10 text-accent'
                    : 'border-border bg-surface text-fg-muted hover:bg-surface-elevated',
                )}
              >
                {r.caseId} — {r.deviceId}
              </button>
            ))}
          </div>

          {selected && <RecoveryDetail report={selected} />}
        </div>
      )}
    </>
  )
}

function RecoveryDetail({ report }: { report: RecoveryReport }) {
  const overallStatus = report.unrecoverable + report.damaged > 0 ? 'PARTIAL' : report.fragmented + report.deleted > 0 ? 'PARTIAL' : 'COMPLETE'

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Recovery Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs font-medium text-fg-subtle">Recovery Status</p>
              <p className={cn('mt-1 font-mono text-2xl font-bold', overallStatus === 'COMPLETE' ? 'text-success' : 'text-warning')}>
                {overallStatus}
              </p>
            </div>
            <div className="grid grid-cols-3 gap-x-6 gap-y-2 sm:grid-cols-6">
              <Stat label="Total" value={report.totalRecordings} />
              <Stat label="Recovered" value={report.recovered} tone="success" />
              <Stat label="Fragmented" value={report.fragmented} tone="warning" />
              <Stat label="Deleted" value={report.deleted} tone="critical" />
              <Stat label="Damaged" value={report.damaged} tone="critical" />
              <Stat label="Unrecoverable" value={report.unrecoverable} tone="critical" />
            </div>
          </div>

          <div className="mt-4 flex h-2.5 w-full overflow-hidden rounded-full bg-surface-elevated">
            {BREAKDOWN.map(({ key, color }) => {
              const value = report[key] as number
              const pct = (value / report.totalRecordings) * 100
              return pct > 0 ? <div key={key} className={cn('h-full', color)} style={{ width: `${pct}%` }} /> : null
            })}
          </div>

          <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
            <Field label="Confidence" value={`${report.confidencePercent}%`} />
            <Field label="Recovery Method" value={report.method} />
            <Field label="Linked Evidence" value={report.evidenceId} mono link={`/evidence/${report.evidenceId}`} />
          </div>

          {report.limitations.length > 0 && (
            <div className="mt-4 space-y-2">
              <p className="text-xs font-medium text-fg-subtle">Limitations</p>
              {report.limitations.map((l, i) => (
                <div key={i} className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning/5 p-2.5">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
                  <p className="text-xs text-fg-muted">{l}</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recovered Items</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[700px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-fg-subtle">
                  <th className="px-4 py-2.5 font-medium">Item</th>
                  <th className="px-4 py-2.5 font-medium">Camera</th>
                  <th className="px-4 py-2.5 font-medium">Time Range</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Confidence</th>
                  <th className="px-4 py-2.5 font-medium">Source Location</th>
                </tr>
              </thead>
              <tbody>
                {report.items.map((item) => (
                  <tr key={item.id} className="border-b border-border/60 last:border-0">
                    <td className="px-4 py-3 font-mono text-xs text-accent">{item.id}</td>
                    <td className="px-4 py-3 text-fg-muted">{item.cameraChannel}</td>
                    <td className="px-4 py-3 font-mono text-xs text-fg-muted">
                      {formatDateTime(item.timeRangeStart)} → {formatDateTime(item.timeRangeEnd)}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={item.status} />
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-fg-subtle">{Math.round(item.confidence * 100)}%</td>
                    <td className="px-4 py-3 text-xs text-fg-subtle">{item.sourceLocation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: 'success' | 'warning' | 'critical' }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-fg-subtle">{label}</p>
      <p
        className={cn(
          'font-mono text-lg font-semibold tabular-nums',
          tone === 'success' && 'text-success',
          tone === 'warning' && 'text-warning',
          tone === 'critical' && 'text-critical',
          !tone && 'text-fg',
        )}
      >
        {value}
      </p>
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

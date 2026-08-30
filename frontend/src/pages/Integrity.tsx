import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, ShieldAlert } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { IntegritySummary, classifyIntegrity } from '@/components/dashboard/IntegritySummary'
import { LoadingState } from '@/components/common/LoadingState'
import { EmptyState } from '@/components/common/EmptyState'
import { formatDateTime } from '@/lib/utils'
import { cn } from '@/lib/utils'
import { getEvidence, getIntegrityAlerts } from '@/services/mockApi'
import type { Evidence, IntegrityAlert } from '@/services/types'

export function Integrity() {
  const [evidence, setEvidence] = useState<Evidence[] | null>(null)
  const [alerts, setAlerts] = useState<IntegrityAlert[]>([])

  useEffect(() => {
    getEvidence().then(setEvidence)
    getIntegrityAlerts().then(setAlerts)
  }, [])

  const recentVerifications = useMemo(() => {
    if (!evidence) return []
    return evidence
      .flatMap((e) => e.verificationHistory.map((v) => ({ ...v, evidenceId: e.id })))
      .filter((v) => v.algorithm !== null)
      .sort((a, b) => +new Date(b.timestamp) - +new Date(a.timestamp))
      .slice(0, 8)
  }, [evidence])

  if (!evidence) {
    return (
      <>
        <PageHeader title="Integrity" description="Loading verification data..." />
        <LoadingState label="Loading integrity data..." />
      </>
    )
  }

  const verified = evidence.filter((e) => classifyIntegrity(e) === 'Verified').length
  const score = ((verified / evidence.length) * 100).toFixed(1)
  const sha256Verified = evidence.filter((e) => e.sha256Status === 'Verified').length
  const md5Verified = evidence.filter((e) => e.md5Status === 'Verified').length
  const pending = evidence.filter((e) => e.sha256Status === 'Pending' || e.md5Status === 'Pending').length
  const failed = evidence.filter((e) => e.sha256Status === 'Failed' || e.md5Status === 'Failed').length

  return (
    <>
      <PageHeader title="Integrity" description="Forensic trust and evidence integrity across all investigations." />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Overall Integrity Score</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center justify-center py-8">
            <p className="font-mono text-5xl font-bold tabular-nums text-success">{score}%</p>
            <p className="mt-2 text-xs text-fg-subtle">Across {evidence.length} evidence records</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Verification Summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <SummaryRow label="SHA-256 Verified" value={sha256Verified} total={evidence.length} />
            <SummaryRow label="MD5 Verified" value={md5Verified} total={evidence.length} />
            <SummaryRow label="Pending Verification" value={pending} total={evidence.length} />
            <SummaryRow label="Failed Verification" value={failed} total={evidence.length} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Integrity Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <IntegritySummary evidence={evidence} />
          </CardContent>
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Recent Verification Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-0">
              {recentVerifications.map((v, i) => (
                <Link
                  key={i}
                  to={`/evidence/${v.evidenceId}`}
                  className="flex items-center justify-between gap-3 border-b border-border/60 py-2.5 last:border-0 hover:bg-surface-elevated/40"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={cn(
                        'h-2 w-2 shrink-0 rounded-full',
                        v.result === 'Success' ? 'bg-success' : 'bg-critical',
                      )}
                    />
                    <div>
                      <p className="text-sm text-fg">{v.label}</p>
                      <p className="font-mono text-[11px] text-fg-subtle">{v.evidenceId}</p>
                    </div>
                  </div>
                  <span className="shrink-0 text-xs text-fg-subtle">{formatDateTime(v.timestamp)}</span>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Integrity Alerts</CardTitle>
          </CardHeader>
          <CardContent>
            {alerts.length === 0 ? (
              <EmptyState icon={ShieldAlert} title="No active alerts" description="All evidence is currently within integrity thresholds." />
            ) : (
              <div className="space-y-3">
                {alerts.map((alert) => (
                  <Link
                    key={alert.id}
                    to={`/evidence/${alert.evidenceId}`}
                    className={cn(
                      'flex items-start gap-2.5 rounded-md border p-3',
                      alert.severity === 'Critical' ? 'border-critical/30 bg-critical/5' : 'border-warning/30 bg-warning/5',
                    )}
                  >
                    <AlertTriangle
                      className={cn('mt-0.5 h-4 w-4 shrink-0', alert.severity === 'Critical' ? 'text-critical' : 'text-warning')}
                    />
                    <div>
                      <p
                        className={cn(
                          'text-xs font-semibold uppercase tracking-wide',
                          alert.severity === 'Critical' ? 'text-critical' : 'text-warning',
                        )}
                      >
                        {alert.severity}
                      </p>
                      <p className="mt-1 text-sm text-fg">{alert.message}</p>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}

function SummaryRow({ label, value, total }: { label: string; value: number; total: number }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-fg-muted">{label}</span>
      <span className="font-mono font-medium text-fg">
        {value}
        <span className="text-fg-subtle">/{total}</span>
      </span>
    </div>
  )
}

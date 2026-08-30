import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2 } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardContent } from '@/components/ui/Card'
import { StatusBadge } from '@/components/common/StatusBadge'
import { LoadingState } from '@/components/common/LoadingState'
import { EmptyState } from '@/components/common/EmptyState'
import { cn } from '@/lib/utils'
import { getValidationChecks } from '@/services/mockApi'
import type { ValidationCheck } from '@/services/types'

export function Validation() {
  const [checks, setChecks] = useState<ValidationCheck[] | null>(null)

  useEffect(() => {
    getValidationChecks().then(setChecks)
  }, [])

  const summary = useMemo(() => {
    if (!checks) return { pass: 0, warning: 0, fail: 0 }
    return {
      pass: checks.filter((c) => c.status === 'Pass').length,
      warning: checks.filter((c) => c.status === 'Warning').length,
      fail: checks.filter((c) => c.status === 'Fail').length,
    }
  }, [checks])

  if (!checks) {
    return (
      <>
        <PageHeader title="Validation" description="Loading validation checks..." />
        <LoadingState label="Loading validation checks..." />
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="Validation"
        description="Ground-truth comparison for recovery, parsing, timestamp normalization, and AI detection. Demonstrates measurable accuracy rather than unsupported claims."
      />

      <div className="mb-4 grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="py-4 text-center">
            <p className="font-mono text-2xl font-bold text-success">{summary.pass}</p>
            <p className="mt-1 text-xs text-fg-subtle">Pass</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 text-center">
            <p className="font-mono text-2xl font-bold text-warning">{summary.warning}</p>
            <p className="mt-1 text-xs text-fg-subtle">Warning</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 text-center">
            <p className="font-mono text-2xl font-bold text-critical">{summary.fail}</p>
            <p className="mt-1 text-xs text-fg-subtle">Fail</p>
          </CardContent>
        </Card>
      </div>

      {checks.length === 0 ? (
        <EmptyState icon={CheckCircle2} title="No validation checks" description="No ground-truth validation has been run yet." />
      ) : (
        <div className="space-y-3">
          {checks.map((check) => (
            <Card key={check.id}>
              <CardContent className="p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wide text-fg-subtle">{check.category}</p>
                    <p className="mt-0.5 font-mono text-xs text-fg-subtle">{check.caseId}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span
                      className={cn(
                        'font-mono text-lg font-semibold tabular-nums',
                        check.status === 'Pass' && 'text-success',
                        check.status === 'Warning' && 'text-warning',
                        check.status === 'Fail' && 'text-critical',
                      )}
                    >
                      {check.accuracyPercent}%
                    </span>
                    <StatusBadge status={check.status} />
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <p className="text-xs font-medium text-fg-subtle">Expected</p>
                    <p className="mt-0.5 text-sm text-fg-muted">{check.expected}</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-fg-subtle">Actual</p>
                    <p className="mt-0.5 text-sm text-fg-muted">{check.actual}</p>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 font-mono text-xs text-fg-subtle">
                  <span>False Positives: {check.falsePositives}</span>
                  <span>False Negatives: {check.falseNegatives}</span>
                  <span>Ground Truth: {check.groundTruthSource}</span>
                </div>

                <p className="mt-3 border-t border-border pt-3 text-xs text-fg-muted">{check.notes}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </>
  )
}

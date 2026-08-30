import { cn } from '@/lib/utils'
import type { Evidence } from '@/services/types'

export type IntegrityClass = 'Verified' | 'Pending' | 'Warning' | 'Failed'

export function classifyIntegrity(e: Evidence): IntegrityClass {
  if (e.sha256Status === 'Failed' || e.md5Status === 'Failed') return 'Failed'
  if (e.sha256Status === 'Warning' || e.md5Status === 'Warning') return 'Warning'
  if (e.sha256Status === 'Pending' || e.md5Status === 'Pending') return 'Pending'
  return 'Verified'
}

const ORDER: IntegrityClass[] = ['Verified', 'Pending', 'Warning', 'Failed']

const COLOR: Record<IntegrityClass, string> = {
  Verified: 'bg-success',
  Pending: 'bg-fg-subtle',
  Warning: 'bg-warning',
  Failed: 'bg-critical',
}

export function IntegritySummary({ evidence }: { evidence: Evidence[] }) {
  const counts = evidence.reduce<Record<IntegrityClass, number>>(
    (acc, e) => {
      const cls = classifyIntegrity(e)
      acc[cls] += 1
      return acc
    },
    { Verified: 0, Pending: 0, Warning: 0, Failed: 0 },
  )
  const total = evidence.length || 1

  return (
    <div className="space-y-3">
      {ORDER.map((cls) => (
        <div key={cls}>
          <div className="mb-1 flex items-center justify-between text-xs">
            <span className="font-medium uppercase tracking-wide text-fg-muted">{cls}</span>
            <span className="font-mono font-semibold text-fg">{counts[cls]}</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-elevated">
            <div
              className={cn('h-full rounded-full', COLOR[cls])}
              style={{ width: `${(counts[cls] / total) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

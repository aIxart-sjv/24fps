import { CheckCircle2, AlertTriangle, XCircle } from 'lucide-react'
import { cn, formatDateTime } from '@/lib/utils'
import type { CustodyEvent } from '@/services/types'

const RESULT_ICON = {
  Success: CheckCircle2,
  Warning: AlertTriangle,
  Failure: XCircle,
} as const

const RESULT_COLOR = {
  Success: 'text-success border-success/40 bg-success/10',
  Warning: 'text-warning border-warning/40 bg-warning/10',
  Failure: 'text-critical border-critical/40 bg-critical/10',
} as const

export function CustodyTimeline({ log }: { log: CustodyEvent[] }) {
  return (
    <ol className="space-y-0">
      {log.map((event, i) => {
        const Icon = RESULT_ICON[event.result]
        const isLast = i === log.length - 1
        return (
          <li key={event.stage} className="relative flex gap-3 pb-5 last:pb-0">
            {!isLast && <span className="absolute left-[13px] top-6 h-full w-px bg-border" />}
            <span className={cn('flex h-6 w-6 shrink-0 items-center justify-center rounded-full border', RESULT_COLOR[event.result])}>
              <Icon className="h-3.5 w-3.5" />
            </span>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                <p className="text-sm font-semibold uppercase tracking-wide text-fg">{event.stage}</p>
                <span className="font-mono text-[11px] text-fg-subtle">{formatDateTime(event.timestamp)}</span>
              </div>
              <p className="mt-0.5 text-sm text-fg-muted">{event.action}</p>
              <p className="mt-0.5 text-xs text-fg-subtle">Actor: {event.actor}</p>
            </div>
          </li>
        )
      })}
    </ol>
  )
}

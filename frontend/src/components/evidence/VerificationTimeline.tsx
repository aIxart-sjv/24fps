import { formatDateTime } from '@/lib/utils'
import { cn } from '@/lib/utils'
import type { VerificationEvent } from '@/services/types'

export function VerificationTimeline({ events }: { events: VerificationEvent[] }) {
  return (
    <div>
      {events.map((event, i) => (
        <div key={i} className="relative flex gap-3 pb-4 last:pb-0">
          <div className="flex flex-col items-center">
            <span
              className={cn(
                'z-10 mt-1 h-2 w-2 shrink-0 rounded-full',
                event.result === 'Success' ? 'bg-success' : 'bg-critical',
              )}
            />
            {i < events.length - 1 && <span className="mt-1 w-px flex-1 bg-border" />}
          </div>
          <div className="min-w-0">
            <p className="font-mono text-[11px] text-fg-subtle">{formatDateTime(event.timestamp)}</p>
            <p className="mt-0.5 text-sm text-fg">{event.label}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

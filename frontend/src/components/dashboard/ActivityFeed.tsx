import { Link } from 'react-router-dom'
import { formatTime } from '@/lib/utils'
import { cn } from '@/lib/utils'
import type { ActivityEvent } from '@/services/types'

function resourceLink(event: ActivityEvent): string {
  if (event.resource === 'Evidence') return `/evidence/${event.resourceId}`
  if (event.resource === 'Case') return `/cases/${event.resourceId}`
  if (event.resource === 'Device') return `/devices`
  return '/activity'
}

export function ActivityFeed({ events }: { events: ActivityEvent[] }) {
  return (
    <div className="space-y-0">
      {events.map((event, i) => (
        <Link
          key={event.id}
          to={resourceLink(event)}
          className="group relative flex gap-3 py-2.5 first:pt-0 last:pb-0"
        >
          <div className="flex flex-col items-center">
            <span
              className={cn(
                'z-10 mt-1 h-2 w-2 shrink-0 rounded-full',
                event.result === 'Success' && 'bg-success',
                event.result === 'Warning' && 'bg-warning',
                event.result === 'Failure' && 'bg-critical',
              )}
            />
            {i < events.length - 1 && <span className="mt-1 w-px flex-1 bg-border" />}
          </div>
          <div className="min-w-0 pb-1">
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-[11px] text-fg-subtle">{formatTime(event.timestamp)}</span>
            </div>
            <p className="mt-0.5 text-sm text-fg group-hover:text-accent">
              {event.action.charAt(0) + event.action.slice(1).toLowerCase()}
            </p>
            <p className="mt-0.5 font-mono text-xs text-fg-subtle">
              {event.resource}: {event.resourceId}
            </p>
          </div>
        </Link>
      ))}
    </div>
  )
}

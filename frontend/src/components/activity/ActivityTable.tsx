import { useNavigate } from 'react-router-dom'
import { StatusBadge } from '@/components/common/StatusBadge'
import { formatDateTime } from '@/lib/utils'
import type { ActivityEvent } from '@/services/types'

function resourceLink(event: ActivityEvent): string {
  if (event.resource === 'Evidence') return `/evidence/${event.resourceId}`
  if (event.resource === 'Case') return `/cases/${event.resourceId}`
  return '/activity'
}

export function ActivityTable({ events }: { events: ActivityEvent[] }) {
  const navigate = useNavigate()

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full min-w-[720px] text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-fg-subtle">
            <th className="px-4 py-2.5 font-medium">Timestamp</th>
            <th className="px-4 py-2.5 font-medium">User</th>
            <th className="px-4 py-2.5 font-medium">Action</th>
            <th className="px-4 py-2.5 font-medium">Resource</th>
            <th className="px-4 py-2.5 font-medium">Result</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr
              key={event.id}
              onClick={() => navigate(resourceLink(event))}
              className="cursor-pointer border-b border-border/60 font-mono text-xs last:border-0 hover:bg-surface-elevated/60"
            >
              <td className="px-4 py-2.5 text-fg-subtle">{formatDateTime(event.timestamp)}</td>
              <td className="px-4 py-2.5 text-fg-muted">{event.user}</td>
              <td className="px-4 py-2.5 font-sans font-medium text-fg">{event.action}</td>
              <td className="px-4 py-2.5 text-accent">
                {event.resource} · {event.resourceId}
              </td>
              <td className="px-4 py-2.5">
                <StatusBadge status={event.result} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

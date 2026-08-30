import { Link } from 'react-router-dom'
import {
  FileSearch,
  HardDrive,
  Film,
  ShieldCheck,
  Sparkles,
  CheckCircle2,
  FolderKanban,
} from 'lucide-react'
import { cn, formatDateTime } from '@/lib/utils'
import type { TimelineEvent, TimelineEventCategory } from '@/services/types'

const CATEGORY_ICON: Record<TimelineEventCategory, typeof FileSearch> = {
  'Evidence Registered': FileSearch,
  'Device Discovered': HardDrive,
  'Recording Acquired': Film,
  'Hash Verified': ShieldCheck,
  'AI Event Detected': Sparkles,
  'Analysis Completed': CheckCircle2,
  'Case Update': FolderKanban,
}

const CATEGORY_COLOR: Record<TimelineEventCategory, string> = {
  'Evidence Registered': 'border-info/40 bg-info/10 text-info',
  'Device Discovered': 'border-fg-subtle/40 bg-surface-elevated text-fg-muted',
  'Recording Acquired': 'border-accent/40 bg-accent/10 text-accent',
  'Hash Verified': 'border-success/40 bg-success/10 text-success',
  'AI Event Detected': 'border-warning/40 bg-warning/10 text-warning',
  'Analysis Completed': 'border-success/40 bg-success/10 text-success',
  'Case Update': 'border-fg-subtle/40 bg-surface-elevated text-fg-muted',
}

export function TimelineView({
  events,
  density = 'comfortable',
}: {
  events: TimelineEvent[]
  density?: 'compact' | 'comfortable'
}) {
  const sorted = [...events].sort((a, b) => +new Date(b.timestamp) - +new Date(a.timestamp))

  return (
    <div>
      {sorted.map((event, i) => {
        const Icon = CATEGORY_ICON[event.category]
        return (
          <div key={event.id} className={cn('relative flex gap-4', density === 'compact' ? 'pb-3' : 'pb-6')}>
            <div className="flex flex-col items-center">
              <div className={cn('z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border', CATEGORY_COLOR[event.category])}>
                <Icon className="h-3.5 w-3.5" />
              </div>
              {i < sorted.length - 1 && <span className="mt-1 w-px flex-1 bg-border" />}
            </div>
            <div className={cn('min-w-0 flex-1', density === 'compact' ? 'pt-0.5' : 'pt-1')}>
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-medium text-fg">{event.title}</p>
                <span className="rounded border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-fg-subtle">
                  {event.category}
                </span>
              </div>
              {density === 'comfortable' && <p className="mt-1 text-sm text-fg-muted">{event.description}</p>}
              <div className="mt-1 flex items-center gap-2 font-mono text-[11px] text-fg-subtle">
                <span>{formatDateTime(event.timestamp)}</span>
                <span>·</span>
                <Link to={`/cases/${event.caseId}`} className="hover:text-accent">
                  {event.caseId}
                </Link>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

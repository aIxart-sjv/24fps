import { Search, Video } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatRelativeTime } from '@/lib/utils'
import type { Recording } from '@/services/types'

export function RecordingList({
  recordings,
  selectedId,
  onSelect,
  search,
  onSearchChange,
}: {
  recordings: Recording[]
  selectedId: string | undefined
  onSelect: (r: Recording) => void
  search: string
  onSearchChange: (value: string) => void
}) {
  return (
    <div className="flex h-full flex-col rounded-lg border border-border bg-surface">
      <div className="border-b border-border p-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-subtle" />
          <input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Filter recordings..."
            className="h-8 w-full rounded-md border border-border bg-surface-elevated pl-8 pr-3 text-xs text-fg placeholder:text-fg-subtle focus:border-accent/50 focus:outline-none"
          />
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {recordings.map((r) => (
          <button
            key={r.id}
            onClick={() => onSelect(r)}
            className={cn(
              'flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left',
              selectedId === r.id ? 'bg-accent/10' : 'hover:bg-surface-elevated',
            )}
          >
            <div
              className={cn(
                'flex h-8 w-8 shrink-0 items-center justify-center rounded-md',
                selectedId === r.id ? 'bg-accent/20 text-accent' : 'bg-surface-elevated text-fg-subtle',
              )}
            >
              <Video className="h-3.5 w-3.5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className={cn('truncate font-mono text-xs', selectedId === r.id ? 'text-accent' : 'text-fg')}>
                {r.id}
              </p>
              <p className="mt-0.5 text-[11px] text-fg-subtle">
                {r.detectionEvents.length} events · {formatRelativeTime(r.recordedAt)}
              </p>
            </div>
          </button>
        ))}
        {recordings.length === 0 && <p className="px-2.5 py-4 text-center text-xs text-fg-subtle">No recordings match.</p>}
      </div>
    </div>
  )
}

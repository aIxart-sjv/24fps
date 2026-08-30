import { Car, Footprints, AlertTriangle, Box, Waves } from 'lucide-react'
import { StatusBadge } from '@/components/common/StatusBadge'
import { cn } from '@/lib/utils'
import type { DetectionCategory, DetectionEvent, Recording } from '@/services/types'

const CATEGORY_ICON: Record<DetectionCategory, typeof Car> = {
  Person: Footprints,
  Vehicle: Car,
  Object: Box,
  Motion: Waves,
  Anomaly: AlertTriangle,
}

const CATEGORY_COLOR: Record<DetectionCategory, string> = {
  Person: 'text-info',
  Vehicle: 'text-accent',
  Object: 'text-fg-muted',
  Motion: 'text-warning',
  Anomaly: 'text-critical',
}

function formatClock(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function AnalysisTimeline({
  recording,
  activeEvent,
  onJump,
}: {
  recording: Recording
  activeEvent: DetectionEvent | null
  onJump: (seconds: number) => void
}) {
  const events = recording.detectionEvents
  if (events.length === 0) {
    return <p className="py-6 text-center text-xs text-fg-subtle">No detection events for this recording.</p>
  }

  return (
    <div className="space-y-1.5">
      {events.map((event, i) => {
        const Icon = CATEGORY_ICON[event.category]
        const active = activeEvent?.timestampSeconds === event.timestampSeconds
        return (
          <button
            key={i}
            onClick={() => onJump(event.timestampSeconds)}
            className={cn(
              'flex w-full flex-col gap-1.5 rounded-md border px-3 py-2 text-left transition-colors',
              active ? 'border-accent/40 bg-accent/5' : 'border-transparent hover:bg-surface-elevated',
            )}
          >
            <div className="flex w-full items-center gap-3">
              <Icon className={cn('h-4 w-4 shrink-0', CATEGORY_COLOR[event.category])} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium uppercase tracking-wide text-fg">{event.label}</p>
                <p className="font-mono text-[11px] text-fg-subtle">{formatClock(event.timestampSeconds)}</p>
              </div>
              <span className="shrink-0 font-mono text-[11px] text-fg-subtle">{(event.confidence * 100).toFixed(1)}%</span>
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pl-7 font-mono text-[10px] text-fg-subtle">
              <span>Model: {recording.aiModel}</span>
              <span>Version: {recording.aiModelVersion}</span>
              <span>Source: {recording.id}</span>
              <StatusBadge status={event.reviewStatus} />
            </div>
          </button>
        )
      })}
    </div>
  )
}

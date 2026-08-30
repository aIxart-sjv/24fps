import { useRef, useState } from 'react'
import { Play, Pause, Volume2, VolumeX, Maximize, Camera } from 'lucide-react'
import { StatusBadge } from '@/components/common/StatusBadge'
import { cn, formatDateTime } from '@/lib/utils'
import type { DetectionEvent, Recording } from '@/services/types'

const SPEEDS = [0.5, 1, 1.5, 2]

function formatClock(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function VideoWorkspace({
  recording,
  currentTime,
  playing,
  speed,
  onSeek,
  onTogglePlay,
  onSpeedChange,
  activeEvent,
}: {
  recording: Recording
  currentTime: number
  playing: boolean
  speed: number
  onSeek: (seconds: number) => void
  onTogglePlay: () => void
  onSpeedChange: (speed: number) => void
  activeEvent: DetectionEvent | null
}) {
  const [muted, setMuted] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const barRef = useRef<HTMLDivElement>(null)

  function handleSeekClick(e: React.MouseEvent<HTMLDivElement>) {
    if (!barRef.current || recording.durationSeconds === 0) return
    const rect = barRef.current.getBoundingClientRect()
    const pct = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
    onSeek(pct * recording.durationSeconds)
  }

  function handleFullscreen() {
    containerRef.current?.requestFullscreen?.().catch(() => {})
  }

  const progressPct = recording.durationSeconds > 0 ? (currentTime / recording.durationSeconds) * 100 : 0

  return (
    <div className="flex flex-col rounded-lg border border-border bg-surface">
      <div ref={containerRef} className="relative aspect-video w-full overflow-hidden rounded-t-lg bg-[#050506]">
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="flex flex-col items-center gap-2 text-fg-subtle">
            <Camera className="h-9 w-9" />
            <p className="font-mono text-xs">{recording.id}</p>
            <p className="text-[11px]">{recording.resolution} · Simulated playback</p>
          </div>
        </div>

        <div
          className="pointer-events-none absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage: 'repeating-linear-gradient(0deg, #fff 0px, #fff 1px, transparent 1px, transparent 3px)',
          }}
        />

        <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded bg-black/50 px-2 py-1 backdrop-blur-sm">
          <span className="h-1.5 w-1.5 rounded-full bg-critical" />
          <span className="font-mono text-[10px] font-medium text-white">REC</span>
        </div>

        {activeEvent && (
          <div className="absolute bottom-3 left-3 rounded border border-accent/40 bg-black/60 px-2.5 py-1.5 backdrop-blur-sm animate-fade-in">
            <p className="font-mono text-[10px] uppercase tracking-wide text-accent">{activeEvent.category}</p>
            <p className="text-xs text-white">{activeEvent.label}</p>
          </div>
        )}

        <div className="absolute right-3 top-3 rounded bg-black/50 px-2 py-1 font-mono text-[10px] text-white backdrop-blur-sm">
          {formatClock(currentTime)} / {formatClock(recording.durationSeconds)}
        </div>
      </div>

      <div className="border-t border-border p-3">
        <div
          ref={barRef}
          onClick={handleSeekClick}
          className="group relative h-1.5 w-full cursor-pointer rounded-full bg-surface-elevated"
        >
          <div className="absolute inset-y-0 left-0 rounded-full bg-accent" style={{ width: `${progressPct}%` }} />
          {recording.detectionEvents.map((event, i) => (
            <div
              key={i}
              className="absolute top-1/2 h-2.5 w-1 -translate-y-1/2 rounded-full bg-warning/70"
              style={{ left: `${(event.timestampSeconds / Math.max(1, recording.durationSeconds)) * 100}%` }}
              title={event.label}
            />
          ))}
          <div
            className="absolute top-1/2 h-3 w-3 -translate-y-1/2 -translate-x-1/2 rounded-full border-2 border-accent bg-background opacity-0 group-hover:opacity-100"
            style={{ left: `${progressPct}%` }}
          />
        </div>

        <div className="mt-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={onTogglePlay}
              className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-accent-fg hover:bg-accent/90"
            >
              {playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5 translate-x-0.5" />}
            </button>
            <span className="font-mono text-xs tabular-nums text-fg-muted">{formatClock(currentTime)}</span>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1 rounded-md border border-border p-0.5">
              {SPEEDS.map((s) => (
                <button
                  key={s}
                  onClick={() => onSpeedChange(s)}
                  className={cn(
                    'rounded px-1.5 py-0.5 font-mono text-[11px]',
                    speed === s ? 'bg-surface-elevated text-fg' : 'text-fg-subtle hover:text-fg-muted',
                  )}
                >
                  {s}x
                </button>
              ))}
            </div>
            <button onClick={() => setMuted((m) => !m)} className="text-fg-muted hover:text-fg">
              {muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
            </button>
            <button onClick={handleFullscreen} className="text-fg-muted hover:text-fg">
              <Maximize className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-2 border-t border-border p-3 font-mono text-[11px] text-fg-subtle sm:grid-cols-4">
        <MetaField label="Channel" value={recording.cameraChannel} />
        <MetaField label="Codec / Container" value={`${recording.codec} / ${recording.container}`} />
        <MetaField label="FPS" value={String(recording.fps)} />
        <MetaField label="Recording Type" value={recording.recordingType} />
        <div>
          <p className="uppercase tracking-wide text-fg-subtle">Extraction Status</p>
          <div className="mt-1">
            <StatusBadge status={recording.extractionStatus} />
          </div>
        </div>
        <MetaField label="Original Timestamp" value={`${formatDateTime(recording.recordedAt)} (${recording.originalTimezone})`} />
        <MetaField label="Normalized (UTC)" value={formatDateTime(recording.normalizedStartAt)} />
        <MetaField label="Normalization Method" value={recording.normalizationMethod} />
      </div>
    </div>
  )
}

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="uppercase tracking-wide text-fg-subtle">{label}</p>
      <p className="mt-1 text-fg">{value}</p>
    </div>
  )
}

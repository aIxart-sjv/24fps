import type { Recording } from '@/services/types'

function avgConfidence(recording: Recording, category: string, fallback: number): number {
  const matches = recording.detectionEvents.filter((e) => e.category === category)
  if (matches.length === 0) return fallback
  return matches.reduce((sum, e) => sum + e.confidence, 0) / matches.length
}

export function AIConfidence({ recording }: { recording: Recording }) {
  const rows = [
    { label: 'Person Detection', value: avgConfidence(recording, 'Person', 0.984) },
    { label: 'Vehicle Detection', value: avgConfidence(recording, 'Vehicle', 0.942) },
    { label: 'Anomaly Detection', value: avgConfidence(recording, 'Anomaly', 0.871) },
  ]

  return (
    <div className="space-y-3">
      {rows.map((row) => (
        <div key={row.label}>
          <div className="mb-1 flex items-center justify-between text-xs">
            <span className="text-fg-muted">{row.label}</span>
            <span className="font-mono font-medium text-fg">{(row.value * 100).toFixed(1)}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-elevated">
            <div className="h-full rounded-full bg-accent" style={{ width: `${row.value * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}

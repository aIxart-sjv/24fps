import { Footprints, Car, AlertTriangle, Star } from 'lucide-react'
import type { Recording } from '@/services/types'

export function DetectionPanel({ recording }: { recording: Recording }) {
  const persons = recording.detectionEvents.filter((e) => e.category === 'Person').length
  const vehicles = recording.detectionEvents.filter((e) => e.category === 'Vehicle').length
  const anomalies = recording.detectionEvents.filter((e) => e.category === 'Anomaly').length
  const important = recording.detectionEvents.filter((e) => e.confidence >= 0.9).length

  const items = [
    { label: 'Persons Detected', value: persons, icon: Footprints, tone: 'text-info' },
    { label: 'Vehicles Detected', value: vehicles, icon: Car, tone: 'text-accent' },
    { label: 'Anomalies', value: anomalies, icon: AlertTriangle, tone: 'text-critical' },
    { label: 'Important Events', value: important, icon: Star, tone: 'text-warning' },
  ]

  return (
    <div className="grid grid-cols-2 gap-3">
      {items.map((item) => (
        <div key={item.label} className="rounded-md border border-border bg-surface-elevated p-3">
          <item.icon className={`h-4 w-4 ${item.tone}`} />
          <p className="mt-2 font-mono text-lg font-semibold text-fg">{item.value}</p>
          <p className="mt-0.5 text-[11px] text-fg-subtle">{item.label}</p>
        </div>
      ))}
    </div>
  )
}

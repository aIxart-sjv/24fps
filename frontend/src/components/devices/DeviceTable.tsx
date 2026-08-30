import { StatusBadge } from '@/components/common/StatusBadge'
import { formatRelativeTime } from '@/lib/utils'
import { cn } from '@/lib/utils'
import type { Device } from '@/services/types'

export function DeviceTable({ devices, onSelect }: { devices: Device[]; onSelect: (device: Device) => void }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full min-w-[860px] text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-fg-subtle">
            <th className="px-4 py-2.5 font-medium">Device ID</th>
            <th className="px-4 py-2.5 font-medium">Type</th>
            <th className="px-4 py-2.5 font-medium">Manufacturer</th>
            <th className="px-4 py-2.5 font-medium">Model</th>
            <th className="px-4 py-2.5 font-medium">Identification</th>
            <th className="px-4 py-2.5 font-medium">Status</th>
            <th className="px-4 py-2.5 font-medium">Storage</th>
            <th className="px-4 py-2.5 font-medium">Last Activity</th>
          </tr>
        </thead>
        <tbody>
          {devices.map((d) => {
            const pct = Math.round((d.storageUsed / d.storageTotal) * 100)
            return (
              <tr
                key={d.id}
                onClick={() => onSelect(d)}
                className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-surface-elevated/60"
              >
                <td className="px-4 py-3 font-mono text-xs text-accent">{d.id}</td>
                <td className="px-4 py-3 text-fg-muted">{d.type}</td>
                <td className="px-4 py-3 text-fg">{d.manufacturer}</td>
                <td className="px-4 py-3 font-mono text-xs text-fg-muted">{d.model}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    <span
                      className={cn(
                        'h-1.5 w-1.5 shrink-0 rounded-full',
                        d.identificationConfidence >= 0.9 ? 'bg-success' : d.identificationConfidence >= 0.7 ? 'bg-warning' : 'bg-critical',
                      )}
                    />
                    <span className="font-mono text-[11px] text-fg-subtle">{Math.round(d.identificationConfidence * 100)}%</span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={d.status} />
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-elevated">
                      <div
                        className={cn('h-full rounded-full', pct > 90 ? 'bg-warning' : 'bg-accent')}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="font-mono text-[11px] text-fg-subtle">{pct}%</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-fg-subtle">{formatRelativeTime(d.lastActivity)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

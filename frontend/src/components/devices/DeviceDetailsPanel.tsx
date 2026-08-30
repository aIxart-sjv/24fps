import { Link } from 'react-router-dom'
import { Dialog } from '@/components/ui/Dialog'
import { StatusBadge } from '@/components/common/StatusBadge'
import { formatBytes, formatDateTime, formatRelativeTime } from '@/lib/utils'
import type { Device, Evidence, Recording } from '@/services/types'

export function DeviceDetailsPanel({
  device,
  evidence,
  recordings,
  onClose,
}: {
  device: Device | null
  evidence: Evidence[]
  recordings: Recording[]
  onClose: () => void
}) {
  if (!device) return null
  const pct = Math.round((device.storageUsed / device.storageTotal) * 100)

  return (
    <Dialog
      open={!!device}
      onOpenChange={(open) => !open && onClose()}
      variant="panel"
      title={device.id}
      description={`${device.manufacturer} ${device.model}`}
    >
      <div className="space-y-5">
        <div>
          <p className="text-xs font-medium text-fg-subtle">Status</p>
          <div className="mt-1.5">
            <StatusBadge status={device.status} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Type" value={device.type} />
          <Field label="Case" value={device.caseId} mono link={`/cases/${device.caseId}`} />
          <Field label="Manufacturer" value={device.manufacturer} />
          <Field label="Model" value={device.model} mono />
          <Field label="Last Activity" value={formatRelativeTime(device.lastActivity)} />
        </div>

        <div>
          <p className="mb-2 text-xs font-medium text-fg-subtle">Device Identification</p>
          <div className="grid grid-cols-2 gap-4 rounded-md border border-border bg-surface-elevated/40 p-3">
            <Field label="Firmware" value={device.firmware} mono />
            <Field label="Serial Number" value={device.serialNumber} mono />
            <Field label="Channel Count" value={String(device.channelCount)} />
            <Field label="Camera Count" value={String(device.cameraCount)} />
            <Field label="Identification Method" value={device.identificationMethod} />
            <Field label="Identification Confidence" value={`${Math.round(device.identificationConfidence * 100)}%`} mono />
          </div>
        </div>

        <div>
          <p className="mb-1.5 text-xs font-medium text-fg-subtle">Storage</p>
          <div className="h-2 w-full overflow-hidden rounded-full bg-surface-elevated">
            <div
              className={pct > 90 ? 'h-full rounded-full bg-warning' : 'h-full rounded-full bg-accent'}
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="mt-1.5 font-mono text-xs text-fg-subtle">
            {formatBytes(device.storageUsed)} / {formatBytes(device.storageTotal)} ({pct}%)
          </p>
        </div>

        <div>
          <p className="mb-2 text-xs font-medium text-fg-subtle">Associated Evidence ({evidence.length})</p>
          {evidence.length === 0 ? (
            <p className="text-xs text-fg-subtle">No evidence linked to this device.</p>
          ) : (
            <div className="space-y-1.5">
              {evidence.map((e) => (
                <Link
                  key={e.id}
                  to={`/evidence/${e.id}`}
                  className="flex items-center justify-between rounded-md border border-border bg-surface-elevated px-3 py-2 hover:bg-surface-hover"
                >
                  <span className="truncate text-xs text-fg">{e.fileName}</span>
                  <span className="ml-2 shrink-0 font-mono text-[10px] text-accent">{e.id}</span>
                </Link>
              ))}
            </div>
          )}
        </div>

        <div>
          <p className="mb-2 text-xs font-medium text-fg-subtle">Recordings ({recordings.length})</p>
          {recordings.length === 0 ? (
            <p className="text-xs text-fg-subtle">No recordings linked to this device.</p>
          ) : (
            <div className="space-y-1.5">
              {recordings.map((r) => (
                <div
                  key={r.id}
                  className="flex items-center justify-between rounded-md border border-border bg-surface-elevated px-3 py-2"
                >
                  <span className="font-mono text-xs text-fg">{r.id}</span>
                  <span className="text-[11px] text-fg-subtle">{r.detectionEvents.length} detections</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <p className="mb-2 text-xs font-medium text-fg-subtle">Acquisition History</p>
          <div className="space-y-2.5">
            {device.acquisitionHistory.map((h, i) => (
              <div key={i} className="flex gap-2.5">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                <div>
                  <p className="text-xs text-fg">{h.action}</p>
                  <p className="mt-0.5 font-mono text-[10px] text-fg-subtle">{formatDateTime(h.timestamp)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Dialog>
  )
}

function Field({ label, value, mono, link }: { label: string; value: string; mono?: boolean; link?: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-fg-subtle">{label}</p>
      <div className="mt-1">
        {link ? (
          <Link to={link} className="font-mono text-sm text-accent hover:underline">
            {value}
          </Link>
        ) : (
          <p className={mono ? 'font-mono text-sm text-fg' : 'text-sm text-fg'}>{value}</p>
        )}
      </div>
    </div>
  )
}

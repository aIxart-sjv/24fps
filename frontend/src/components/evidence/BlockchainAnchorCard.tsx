import { Link2 } from 'lucide-react'
import { StatusBadge } from '@/components/common/StatusBadge'
import { formatDateTime, truncateHash } from '@/lib/utils'
import type { BlockchainAnchor } from '@/services/types'

export function BlockchainAnchorCard({ anchor }: { anchor: BlockchainAnchor }) {
  return (
    <div className="rounded-lg border border-border bg-surface-elevated p-4">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-fg-muted">
          <Link2 className="h-3.5 w-3.5" />
          Blockchain Anchor
        </span>
        <StatusBadge status={anchor.status} />
      </div>
      <p className="mt-2 text-[10px] uppercase tracking-wide text-fg-subtle">
        Demo / simulated — no real blockchain transaction occurs
      </p>
      <dl className="mt-3 grid grid-cols-1 gap-2 font-mono text-xs">
        <div className="flex items-center justify-between gap-2">
          <dt className="text-fg-subtle">Fingerprint</dt>
          <dd className="truncate text-fg">{truncateHash(anchor.fingerprint)}</dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-fg-subtle">Reference</dt>
          <dd className="truncate text-fg">{anchor.referenceId || '—'}</dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-fg-subtle">Anchored At</dt>
          <dd className="text-fg">{anchor.anchoredAt ? formatDateTime(anchor.anchoredAt) : '—'}</dd>
        </div>
      </dl>
    </div>
  )
}

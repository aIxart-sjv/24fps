import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { StatusBadge } from '@/components/common/StatusBadge'
import type { HashStatus } from '@/services/types'

export function HashCard({ algorithm, value, status }: { algorithm: string; value: string; status: HashStatus }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    await navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="rounded-lg border border-border bg-surface-elevated p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-fg-muted">{algorithm}</span>
        <StatusBadge status={status} />
      </div>
      <div className="mt-3 flex items-center gap-2">
        <p className="min-w-0 flex-1 truncate font-mono text-sm text-fg">{value}</p>
        <button
          onClick={handleCopy}
          className="shrink-0 rounded p-1.5 text-fg-subtle hover:bg-surface-hover hover:text-fg"
          aria-label={`Copy ${algorithm} hash`}
        >
          {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
      </div>
    </div>
  )
}

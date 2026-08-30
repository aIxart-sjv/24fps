import { StatusBadge } from '@/components/common/StatusBadge'
import type { Evidence } from '@/services/types'

export function EvidenceHeader({ evidence }: { evidence: Evidence }) {
  const integrityLabel =
    evidence.sha256Status === 'Verified' && evidence.md5Status === 'Verified'
      ? 'Integrity Verified'
      : evidence.sha256Status === 'Failed' || evidence.md5Status === 'Failed'
        ? 'Integrity Failed'
        : 'Integrity Pending'

  return (
    <div>
      <p className="font-mono text-sm text-fg-subtle">{evidence.id}</p>
      <h1 className="mt-1 text-xl font-semibold tracking-tight text-fg">{evidence.fileName}</h1>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <StatusBadge status={integrityLabel === 'Integrity Verified' ? 'Verified' : integrityLabel === 'Integrity Failed' ? 'Failed' : 'Pending'} />
        <span className="text-xs font-medium uppercase tracking-wide text-fg-subtle">{integrityLabel}</span>
      </div>
    </div>
  )
}

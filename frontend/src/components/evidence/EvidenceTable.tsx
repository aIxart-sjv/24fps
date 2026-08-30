import { useNavigate } from 'react-router-dom'
import { StatusBadge } from '@/components/common/StatusBadge'
import { formatBytes, formatDateTime } from '@/lib/utils'
import type { Evidence } from '@/services/types'

export function EvidenceTable({ evidence, showCase = true }: { evidence: Evidence[]; showCase?: boolean }) {
  const navigate = useNavigate()

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full min-w-[960px] text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-fg-subtle">
            <th className="px-4 py-2.5 font-medium">Evidence ID</th>
            {showCase && <th className="px-4 py-2.5 font-medium">Case</th>}
            <th className="px-4 py-2.5 font-medium">Source Type</th>
            <th className="px-4 py-2.5 font-medium">File</th>
            <th className="px-4 py-2.5 font-medium">Size</th>
            <th className="px-4 py-2.5 font-medium">SHA-256</th>
            <th className="px-4 py-2.5 font-medium">MD5</th>
            <th className="px-4 py-2.5 font-medium">Registered</th>
            <th className="px-4 py-2.5 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {evidence.map((e) => (
            <tr
              key={e.id}
              onClick={() => navigate(`/evidence/${e.id}`)}
              className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-surface-elevated/60"
            >
              <td className="px-4 py-3 font-mono text-xs text-accent">{e.id}</td>
              {showCase && (
                <td className="px-4 py-3 font-mono text-xs text-fg-muted">{e.caseId}</td>
              )}
              <td className="px-4 py-3 text-fg-muted">{e.sourceType}</td>
              <td className="px-4 py-3 text-fg">{e.fileName}</td>
              <td className="px-4 py-3 font-mono text-xs text-fg-muted">{formatBytes(e.fileSize)}</td>
              <td className="px-4 py-3">
                <StatusBadge status={e.sha256Status} />
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={e.md5Status} />
              </td>
              <td className="px-4 py-3 text-xs text-fg-subtle">{formatDateTime(e.registeredAt)}</td>
              <td className="px-4 py-3">
                <StatusBadge status={e.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

import { useNavigate } from 'react-router-dom'
import { StatusBadge } from '@/components/common/StatusBadge'
import { formatRelativeTime } from '@/lib/utils'
import type { Case, Evidence } from '@/services/types'

export function RecentCasesTable({ cases, evidence }: { cases: Case[]; evidence: Evidence[] }) {
  const navigate = useNavigate()
  const sorted = [...cases].sort((a, b) => +new Date(b.updatedAt) - +new Date(a.updatedAt)).slice(0, 6)

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-fg-subtle">
            <th className="py-2 pr-3 font-medium">Case ID</th>
            <th className="py-2 pr-3 font-medium">Case Name</th>
            <th className="py-2 pr-3 font-medium">Priority</th>
            <th className="py-2 pr-3 font-medium">Evidence</th>
            <th className="py-2 pr-3 font-medium">Status</th>
            <th className="py-2 pr-0 text-right font-medium">Last Updated</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((c) => (
            <tr
              key={c.id}
              onClick={() => navigate(`/cases/${c.id}`)}
              className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-surface-elevated/60"
            >
              <td className="py-2.5 pr-3 font-mono text-xs text-accent">{c.id}</td>
              <td className="py-2.5 pr-3 text-fg">{c.name}</td>
              <td className="py-2.5 pr-3">
                <StatusBadge status={c.priority} />
              </td>
              <td className="py-2.5 pr-3 font-mono text-xs text-fg-muted">
                {evidence.filter((e) => e.caseId === c.id).length} Evidence
              </td>
              <td className="py-2.5 pr-3">
                <StatusBadge status={c.status} />
              </td>
              <td className="py-2.5 pr-0 text-right text-xs text-fg-subtle">{formatRelativeTime(c.updatedAt)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

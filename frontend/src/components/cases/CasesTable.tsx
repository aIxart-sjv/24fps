import { useNavigate } from 'react-router-dom'
import { ArrowDown, ArrowUp } from 'lucide-react'
import { StatusBadge } from '@/components/common/StatusBadge'
import { formatDate, formatRelativeTime } from '@/lib/utils'
import type { Case, Evidence } from '@/services/types'

export type SortKey = 'id' | 'name' | 'priority' | 'evidence' | 'status' | 'created' | 'updated'

interface Props {
  cases: Case[]
  evidence: Evidence[]
  sortKey: SortKey
  sortDir: 'asc' | 'desc'
  onSort: (key: SortKey) => void
}

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'id', label: 'Case ID' },
  { key: 'name', label: 'Case Name' },
  { key: 'priority', label: 'Priority' },
  { key: 'evidence', label: 'Evidence' },
  { key: 'status', label: 'Status' },
  { key: 'created', label: 'Created' },
  { key: 'updated', label: 'Updated' },
]

export function CasesTable({ cases, evidence, sortKey, sortDir, onSort }: Props) {
  const navigate = useNavigate()

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full min-w-[900px] text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-fg-subtle">
            {COLUMNS.slice(0, 2).map((col) => (
              <SortableHeader key={col.key} col={col} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
            ))}
            <th className="px-4 py-2.5 font-medium">Lead Investigator</th>
            {COLUMNS.slice(2).map((col) => (
              <SortableHeader key={col.key} col={col} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
            ))}
          </tr>
        </thead>
        <tbody>
          {cases.map((c) => (
            <tr
              key={c.id}
              onClick={() => navigate(`/cases/${c.id}`)}
              className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-surface-elevated/60"
            >
              <td className="px-4 py-3 font-mono text-xs text-accent">{c.id}</td>
              <td className="px-4 py-3 text-fg">{c.name}</td>
              <td className="px-4 py-3 text-fg-muted">{c.leadInvestigator}</td>
              <td className="px-4 py-3">
                <StatusBadge status={c.priority} />
              </td>
              <td className="px-4 py-3 font-mono text-xs text-fg-muted">
                {evidence.filter((e) => e.caseId === c.id).length}
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={c.status} />
              </td>
              <td className="px-4 py-3 text-xs text-fg-subtle">{formatDate(c.createdAt)}</td>
              <td className="px-4 py-3 text-xs text-fg-subtle">{formatRelativeTime(c.updatedAt)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SortableHeader({
  col,
  sortKey,
  sortDir,
  onSort,
}: {
  col: { key: SortKey; label: string }
  sortKey: SortKey
  sortDir: 'asc' | 'desc'
  onSort: (key: SortKey) => void
}) {
  const active = sortKey === col.key
  return (
    <th className="px-4 py-2.5 font-medium">
      <button
        onClick={() => onSort(col.key)}
        className="flex items-center gap-1 hover:text-fg"
      >
        {col.label}
        {active && (sortDir === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />)}
      </button>
    </th>
  )
}

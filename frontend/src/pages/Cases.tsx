import { useEffect, useMemo, useState } from 'react'
import { Plus, Search } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { Button } from '@/components/ui/Button'
import { CasesTable, type SortKey } from '@/components/cases/CasesTable'
import { NewCaseDialog } from '@/components/cases/NewCaseDialog'
import { EmptyState } from '@/components/common/EmptyState'
import { TableSkeleton } from '@/components/common/LoadingState'
import { getCases, getEvidence } from '@/services/mockApi'
import type { Case, CasePriority, CaseStatus, Evidence } from '@/services/types'
import { FolderKanban } from 'lucide-react'

const STATUSES: CaseStatus[] = ['Draft', 'Active', 'Under Review', 'Closed']
const PRIORITIES: CasePriority[] = ['Low', 'Medium', 'High', 'Critical']

export function Cases() {
  const [cases, setCases] = useState<Case[] | null>(null)
  const [evidence, setEvidence] = useState<Evidence[]>([])
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<CaseStatus | 'All'>('All')
  const [priorityFilter, setPriorityFilter] = useState<CasePriority | 'All'>('All')
  const [sortKey, setSortKey] = useState<SortKey>('updated')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [dialogOpen, setDialogOpen] = useState(false)

  useEffect(() => {
    getCases().then(setCases)
    getEvidence().then(setEvidence)
  }, [])

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const filtered = useMemo(() => {
    if (!cases) return []
    let result = cases.filter((c) => {
      const matchesSearch =
        !search.trim() ||
        c.id.toLowerCase().includes(search.toLowerCase()) ||
        c.name.toLowerCase().includes(search.toLowerCase())
      const matchesStatus = statusFilter === 'All' || c.status === statusFilter
      const matchesPriority = priorityFilter === 'All' || c.priority === priorityFilter
      return matchesSearch && matchesStatus && matchesPriority
    })

    const priorityRank: Record<CasePriority, number> = { Low: 0, Medium: 1, High: 2, Critical: 3 }
    result = [...result].sort((a, b) => {
      let cmp = 0
      switch (sortKey) {
        case 'id':
          cmp = a.id.localeCompare(b.id)
          break
        case 'name':
          cmp = a.name.localeCompare(b.name)
          break
        case 'priority':
          cmp = priorityRank[a.priority] - priorityRank[b.priority]
          break
        case 'evidence':
          cmp =
            evidence.filter((e) => e.caseId === a.id).length - evidence.filter((e) => e.caseId === b.id).length
          break
        case 'status':
          cmp = a.status.localeCompare(b.status)
          break
        case 'created':
          cmp = +new Date(a.createdAt) - +new Date(b.createdAt)
          break
        case 'updated':
          cmp = +new Date(a.updatedAt) - +new Date(b.updatedAt)
          break
      }
      return sortDir === 'asc' ? cmp : -cmp
    })

    return result
  }, [cases, search, statusFilter, priorityFilter, sortKey, sortDir, evidence])

  return (
    <>
      <PageHeader
        title="Investigations"
        description="Manage active and historical forensic investigations."
        actions={
          <Button variant="primary" size="sm" onClick={() => setDialogOpen(true)}>
            <Plus className="h-4 w-4" />
            New Investigation
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-subtle" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search cases..."
            className="h-9 w-64 rounded-md border border-border bg-surface pl-8 pr-3 text-sm text-fg placeholder:text-fg-subtle focus:border-accent/50 focus:outline-none"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as CaseStatus | 'All')}
          className="h-9 rounded-md border border-border bg-surface px-3 text-sm text-fg focus:border-accent/50 focus:outline-none"
        >
          <option value="All">All Statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value as CasePriority | 'All')}
          className="h-9 rounded-md border border-border bg-surface px-3 text-sm text-fg focus:border-accent/50 focus:outline-none"
        >
          <option value="All">All Priorities</option>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <span className="ml-auto text-xs text-fg-subtle">{filtered.length} investigations</span>
      </div>

      {!cases ? (
        <TableSkeleton />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={FolderKanban}
          title="No investigations found"
          description="Try adjusting your search or filters, or create a new investigation."
          action={
            <Button variant="secondary" size="sm" onClick={() => setDialogOpen(true)}>
              <Plus className="h-4 w-4" />
              New Investigation
            </Button>
          }
        />
      ) : (
        <CasesTable cases={filtered} evidence={evidence} sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
      )}

      <NewCaseDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onCreated={(newCase) => setCases((prev) => (prev ? [newCase, ...prev] : [newCase]))}
      />
    </>
  )
}

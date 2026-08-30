import { useEffect, useMemo, useState } from 'react'
import { Activity as ActivityIcon, Search } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { ActivityTable } from '@/components/activity/ActivityTable'
import { EmptyState } from '@/components/common/EmptyState'
import { TableSkeleton } from '@/components/common/LoadingState'
import { getActivity } from '@/services/mockApi'
import type { ActivityEvent, ActivityResult } from '@/services/types'

const RESULTS: ActivityResult[] = ['Success', 'Warning', 'Failure']

export function ActivityLog() {
  const [activity, setActivity] = useState<ActivityEvent[] | null>(null)
  const [search, setSearch] = useState('')
  const [resultFilter, setResultFilter] = useState<ActivityResult | 'All'>('All')

  useEffect(() => {
    getActivity().then(setActivity)
  }, [])

  const filtered = useMemo(() => {
    if (!activity) return []
    const sorted = [...activity].sort((a, b) => +new Date(b.timestamp) - +new Date(a.timestamp))
    return sorted.filter((a) => {
      const matchesSearch =
        !search.trim() ||
        a.resourceId.toLowerCase().includes(search.toLowerCase()) ||
        a.action.toLowerCase().includes(search.toLowerCase()) ||
        a.user.toLowerCase().includes(search.toLowerCase())
      const matchesResult = resultFilter === 'All' || a.result === resultFilter
      return matchesSearch && matchesResult
    })
  }, [activity, search, resultFilter])

  return (
    <>
      <PageHeader title="Activity" description="System-wide forensic activity and audit log." />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-subtle" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search activity..."
            className="h-9 w-64 rounded-md border border-border bg-surface pl-8 pr-3 text-sm text-fg placeholder:text-fg-subtle focus:border-accent/50 focus:outline-none"
          />
        </div>
        <select
          value={resultFilter}
          onChange={(e) => setResultFilter(e.target.value as ActivityResult | 'All')}
          className="h-9 rounded-md border border-border bg-surface px-3 text-sm text-fg focus:border-accent/50 focus:outline-none"
        >
          <option value="All">All Results</option>
          {RESULTS.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <span className="ml-auto text-xs text-fg-subtle">{filtered.length} events</span>
      </div>

      {!activity ? (
        <TableSkeleton />
      ) : filtered.length === 0 ? (
        <EmptyState icon={ActivityIcon} title="No activity found" description="Try adjusting your search or filters." />
      ) : (
        <ActivityTable events={filtered} />
      )}
    </>
  )
}

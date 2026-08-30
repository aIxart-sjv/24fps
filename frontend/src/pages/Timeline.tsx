import { useEffect, useMemo, useState } from 'react'
import { GitCommitHorizontal, ZoomIn, ZoomOut } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { TimelineView } from '@/components/timeline/TimelineView'
import { EmptyState } from '@/components/common/EmptyState'
import { LoadingState } from '@/components/common/LoadingState'
import { Button } from '@/components/ui/Button'
import { getCases, getTimelineEvents } from '@/services/mockApi'
import type { Case, TimelineEvent, TimelineEventCategory } from '@/services/types'

const CATEGORIES: TimelineEventCategory[] = [
  'Evidence Registered',
  'Device Discovered',
  'Recording Acquired',
  'Hash Verified',
  'AI Event Detected',
  'Analysis Completed',
  'Case Update',
]

export function Timeline() {
  const [events, setEvents] = useState<TimelineEvent[] | null>(null)
  const [cases, setCases] = useState<Case[]>([])
  const [caseFilter, setCaseFilter] = useState('All')
  const [categoryFilter, setCategoryFilter] = useState<TimelineEventCategory | 'All'>('All')
  const [density, setDensity] = useState<'compact' | 'comfortable'>('comfortable')

  useEffect(() => {
    getTimelineEvents().then(setEvents)
    getCases().then(setCases)
  }, [])

  const filtered = useMemo(() => {
    if (!events) return []
    return events.filter((e) => {
      const matchesCase = caseFilter === 'All' || e.caseId === caseFilter
      const matchesCategory = categoryFilter === 'All' || e.category === categoryFilter
      return matchesCase && matchesCategory
    })
  }, [events, caseFilter, categoryFilter])

  return (
    <>
      <PageHeader title="Timeline" description="Chronological forensic event history across investigations." />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select
          value={caseFilter}
          onChange={(e) => setCaseFilter(e.target.value)}
          className="h-9 rounded-md border border-border bg-surface px-3 text-sm text-fg focus:border-accent/50 focus:outline-none"
        >
          <option value="All">All Cases</option>
          {cases.map((c) => (
            <option key={c.id} value={c.id}>
              {c.id}
            </option>
          ))}
        </select>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value as TimelineEventCategory | 'All')}
          className="h-9 rounded-md border border-border bg-surface px-3 text-sm text-fg focus:border-accent/50 focus:outline-none"
        >
          <option value="All">All Categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <div className="ml-auto flex items-center gap-1 rounded-md border border-border p-0.5">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setDensity('compact')}
            aria-label="Compact zoom"
          >
            <ZoomOut className={density === 'compact' ? 'h-3.5 w-3.5 text-accent' : 'h-3.5 w-3.5'} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setDensity('comfortable')}
            aria-label="Expanded zoom"
          >
            <ZoomIn className={density === 'comfortable' ? 'h-3.5 w-3.5 text-accent' : 'h-3.5 w-3.5'} />
          </Button>
        </div>
      </div>

      {!events ? (
        <LoadingState label="Loading forensic timeline..." />
      ) : filtered.length === 0 ? (
        <EmptyState icon={GitCommitHorizontal} title="No events found" description="Try adjusting your filters." />
      ) : (
        <div className="rounded-lg border border-border bg-surface p-5">
          <TimelineView events={filtered} density={density} />
        </div>
      )}
    </>
  )
}

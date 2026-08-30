import { useEffect, useMemo, useState } from 'react'
import { Search, FileSearch } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { EvidenceTable } from '@/components/evidence/EvidenceTable'
import { EmptyState } from '@/components/common/EmptyState'
import { TableSkeleton } from '@/components/common/LoadingState'
import { getCases, getEvidence } from '@/services/mockApi'
import type { Case, Evidence, HashStatus, SourceType } from '@/services/types'

const SOURCE_TYPES: SourceType[] = ['Forensic Image', 'CCTV Recording', 'Mobile Extraction', 'Document', 'Photograph', 'Audio Recording']
const INTEGRITY_STATUSES: HashStatus[] = ['Verified', 'Pending', 'Warning', 'Failed']

export function EvidenceList() {
  const [evidence, setEvidence] = useState<Evidence[] | null>(null)
  const [cases, setCases] = useState<Case[]>([])
  const [search, setSearch] = useState('')
  const [caseFilter, setCaseFilter] = useState<string>('All')
  const [sourceFilter, setSourceFilter] = useState<SourceType | 'All'>('All')
  const [integrityFilter, setIntegrityFilter] = useState<HashStatus | 'All'>('All')

  useEffect(() => {
    getEvidence().then(setEvidence)
    getCases().then(setCases)
  }, [])

  const filtered = useMemo(() => {
    if (!evidence) return []
    return evidence.filter((e) => {
      const matchesSearch =
        !search.trim() ||
        e.id.toLowerCase().includes(search.toLowerCase()) ||
        e.fileName.toLowerCase().includes(search.toLowerCase())
      const matchesCase = caseFilter === 'All' || e.caseId === caseFilter
      const matchesSource = sourceFilter === 'All' || e.sourceType === sourceFilter
      const matchesIntegrity =
        integrityFilter === 'All' || e.sha256Status === integrityFilter || e.md5Status === integrityFilter
      return matchesSearch && matchesCase && matchesSource && matchesIntegrity
    })
  }, [evidence, search, caseFilter, sourceFilter, integrityFilter])

  return (
    <>
      <PageHeader title="Evidence" description="All forensic evidence registered across investigations." />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-subtle" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search evidence..."
            className="h-9 w-64 rounded-md border border-border bg-surface pl-8 pr-3 text-sm text-fg placeholder:text-fg-subtle focus:border-accent/50 focus:outline-none"
          />
        </div>
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
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value as SourceType | 'All')}
          className="h-9 rounded-md border border-border bg-surface px-3 text-sm text-fg focus:border-accent/50 focus:outline-none"
        >
          <option value="All">All Source Types</option>
          {SOURCE_TYPES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={integrityFilter}
          onChange={(e) => setIntegrityFilter(e.target.value as HashStatus | 'All')}
          className="h-9 rounded-md border border-border bg-surface px-3 text-sm text-fg focus:border-accent/50 focus:outline-none"
        >
          <option value="All">All Integrity Status</option>
          {INTEGRITY_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <span className="ml-auto text-xs text-fg-subtle">{filtered.length} records</span>
      </div>

      {!evidence ? (
        <TableSkeleton />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={FileSearch}
          title="No evidence found"
          description="Try adjusting your search or filters."
        />
      ) : (
        <EvidenceTable evidence={filtered} />
      )}
    </>
  )
}

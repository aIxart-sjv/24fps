import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Bell, Search, ShieldCheck, FileSearch, FolderKanban } from 'lucide-react'
import { getActivity, getCases, getEvidence } from '@/services/mockApi'
import type { ActivityEvent, Case, Evidence } from '@/services/types'
import { formatRelativeTime } from '@/lib/utils'
import { cn } from '@/lib/utils'

const ROUTE_TITLES: Record<string, string> = {
  '/dashboard': 'Investigation Overview',
  '/cases': 'Investigations',
  '/evidence': 'Evidence',
  '/devices': 'Devices',
  '/analysis': 'Media Analysis',
  '/insights': 'AI Insights',
  '/timeline': 'Timeline',
  '/integrity': 'Integrity',
  '/activity': 'Activity',
  '/reports': 'Reports',
  '/settings': 'Settings',
}

function useBreadcrumb() {
  const location = useLocation()
  const params = useParams()

  return useMemo(() => {
    if (params.caseId) return { section: 'Investigations', current: params.caseId }
    if (params.evidenceId) return { section: 'Evidence', current: params.evidenceId }
    return { section: ROUTE_TITLES[location.pathname] ?? 'Overview', current: null }
  }, [location.pathname, params])
}

export function Header() {
  const breadcrumb = useBreadcrumb()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [cases, setCases] = useState<Case[]>([])
  const [evidence, setEvidence] = useState<Evidence[]>([])
  const [activity, setActivity] = useState<ActivityEvent[]>([])
  const [searchOpen, setSearchOpen] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getCases().then(setCases)
    getEvidence().then(setEvidence)
    getActivity().then((events) => setActivity(events.slice(0, 5)))
  }, [])

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) setSearchOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  const results = useMemo(() => {
    if (!query.trim()) return { cases: [], evidence: [] }
    const q = query.toLowerCase()
    return {
      cases: cases.filter((c) => c.id.toLowerCase().includes(q) || c.name.toLowerCase().includes(q)).slice(0, 4),
      evidence: evidence.filter((e) => e.id.toLowerCase().includes(q) || e.fileName.toLowerCase().includes(q)).slice(0, 4),
    }
  }, [query, cases, evidence])

  const hasResults = results.cases.length > 0 || results.evidence.length > 0

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border bg-background px-5">
      <div className="min-w-0 text-sm">
        <span className="text-fg-muted">{breadcrumb.section}</span>
        {breadcrumb.current && (
          <>
            <span className="mx-1.5 text-fg-subtle">/</span>
            <span className="font-mono text-fg">{breadcrumb.current}</span>
          </>
        )}
      </div>

      <div className="flex flex-1 items-center justify-end gap-3">
        <div ref={searchRef} className="relative w-full max-w-72">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-subtle" />
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setSearchOpen(true)
            }}
            onFocus={() => setSearchOpen(true)}
            placeholder="Search evidence, cases..."
            className="h-8 w-full rounded-md border border-border bg-surface pl-8 pr-3 text-xs text-fg placeholder:text-fg-subtle focus:border-accent/50 focus:outline-none"
          />
          {searchOpen && query.trim() && (
            <div className="absolute right-0 top-9 z-40 w-80 rounded-md border border-border bg-surface-elevated py-1.5 shadow-2xl animate-fade-in">
              {!hasResults && <p className="px-3 py-2 text-xs text-fg-subtle">No matches for "{query}"</p>}
              {results.cases.length > 0 && (
                <div className="px-1.5">
                  <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">Cases</p>
                  {results.cases.map((c) => (
                    <button
                      key={c.id}
                      onClick={() => {
                        navigate(`/cases/${c.id}`)
                        setSearchOpen(false)
                        setQuery('')
                      }}
                      className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-surface-hover"
                    >
                      <FolderKanban className="h-3.5 w-3.5 shrink-0 text-fg-subtle" />
                      <span className="truncate text-xs text-fg">{c.name}</span>
                      <span className="ml-auto shrink-0 font-mono text-[10px] text-fg-subtle">{c.id}</span>
                    </button>
                  ))}
                </div>
              )}
              {results.evidence.length > 0 && (
                <div className="px-1.5 pt-1">
                  <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">Evidence</p>
                  {results.evidence.map((e) => (
                    <button
                      key={e.id}
                      onClick={() => {
                        navigate(`/evidence/${e.id}`)
                        setSearchOpen(false)
                        setQuery('')
                      }}
                      className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-surface-hover"
                    >
                      <FileSearch className="h-3.5 w-3.5 shrink-0 text-fg-subtle" />
                      <span className="truncate text-xs text-fg">{e.fileName}</span>
                      <span className="ml-auto shrink-0 font-mono text-[10px] text-fg-subtle">{e.id}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="hidden items-center gap-1.5 rounded-md border border-success/25 bg-success/5 px-2.5 py-1.5 text-[11px] font-medium text-success md:flex">
          <span className="h-1.5 w-1.5 rounded-full bg-success" />
          System Operational
        </div>

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button className="relative flex h-8 w-8 items-center justify-center rounded-md text-fg-muted hover:bg-surface-elevated hover:text-fg">
              <Bell className="h-4 w-4" />
              <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-accent" />
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              sideOffset={8}
              className="z-50 w-80 rounded-md border border-border bg-surface-elevated py-1.5 shadow-2xl animate-fade-in"
            >
              <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                Recent Activity
              </p>
              {activity.map((event) => (
                <div key={event.id} className="flex items-start gap-2.5 px-3 py-2 hover:bg-surface-hover">
                  <span
                    className={cn(
                      'mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full',
                      event.result === 'Success' && 'bg-success',
                      event.result === 'Warning' && 'bg-warning',
                      event.result === 'Failure' && 'bg-critical',
                    )}
                  />
                  <div className="min-w-0">
                    <p className="text-xs text-fg">{event.action.charAt(0) + event.action.slice(1).toLowerCase()}</p>
                    <p className="mt-0.5 font-mono text-[10px] text-fg-subtle">
                      {event.resourceId} · {formatRelativeTime(event.timestamp)}
                    </p>
                  </div>
                </div>
              ))}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-elevated text-xs font-semibold text-fg">
          <ShieldCheck className="h-4 w-4 text-accent" />
        </div>
      </div>
    </header>
  )
}

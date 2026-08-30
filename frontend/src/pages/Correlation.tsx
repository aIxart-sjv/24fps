import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Radar, Camera } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { LoadingState } from '@/components/common/LoadingState'
import { EmptyState } from '@/components/common/EmptyState'
import { cn, formatDateTime } from '@/lib/utils'
import { getCases, getCorrelationEvents } from '@/services/mockApi'
import type { Case, CorrelationEvent } from '@/services/types'

export function Correlation() {
  const [events, setEvents] = useState<CorrelationEvent[] | null>(null)
  const [cases, setCases] = useState<Case[]>([])
  const [caseFilter, setCaseFilter] = useState<string>('All')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    getCorrelationEvents().then((data) => {
      setEvents(data)
      setSelectedId(data[0]?.id ?? null)
      if (data[0]) setCaseFilter(data[0].caseId)
    })
    getCases().then(setCases)
  }, [])

  const filtered = useMemo(() => {
    if (!events) return []
    const list = caseFilter === 'All' ? events : events.filter((e) => e.caseId === caseFilter)
    return [...list].sort((a, b) => +new Date(a.normalizedTimestamp) - +new Date(b.normalizedTimestamp))
  }, [events, caseFilter])

  const cameraChannels = useMemo(() => {
    const set = new Set<string>()
    filtered.forEach((e) => e.cameraChannels.forEach((c) => set.add(c)))
    return Array.from(set)
  }, [filtered])

  const selected = useMemo(() => events?.find((e) => e.id === selectedId) ?? null, [events, selectedId])

  if (!events) {
    return (
      <>
        <PageHeader title="Cross-Camera Correlation" description="Loading correlation data..." />
        <LoadingState label="Loading correlation events..." />
      </>
    )
  }

  const casesWithEvents = cases.filter((c) => events.some((e) => e.caseId === c.id))

  return (
    <>
      <PageHeader
        title="Cross-Camera Correlation"
        description="Investigation events aligned by normalized time across multiple camera sources. All correlations shown are simulated demo analysis."
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select
          value={caseFilter}
          onChange={(e) => setCaseFilter(e.target.value)}
          className="h-9 rounded-md border border-border bg-surface px-3 text-sm text-fg focus:border-accent/50 focus:outline-none"
        >
          {casesWithEvents.map((c) => (
            <option key={c.id} value={c.id}>
              {c.id} — {c.name}
            </option>
          ))}
          <option value="All">All Cases</option>
        </select>
        <span className="ml-auto text-xs text-fg-subtle">{filtered.length} correlated events</span>
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon={Radar} title="No correlation events" description="No cross-camera correlations found for this case." />
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_400px]">
          <Card>
            <CardHeader>
              <CardTitle>Synchronized Timeline</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="mb-3 flex flex-wrap gap-1.5">
                {cameraChannels.map((c) => (
                  <Badge key={c} tone="neutral">
                    <Camera className="h-3 w-3" />
                    {c}
                  </Badge>
                ))}
              </div>
              <ol className="space-y-0">
                {filtered.map((event, i) => (
                  <li key={event.id} className="relative flex gap-3 pb-5 last:pb-0">
                    {i !== filtered.length - 1 && <span className="absolute left-[13px] top-6 h-full w-px bg-border" />}
                    <button
                      onClick={() => setSelectedId(event.id)}
                      className={cn(
                        'flex h-6 w-6 shrink-0 items-center justify-center rounded-full border',
                        event.id === selectedId ? 'border-accent bg-accent/20 text-accent' : 'border-border bg-surface-elevated text-fg-subtle',
                      )}
                    >
                      <Radar className="h-3.5 w-3.5" />
                    </button>
                    <button onClick={() => setSelectedId(event.id)} className="min-w-0 flex-1 pt-0.5 text-left">
                      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                        <p className={cn('text-sm font-medium', event.id === selectedId ? 'text-fg' : 'text-fg-muted')}>{event.title}</p>
                        <span className="font-mono text-[11px] text-fg-subtle">{formatDateTime(event.normalizedTimestamp)} UTC</span>
                      </div>
                      <p className="mt-1 flex flex-wrap gap-1.5">
                        {event.cameraChannels.map((c) => (
                          <span key={c} className="font-mono text-[10px] text-accent">
                            {c}
                          </span>
                        ))}
                      </p>
                    </button>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>

          {selected && (
            <Card className="h-fit">
              <CardHeader>
                <CardTitle>Event Detail</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="text-xs font-medium text-fg-subtle">Title</p>
                  <p className="mt-1 text-sm text-fg">{selected.title}</p>
                </div>
                <div>
                  <p className="text-xs font-medium text-fg-subtle">Description</p>
                  <p className="mt-1 text-sm text-fg-muted">{selected.description}</p>
                </div>
                <div>
                  <p className="text-xs font-medium text-fg-subtle">Normalized Timestamp</p>
                  <p className="mt-1 font-mono text-sm text-fg">{formatDateTime(selected.normalizedTimestamp)} UTC</p>
                </div>
                <div>
                  <p className="mb-1.5 text-xs font-medium text-fg-subtle">Camera Channels</p>
                  <div className="flex flex-wrap gap-1.5">
                    {selected.cameraChannels.map((c) => (
                      <Badge key={c} tone="accent">
                        {c}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="mb-1.5 text-xs font-medium text-fg-subtle">Linked Recordings</p>
                  <div className="space-y-1.5">
                    {selected.recordings.map((r) => (
                      <p key={r} className="font-mono text-xs text-fg-muted">
                        {r}
                      </p>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="mb-1.5 text-xs font-medium text-fg-subtle">Related Evidence</p>
                  <div className="space-y-1.5">
                    {selected.relatedEvidence.map((e) => (
                      <Link key={e} to={`/evidence/${e}`} className="block font-mono text-xs text-accent hover:underline">
                        {e}
                      </Link>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-medium text-fg-subtle">Confidence</p>
                  <p className="mt-1 font-mono text-sm text-fg">{Math.round(selected.confidence * 100)}%</p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </>
  )
}

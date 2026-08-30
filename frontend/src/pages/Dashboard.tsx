import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, FolderKanban, FileSearch, Film, ShieldCheck } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { MetricCard } from '@/components/dashboard/MetricCard'
import { ActivityFeed } from '@/components/dashboard/ActivityFeed'
import { CaseChart } from '@/components/dashboard/CaseChart'
import { IntegritySummary, classifyIntegrity } from '@/components/dashboard/IntegritySummary'
import { RecentCasesTable } from '@/components/dashboard/RecentCasesTable'
import { LoadingState } from '@/components/common/LoadingState'
import { getActivity, getCases, getEvidence, getRecordings } from '@/services/mockApi'
import type { ActivityEvent, Case, Evidence, Recording } from '@/services/types'

export function Dashboard() {
  const [cases, setCases] = useState<Case[] | null>(null)
  const [evidence, setEvidence] = useState<Evidence[] | null>(null)
  const [recordings, setRecordings] = useState<Recording[] | null>(null)
  const [activity, setActivity] = useState<ActivityEvent[] | null>(null)

  useEffect(() => {
    getCases().then(setCases)
    getEvidence().then(setEvidence)
    getRecordings().then(setRecordings)
    getActivity().then(setActivity)
  }, [])

  if (!cases || !evidence || !recordings || !activity) {
    return (
      <>
        <PageHeader title="Investigation Overview" description="Loading investigation environment..." />
        <LoadingState label="Loading dashboard metrics..." />
      </>
    )
  }

  const activeCases = cases.filter((c) => c.status === 'Active')
  const attentionCases = activeCases.filter((c) => c.priority === 'High' || c.priority === 'Critical')
  const weekAgo = new Date('2026-08-20T00:00:00')
  const recentEvidence = evidence.filter((e) => new Date(e.registeredAt) >= weekAgo)
  const processedRecordings = recordings.filter((r) => r.detectionEvents.length > 0)
  const processedPct = Math.round((processedRecordings.length / recordings.length) * 100)
  const verifiedEvidence = evidence.filter((e) => classifyIntegrity(e) === 'Verified')
  const integrityPct = ((verifiedEvidence.length / evidence.length) * 100).toFixed(1)

  return (
    <>
      <PageHeader
        title="Investigation Overview"
        description="High-level status across all active investigations and forensic evidence."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          icon={FolderKanban}
          label="Active Cases"
          value={String(activeCases.length)}
          subtitle={`${attentionCases.length} requiring attention`}
          tone="accent"
        />
        <MetricCard
          icon={FileSearch}
          label="Registered Evidence"
          value={String(evidence.length)}
          subtitle={`+${recentEvidence.length} this week`}
        />
        <MetricCard
          icon={Film}
          label="Analyzed Recordings"
          value={String(recordings.length)}
          subtitle={`${processedPct}% successfully processed`}
        />
        <MetricCard
          icon={ShieldCheck}
          label="Integrity Status"
          value={`${integrityPct}%`}
          subtitle="All critical evidence verified"
          tone="success"
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="flex flex-col xl:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Investigation Activity
              <span className="flex items-center gap-1 rounded-full border border-success/25 bg-success/5 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-success">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-success" />
                Live
              </span>
            </CardTitle>
            <Link to="/activity" className="flex items-center gap-1 text-xs text-fg-subtle hover:text-accent">
              View all
              <ArrowRight className="h-3 w-3" />
            </Link>
          </CardHeader>
          <CardContent className="flex-1">
            <ActivityFeed events={activity.slice(0, 8)} />
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Case Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <CaseChart cases={cases} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Evidence Integrity Overview</CardTitle>
            </CardHeader>
            <CardContent>
              <IntegritySummary evidence={evidence} />
            </CardContent>
          </Card>
        </div>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Recent Investigations</CardTitle>
          <Link to="/cases" className="flex items-center gap-1 text-xs text-fg-subtle hover:text-accent">
            View all
            <ArrowRight className="h-3 w-3" />
          </Link>
        </CardHeader>
        <CardContent>
          <RecentCasesTable cases={cases} evidence={evidence} />
        </CardContent>
      </Card>
    </>
  )
}

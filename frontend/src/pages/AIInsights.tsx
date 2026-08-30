import { useEffect, useMemo, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { Badge } from '@/components/ui/Badge'
import { InsightCard } from '@/components/insights/InsightCard'
import { EmptyState } from '@/components/common/EmptyState'
import { LoadingState } from '@/components/common/LoadingState'
import { getAIInsights } from '@/services/mockApi'
import type { AIInsight, InsightType } from '@/services/types'

const TYPES: InsightType[] = ['Suspicious Activity', 'Evidence Correlation', 'Investigation Recommendation']

export function AIInsights() {
  const [insights, setInsights] = useState<AIInsight[] | null>(null)
  const [typeFilter, setTypeFilter] = useState<InsightType | 'All'>('All')

  useEffect(() => {
    getAIInsights().then(setInsights)
  }, [])

  const filtered = useMemo(() => {
    if (!insights) return []
    return typeFilter === 'All' ? insights : insights.filter((i) => i.type === typeFilter)
  }, [insights, typeFilter])

  return (
    <>
      <PageHeader
        title="AI Insights"
        description="Automated correlations and recommendations surfaced from case evidence."
        actions={<Badge tone="accent">Demo Analysis</Badge>}
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <button
          onClick={() => setTypeFilter('All')}
          className={`rounded-md border px-3 py-1.5 text-xs font-medium ${
            typeFilter === 'All' ? 'border-accent/40 bg-accent/10 text-accent' : 'border-border text-fg-muted hover:bg-surface-elevated'
          }`}
        >
          All
        </button>
        {TYPES.map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(t)}
            className={`rounded-md border px-3 py-1.5 text-xs font-medium ${
              typeFilter === t ? 'border-accent/40 bg-accent/10 text-accent' : 'border-border text-fg-muted hover:bg-surface-elevated'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {!insights ? (
        <LoadingState label="Loading AI insights..." />
      ) : filtered.length === 0 ? (
        <EmptyState icon={Sparkles} title="No insights available" description="No AI insights match the selected filter." />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {filtered.map((insight) => (
            <InsightCard key={insight.id} insight={insight} />
          ))}
        </div>
      )}
    </>
  )
}

import { Link } from 'react-router-dom'
import { AlertTriangle, Link2, Lightbulb } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { formatDateTime } from '@/lib/utils'
import type { AIInsight, InsightType } from '@/services/types'

const TYPE_ICON: Record<InsightType, typeof AlertTriangle> = {
  'Suspicious Activity': AlertTriangle,
  'Evidence Correlation': Link2,
  'Investigation Recommendation': Lightbulb,
}

const TYPE_TONE: Record<InsightType, 'warning' | 'info' | 'accent'> = {
  'Suspicious Activity': 'warning',
  'Evidence Correlation': 'info',
  'Investigation Recommendation': 'accent',
}

const TONE_ICON_WRAP: Record<'warning' | 'info' | 'accent', string> = {
  warning: 'bg-warning/10',
  info: 'bg-info/10',
  accent: 'bg-accent/10',
}

const TONE_ICON_COLOR: Record<'warning' | 'info' | 'accent', string> = {
  warning: 'text-warning',
  info: 'text-info',
  accent: 'text-accent',
}

export function InsightCard({ insight }: { insight: AIInsight }) {
  const Icon = TYPE_ICON[insight.type]
  const tone = TYPE_TONE[insight.type]

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${TONE_ICON_WRAP[tone]}`}>
            <Icon className={`h-4 w-4 ${TONE_ICON_COLOR[tone]}`} />
          </div>
          <div>
            <Badge tone={tone}>{insight.type}</Badge>
            <h3 className="mt-1.5 text-sm font-semibold text-fg">{insight.title}</h3>
          </div>
        </div>
        <div className="shrink-0 text-right">
          <p className="font-mono text-sm font-semibold text-fg">{Math.round(insight.confidence * 100)}%</p>
          <p className="text-[10px] uppercase tracking-wide text-fg-subtle">Confidence</p>
        </div>
      </div>

      <p className="mt-3 text-sm leading-relaxed text-fg-muted">{insight.description}</p>

      <div className="mt-3.5 flex flex-wrap items-center gap-1.5">
        {insight.relatedEvidence.map((id) => (
          <Link
            key={id}
            to={`/evidence/${id}`}
            className="rounded border border-border bg-surface-elevated px-2 py-0.5 font-mono text-[11px] text-accent hover:bg-surface-hover"
          >
            {id}
          </Link>
        ))}
        {insight.relatedRecordings.map((id) => (
          <span
            key={id}
            className="rounded border border-border bg-surface-elevated px-2 py-0.5 font-mono text-[11px] text-fg-muted"
          >
            {id}
          </span>
        ))}
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-border pt-2.5">
        <Link to={`/cases/${insight.caseId}`} className="font-mono text-[11px] text-fg-subtle hover:text-accent">
          {insight.caseId}
        </Link>
        <span className="text-[11px] text-fg-subtle">{formatDateTime(insight.timestamp)}</span>
      </div>
    </div>
  )
}

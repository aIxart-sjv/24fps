import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

export function MetricCard({
  icon: Icon,
  label,
  value,
  subtitle,
  tone = 'neutral',
}: {
  icon: LucideIcon
  label: string
  value: string
  subtitle: string
  tone?: 'neutral' | 'accent' | 'success' | 'warning'
}) {
  const toneColor = {
    neutral: 'text-fg-muted',
    accent: 'text-accent',
    success: 'text-success',
    warning: 'text-warning',
  }[tone]

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-fg-muted">{label}</p>
        <Icon className={cn('h-4 w-4', toneColor)} />
      </div>
      <p className="mt-2.5 font-mono text-2xl font-semibold tabular-nums text-fg">{value}</p>
      <p className="mt-1 text-xs text-fg-subtle">{subtitle}</p>
    </div>
  )
}

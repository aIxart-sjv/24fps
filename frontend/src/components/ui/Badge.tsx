import type { HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide',
  {
    variants: {
      tone: {
        neutral: 'bg-surface-elevated border-border text-fg-muted',
        accent: 'bg-accent/10 border-accent/30 text-accent',
        success: 'bg-success/10 border-success/30 text-success',
        warning: 'bg-warning/10 border-warning/30 text-warning',
        critical: 'bg-critical/10 border-critical/30 text-critical',
        info: 'bg-info/10 border-info/30 text-info',
      },
    },
    defaultVariants: {
      tone: 'neutral',
    },
  },
)

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />
}

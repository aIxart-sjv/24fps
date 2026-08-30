import { cn } from '@/lib/utils'

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded bg-surface-elevated', className)} />
}

export function LoadingState({ label = 'Loading...' }: { label?: string }) {
  return (
    <div className="space-y-3 py-2" role="status" aria-label={label}>
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-5/6" />
      <p className="pt-1 text-xs text-fg-subtle">{label}</p>
    </div>
  )
}

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-11 w-full" />
      ))}
    </div>
  )
}

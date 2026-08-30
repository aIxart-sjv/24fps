import { AlertOctagon } from 'lucide-react'
import { Button } from '@/components/ui/Button'

export function ErrorState({
  title = 'Something went wrong',
  description,
  onRetry,
}: {
  title?: string
  description?: string
  onRetry?: () => void
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-critical/20 bg-critical/5 px-6 py-16 text-center">
      <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-full bg-critical/10">
        <AlertOctagon className="h-5 w-5 text-critical" />
      </div>
      <h3 className="text-sm font-medium text-fg">{title}</h3>
      {description && <p className="mt-1.5 max-w-sm text-sm text-fg-muted">{description}</p>}
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  )
}

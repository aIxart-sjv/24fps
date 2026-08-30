import { Link } from 'react-router-dom'
import { CompassIcon } from 'lucide-react'
import { Button } from '@/components/ui/Button'

export function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <CompassIcon className="mb-4 h-8 w-8 text-fg-subtle" />
      <h1 className="text-lg font-semibold text-fg">Page not found</h1>
      <p className="mt-1.5 text-sm text-fg-muted">This route does not exist in the investigation platform.</p>
      <Link to="/">
        <Button variant="secondary" size="sm" className="mt-4">
          Return to Overview
        </Button>
      </Link>
    </div>
  )
}

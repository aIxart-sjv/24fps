import { Badge, type BadgeProps } from '@/components/ui/Badge'

type Tone = NonNullable<BadgeProps['tone']>

const STATUS_TONE: Record<string, Tone> = {
  // Case status
  Draft: 'neutral',
  Active: 'accent',
  'Under Review': 'warning',
  Closed: 'neutral',
  // Priority
  Low: 'neutral',
  Medium: 'info',
  High: 'warning',
  Critical: 'critical',
  // Hash / integrity status
  Verified: 'success',
  Pending: 'neutral',
  Failed: 'critical',
  Warning: 'warning',
  // Evidence status
  Archived: 'neutral',
  Flagged: 'critical',
  // Device status
  Online: 'success',
  Offline: 'neutral',
  Analyzing: 'accent',
  Error: 'critical',
  // Activity result
  Success: 'success',
  Failure: 'critical',
  // Report status
  Ready: 'success',
  Generating: 'accent',
  // Acquisition / extraction / filesystem parsing status
  'In Progress': 'accent',
  Completed: 'success',
  Extracted: 'success',
  'Partially Extracted': 'warning',
  Recognized: 'success',
  Partial: 'warning',
  Unrecognized: 'critical',
  // Recovery item status
  Recovered: 'success',
  Fragmented: 'warning',
  Deleted: 'critical',
  Damaged: 'critical',
  Unrecoverable: 'critical',
  // Validation status
  Pass: 'success',
  Fail: 'critical',
  // Review status
  Confirmed: 'success',
  Dismissed: 'neutral',
  Unreviewed: 'info',
  // Blockchain anchor status (demo/simulated)
  'Demo Verified': 'success',
  'Pending Anchor': 'warning',
  'Not Anchored': 'neutral',
  // System / AI service status
  Degraded: 'warning',
}

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  return (
    <Badge tone={STATUS_TONE[status] ?? 'neutral'} className={className}>
      {status}
    </Badge>
  )
}

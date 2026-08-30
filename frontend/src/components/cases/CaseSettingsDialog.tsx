import { useState } from 'react'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { updateCaseStatus } from '@/services/mockApi'
import { useToast } from '@/hooks/useToast'
import type { Case, CaseStatus } from '@/services/types'

const STATUSES: CaseStatus[] = ['Draft', 'Active', 'Under Review', 'Closed']

export function CaseSettingsDialog({
  open,
  onOpenChange,
  caseData,
  onUpdated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  caseData: Case
  onUpdated: (updated: Case) => void
}) {
  const { notify } = useToast()
  const [status, setStatus] = useState<CaseStatus>(caseData.status)
  const [submitting, setSubmitting] = useState(false)

  async function handleSave() {
    setSubmitting(true)
    const updated = await updateCaseStatus(caseData.id, status)
    setSubmitting(false)
    if (updated) {
      onOpenChange(false)
      onUpdated(updated)
      notify('Case status updated', { description: `${caseData.id} is now ${status}.`, tone: 'success' })
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Case Settings" description={caseData.id}>
      <div className="space-y-4">
        <div>
          <span className="mb-1.5 block text-xs font-medium text-fg-muted">Case Status</span>
          <div className="flex flex-wrap gap-2">
            {STATUSES.map((s) => (
              <button
                key={s}
                onClick={() => setStatus(s)}
                className={`h-8 rounded-md border px-3 text-xs font-medium transition-colors ${
                  status === s ? 'border-accent/40 bg-accent/10 text-accent' : 'border-border text-fg-muted hover:bg-surface-elevated'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-border pt-4">
          <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" onClick={handleSave} disabled={submitting || status === caseData.status}>
            {submitting ? 'Saving...' : 'Save Changes'}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}

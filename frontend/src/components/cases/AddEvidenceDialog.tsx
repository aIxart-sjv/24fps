import { useState } from 'react'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { createEvidence } from '@/services/mockApi'
import { useToast } from '@/hooks/useToast'
import type { Evidence, SourceType } from '@/services/types'

const SOURCE_TYPES: SourceType[] = ['Forensic Image', 'CCTV Recording', 'Mobile Extraction', 'Document', 'Photograph', 'Audio Recording']

export function AddEvidenceDialog({
  open,
  onOpenChange,
  caseId,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  caseId: string
  onCreated: (evidence: Evidence) => void
}) {
  const { notify } = useToast()
  const [fileName, setFileName] = useState('')
  const [sourceType, setSourceType] = useState<SourceType>('Forensic Image')
  const [originalSource, setOriginalSource] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!fileName.trim()) return
    setSubmitting(true)
    const evidence = await createEvidence({ caseId, fileName, sourceType, originalSource: originalSource || 'Field capture' })
    setSubmitting(false)
    onOpenChange(false)
    setFileName('')
    setOriginalSource('')
    onCreated(evidence)
    notify('Evidence registered successfully', { description: `${evidence.id} added to ${caseId}.`, tone: 'success' })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} variant="panel" title="Add Evidence" description={`Register new evidence to ${caseId}`}>
      <form onSubmit={handleSubmit} className="flex h-full flex-col">
        <div className="flex-1 space-y-4">
          <Field label="File Name">
            <input
              required
              value={fileName}
              onChange={(e) => setFileName(e.target.value)}
              placeholder="e.g. dashcam_footage.mp4"
              className="h-9 w-full rounded-md border border-border bg-surface-elevated px-3 text-sm text-fg placeholder:text-fg-subtle focus:border-accent/50 focus:outline-none"
            />
          </Field>
          <Field label="Source Type">
            <select
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value as SourceType)}
              className="h-9 w-full rounded-md border border-border bg-surface-elevated px-3 text-sm text-fg focus:border-accent/50 focus:outline-none"
            >
              {SOURCE_TYPES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Original Source">
            <input
              value={originalSource}
              onChange={(e) => setOriginalSource(e.target.value)}
              placeholder="e.g. DVR-UNIT-03 or Field capture"
              className="h-9 w-full rounded-md border border-border bg-surface-elevated px-3 text-sm text-fg placeholder:text-fg-subtle focus:border-accent/50 focus:outline-none"
            />
          </Field>
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-border pt-4">
          <Button type="button" variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" size="sm" disabled={submitting || !fileName.trim()}>
            {submitting ? 'Registering...' : 'Register Evidence'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-fg-muted">{label}</span>
      {children}
    </label>
  )
}

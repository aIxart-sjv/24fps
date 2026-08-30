import { useState } from 'react'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { createCase } from '@/services/mockApi'
import { useToast } from '@/hooks/useToast'
import type { Case } from '@/services/types'

const PRIORITIES: Case['priority'][] = ['Low', 'Medium', 'High', 'Critical']
const INVESTIGATORS = ['Insp. R. Mehta', 'Insp. A. Fernandes', 'Insp. S. Kulkarni', 'Insp. N. Rao', 'Insp. P. Singh']

export function NewCaseDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: (newCase: Case) => void
}) {
  const { notify } = useToast()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<Case['priority']>('Medium')
  const [leadInvestigator, setLeadInvestigator] = useState(INVESTIGATORS[0])
  const [submitting, setSubmitting] = useState(false)

  function reset() {
    setName('')
    setDescription('')
    setPriority('Medium')
    setLeadInvestigator(INVESTIGATORS[0])
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    setSubmitting(true)
    const newCase = await createCase({ name, description, priority, leadInvestigator })
    setSubmitting(false)
    onOpenChange(false)
    reset()
    onCreated(newCase)
    notify('Investigation created', { description: `${newCase.id} has been registered.`, tone: 'success' })
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      variant="panel"
      title="New Investigation"
      description="Register a new case in the forensic platform."
    >
      <form onSubmit={handleSubmit} className="flex h-full flex-col">
        <div className="flex-1 space-y-4">
          <Field label="Case Name">
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Highway Incident Investigation"
              className="h-9 w-full rounded-md border border-border bg-surface-elevated px-3 text-sm text-fg placeholder:text-fg-subtle focus:border-accent/50 focus:outline-none"
            />
          </Field>

          <Field label="Description">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              placeholder="Brief summary of the investigation..."
              className="w-full resize-none rounded-md border border-border bg-surface-elevated px-3 py-2 text-sm text-fg placeholder:text-fg-subtle focus:border-accent/50 focus:outline-none"
            />
          </Field>

          <Field label="Priority">
            <div className="flex gap-2">
              {PRIORITIES.map((p) => (
                <button
                  type="button"
                  key={p}
                  onClick={() => setPriority(p)}
                  className={`h-8 flex-1 rounded-md border text-xs font-medium transition-colors ${
                    priority === p
                      ? 'border-accent/40 bg-accent/10 text-accent'
                      : 'border-border text-fg-muted hover:bg-surface-elevated'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </Field>

          <Field label="Lead Investigator">
            <select
              value={leadInvestigator}
              onChange={(e) => setLeadInvestigator(e.target.value)}
              className="h-9 w-full rounded-md border border-border bg-surface-elevated px-3 text-sm text-fg focus:border-accent/50 focus:outline-none"
            >
              {INVESTIGATORS.map((inv) => (
                <option key={inv} value={inv}>
                  {inv}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border pt-4">
          <Button type="button" variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" size="sm" disabled={submitting || !name.trim()}>
            {submitting ? 'Creating...' : 'Create Investigation'}
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

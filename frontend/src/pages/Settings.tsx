import { useEffect, useState } from 'react'
import { Cpu, Database, Palette, ScanEye, SlidersHorizontal } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { useToast } from '@/hooks/useToast'
import { cn } from '@/lib/utils'

const ACCENTS = [
  { name: 'Cyan', value: '#22d3ee' },
  { name: 'Blue', value: '#3b82f6' },
  { name: 'Violet', value: '#a78bfa' },
  { name: 'Emerald', value: '#34d399' },
]

function Toggle({ checked, onChange, disabled }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative h-5 w-9 shrink-0 rounded-full transition-colors disabled:opacity-50',
        checked ? 'bg-accent' : 'bg-surface-elevated border border-border',
      )}
    >
      <span
        className={cn(
          'absolute top-0.5 h-4 w-4 rounded-full bg-background transition-transform',
          checked ? 'translate-x-4' : 'translate-x-0.5',
        )}
      />
    </button>
  )
}

export function Settings() {
  const { notify } = useToast()
  const [timezone, setTimezone] = useState('Asia/Kolkata (IST)')
  const [language, setLanguage] = useState('English')
  const [compactMode, setCompactMode] = useState(false)
  const [accent, setAccent] = useState('#22d3ee')

  useEffect(() => {
    const stored = localStorage.getItem('24fps-accent')
    if (stored) {
      setAccent(stored)
      document.documentElement.style.setProperty('--color-accent', stored)
    }
    const storedCompact = localStorage.getItem('24fps-compact')
    if (storedCompact) setCompactMode(storedCompact === 'true')
  }, [])

  function handleAccentChange(value: string) {
    setAccent(value)
    document.documentElement.style.setProperty('--color-accent', value)
    localStorage.setItem('24fps-accent', value)
    notify('Accent color updated', { tone: 'success' })
  }

  function handleCompactChange(value: boolean) {
    setCompactMode(value)
    localStorage.setItem('24fps-compact', String(value))
    notify(value ? 'Compact mode enabled' : 'Compact mode disabled', { tone: 'info' })
  }

  return (
    <>
      <PageHeader title="Settings" description="Platform configuration and appearance preferences." />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-surface px-4 py-3">
        <div className="flex items-center gap-2.5">
          <ScanEye className="h-4 w-4 text-accent" />
          <span className="font-mono text-xs uppercase tracking-widest text-fg-muted">24FPS Core Configuration</span>
        </div>
        <div className="flex items-center gap-4 font-mono text-[11px] text-fg-subtle">
          <span className="flex items-center gap-1.5">
            <Cpu className="h-3 w-3" />
            Build v1.0.0-demo
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-success" />
            Session Active
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <SlidersHorizontal className="h-4 w-4 text-fg-subtle" />
              General
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Application Name">
              <input
                value="24FPS — Digital Forensic Intelligence Platform"
                readOnly
                className="h-9 w-full rounded-md border border-border bg-surface-elevated px-3 text-sm text-fg-muted"
              />
            </Field>
            <Field label="Time Zone">
              <select
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="h-9 w-full rounded-md border border-border bg-surface-elevated px-3 text-sm text-fg focus:border-accent/50 focus:outline-none"
              >
                <option>Asia/Kolkata (IST)</option>
                <option>UTC</option>
                <option>America/New_York (EST)</option>
              </select>
            </Field>
            <Field label="Language">
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="h-9 w-full rounded-md border border-border bg-surface-elevated px-3 text-sm text-fg focus:border-accent/50 focus:outline-none"
              >
                <option>English</option>
                <option>Hindi</option>
              </select>
            </Field>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-4 w-4 text-fg-subtle" />
              Evidence Storage
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Evidence Root">
              <p className="rounded-md border border-border bg-surface-elevated px-3 py-2 font-mono text-xs text-fg-muted">
                /var/forensic/evidence
              </p>
            </Field>
            <Field label="Artifact Root">
              <p className="rounded-md border border-border bg-surface-elevated px-3 py-2 font-mono text-xs text-fg-muted">
                /var/forensic/artifacts
              </p>
            </Field>
            <Field label="Report Root">
              <p className="rounded-md border border-border bg-surface-elevated px-3 py-2 font-mono text-xs text-fg-muted">
                /var/forensic/reports
              </p>
            </Field>
          </CardContent>
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Palette className="h-4 w-4 text-fg-subtle" />
              Appearance
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-fg">Dark Mode</p>
                <p className="text-xs text-fg-subtle">24FPS is designed dark-first for forensic review environments.</p>
              </div>
              <Toggle checked disabled onChange={() => {}} />
            </div>
            <div className="flex items-center justify-between border-t border-border pt-4">
              <div>
                <p className="text-sm text-fg">Compact Mode</p>
                <p className="text-xs text-fg-subtle">Reduce spacing density across tables and panels.</p>
              </div>
              <Toggle checked={compactMode} onChange={handleCompactChange} />
            </div>
            <div className="border-t border-border pt-4">
              <p className="text-sm text-fg">Accent Color</p>
              <p className="mb-3 text-xs text-fg-subtle">Applied across active states, links, and highlights.</p>
              <div className="flex gap-2.5">
                {ACCENTS.map((a) => (
                  <button
                    key={a.value}
                    onClick={() => handleAccentChange(a.value)}
                    className={cn(
                      'flex h-9 w-9 items-center justify-center rounded-full border-2 transition-transform hover:scale-105',
                      accent === a.value ? 'border-fg' : 'border-transparent',
                    )}
                    aria-label={a.name}
                    title={a.name}
                  >
                    <span className="h-6 w-6 rounded-full" style={{ backgroundColor: a.value }} />
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </>
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

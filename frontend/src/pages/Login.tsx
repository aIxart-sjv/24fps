import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import { EntryBrandBar } from '@/components/landing/EntryBrandBar'
import { useToast } from '@/hooks/useToast'
import { login } from '@/lib/auth'

export function Login() {
  const navigate = useNavigate()
  const { notify } = useToast()
  const [userId, setUserId] = useState('')
  const [password, setPassword] = useState('')
  const [authenticating, setAuthenticating] = useState(false)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!userId.trim() || !password.trim() || authenticating) return
    setAuthenticating(true)
    setTimeout(() => {
      const session = login(userId, password)
      setAuthenticating(false)
      if (!session) return
      notify('Access granted', {
        description: `Signed in as ${session.userId} · ${session.role === 'admin' ? 'Administrator' : 'Investigator'}`,
        tone: 'success',
      })
      navigate('/dashboard')
    }, 650)
  }

  return (
    <div className="relative flex h-screen min-h-[640px] flex-col overflow-hidden bg-background">
      <div className="absolute inset-0 bg-forensic-grid opacity-60" />

      <div className="relative z-10">
        <EntryBrandBar />
      </div>

      <div className="relative z-10 flex flex-1 items-center justify-center px-6">
        <form
          onSubmit={handleSubmit}
          className="w-full max-w-sm rounded-md border border-border bg-surface p-7"
        >
          <div className="mb-6 flex items-center gap-2.5">
            <ShieldCheck className="h-4 w-4 text-forensic-yellow" />
            <p className="font-plex text-sm font-semibold uppercase tracking-widest text-fg">Secure Access</p>
          </div>

          <div className="space-y-4">
            <div>
              <label htmlFor="userId" className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-fg-muted">
                User ID
              </label>
              <input
                id="userId"
                autoFocus
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder="P-1042"
                className="h-10 w-full rounded-md border border-border bg-surface-elevated px-3 font-plex-mono text-sm text-fg placeholder:text-fg-subtle focus:border-forensic-yellow/60 focus:outline-none"
              />
            </div>
            <div>
              <label htmlFor="password" className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-fg-muted">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="h-10 w-full rounded-md border border-border bg-surface-elevated px-3 text-sm text-fg placeholder:text-fg-subtle focus:border-forensic-yellow/60 focus:outline-none"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={!userId.trim() || !password.trim() || authenticating}
            className="mt-6 flex h-11 w-full items-center justify-center rounded-md bg-forensic-yellow font-plex text-sm font-bold uppercase tracking-widest text-forensic-ink transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {authenticating ? 'Authenticating...' : 'Authenticate'}
          </button>

          <p className="mt-5 text-center font-plex-mono text-[11px] leading-relaxed text-fg-subtle">
            Demo access — any User ID and Password combination is accepted.
            <br />
            Use an ID starting with "A-" to preview the admin role.
          </p>
        </form>
      </div>
    </div>
  )
}

/**
 * Frontend-only mock authentication. There is no backend behind this — it
 * exists purely to support the intended Landing → Login → Platform flow and
 * the future Police/Admin role split described in the UI/UX design plan.
 * Any non-empty User ID + Password combination is accepted; the User ID's
 * shape determines the demo role. Nothing here should be mistaken for real
 * authentication or authorization.
 */

export type UserRole = 'investigator' | 'admin'

export interface Session {
  userId: string
  role: UserRole
}

const SESSION_KEY = '24fps-session'

function inferRole(userId: string): UserRole {
  const id = userId.trim().toLowerCase()
  return id === 'admin' || id.startsWith('a-') ? 'admin' : 'investigator'
}

export function login(userId: string, password: string): Session | null {
  if (!userId.trim() || !password.trim()) return null
  const session: Session = { userId: userId.trim(), role: inferRole(userId) }
  localStorage.setItem(SESSION_KEY, JSON.stringify(session))
  return session
}

export function logout(): void {
  localStorage.removeItem(SESSION_KEY)
}

export function getSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    return raw ? (JSON.parse(raw) as Session) : null
  } catch {
    return null
  }
}

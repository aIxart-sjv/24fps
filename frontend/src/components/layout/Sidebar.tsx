import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutGrid,
  FolderKanban,
  FileSearch,
  HardDrive,
  HardDriveDownload,
  LifeBuoy,
  Film,
  GitCommitHorizontal,
  Radar,
  ShieldCheck,
  CheckCircle2,
  Boxes,
  Sparkles,
  Activity,
  FileText,
  Settings,
  ScanEye,
  LogOut,
  LayoutDashboard,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { DemoModeBadge } from '@/components/common/DemoModeBadge'
import { getSession, logout } from '@/lib/auth'

interface NavItem {
  label: string
  to: string
  icon: typeof LayoutGrid
}

const MAIN: NavItem[] = [
  { label: 'Overview', to: '/dashboard', icon: LayoutGrid },
  { label: 'Cases', to: '/cases', icon: FolderKanban },
  { label: 'Evidence', to: '/evidence', icon: FileSearch },
  { label: 'Devices', to: '/devices', icon: HardDrive },
]

const ACQUISITION: NavItem[] = [
  { label: 'Acquisition', to: '/acquisition', icon: HardDriveDownload },
  { label: 'Recovery', to: '/recovery', icon: LifeBuoy },
]

const ANALYSIS: NavItem[] = [
  { label: 'Media Analysis', to: '/analysis', icon: Film },
  { label: 'Cross-Camera Correlation', to: '/correlation', icon: Radar },
  { label: 'Timeline', to: '/timeline', icon: GitCommitHorizontal },
  { label: 'Integrity', to: '/integrity', icon: ShieldCheck },
  { label: 'Validation', to: '/validation', icon: CheckCircle2 },
  { label: 'AI Insights', to: '/insights', icon: Sparkles },
  { label: 'Vendor Normalization', to: '/vendors', icon: Boxes },
]

const SYSTEM: NavItem[] = [
  { label: 'Activity', to: '/activity', icon: Activity },
  { label: 'Reports', to: '/reports', icon: FileText },
  { label: 'Settings', to: '/settings', icon: Settings },
]

const ADMIN: NavItem[] = [{ label: 'Admin Console', to: '/admin', icon: LayoutDashboard }]

function NavSection({ label, items }: { label: string; items: NavItem[] }) {
  return (
    <div>
      <p className="px-3 text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">{label}</p>
      <div className="mt-1.5 space-y-0.5">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/dashboard'}
            className={({ isActive }) =>
              cn(
                'group relative flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive ? 'bg-surface-elevated text-fg' : 'text-fg-muted hover:bg-surface-elevated/60 hover:text-fg',
              )
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={cn(
                    'absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-accent transition-opacity',
                    isActive ? 'opacity-100' : 'opacity-0',
                  )}
                />
                <item.icon className={cn('h-4 w-4 shrink-0', isActive ? 'text-accent' : 'text-fg-subtle group-hover:text-fg-muted')} />
                {item.label}
              </>
            )}
          </NavLink>
        ))}
      </div>
    </div>
  )
}

export function Sidebar() {
  const navigate = useNavigate()
  const session = getSession()
  const displayName = session?.userId ?? 'R. Mehta'
  const roleLabel = session?.role === 'admin' ? 'Administrator' : 'Lead Investigator'
  const initials = session ? session.userId.replace(/[^a-z0-9]/gi, '').slice(0, 2).toUpperCase() : 'RM'

  function handleSignOut() {
    logout()
    navigate('/')
  }

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-border bg-background">
      <div className="flex items-center gap-2.5 px-4 py-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-md border border-accent/30 bg-accent/10">
          <ScanEye className="h-4.5 w-4.5 text-accent" />
        </div>
        <div className="leading-none">
          <p className="text-sm font-bold tracking-tight text-fg">24FPS</p>
          <p className="mt-0.5 text-[9px] font-medium uppercase tracking-wider text-fg-subtle">
            Forensic Intelligence System
          </p>
        </div>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-2 py-2">
        <NavSection label="Main" items={MAIN} />
        <NavSection label="Acquisition" items={ACQUISITION} />
        <NavSection label="Analysis" items={ANALYSIS} />
        <NavSection label="System" items={SYSTEM} />
        {session?.role === 'admin' && <NavSection label="Admin" items={ADMIN} />}
      </nav>

      <div className="border-t border-border p-3">
        <div className="flex items-center gap-2.5 rounded-md px-1.5 py-1.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-elevated text-xs font-semibold text-fg">
            {initials}
          </div>
          <div className="min-w-0 flex-1 leading-none">
            <p className="truncate text-xs font-medium text-fg">{displayName}</p>
            <p className="mt-0.5 truncate text-[11px] text-fg-subtle">{roleLabel}</p>
          </div>
          <button
            onClick={handleSignOut}
            className="shrink-0 rounded p-1.5 text-fg-subtle hover:bg-surface-elevated hover:text-fg"
            aria-label="Sign out"
            title="Sign out"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
        <div className="mt-2.5">
          <DemoModeBadge />
        </div>
      </div>
    </aside>
  )
}

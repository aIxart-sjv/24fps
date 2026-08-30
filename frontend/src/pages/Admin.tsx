import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
import { getSession } from '@/lib/auth'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs'
import { LoadingState } from '@/components/common/LoadingState'
import { cn, formatDateTime, formatBytes } from '@/lib/utils'
import {
  getActivity,
  getAdminUsers,
  getAIServiceStatuses,
  getDevices,
  getSecurityEvents,
  getSystemServices,
} from '@/services/mockApi'
import type { ActivityEvent, AdminUser, AIServiceStatus, Device, SecurityEvent, SystemService } from '@/services/types'

export function Admin() {
  const session = getSession()
  const [services, setServices] = useState<SystemService[] | null>(null)
  const [users, setUsers] = useState<AdminUser[]>([])
  const [security, setSecurity] = useState<SecurityEvent[]>([])
  const [aiServices, setAiServices] = useState<AIServiceStatus[]>([])
  const [activity, setActivity] = useState<ActivityEvent[]>([])
  const [devices, setDevices] = useState<Device[]>([])

  useEffect(() => {
    getSystemServices().then(setServices)
    getAdminUsers().then(setUsers)
    getSecurityEvents().then(setSecurity)
    getAIServiceStatuses().then(setAiServices)
    getActivity().then(setActivity)
    getDevices().then(setDevices)
  }, [])

  if (session?.role !== 'admin') {
    return <Navigate to="/dashboard" replace />
  }

  if (!services) {
    return (
      <>
        <PageHeader title="Admin Console" description="Loading system status..." />
        <LoadingState label="Loading admin console..." />
      </>
    )
  }

  const storageTotal = devices.reduce((sum, d) => sum + d.storageTotal, 0)
  const storageUsed = devices.reduce((sum, d) => sum + d.storageUsed, 0)

  return (
    <>
      <PageHeader
        title="Admin Console"
        description="System status, access control, and audit monitoring. All authorization shown here is simulated — no real access control is enforced."
      />

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">System Status</TabsTrigger>
          <TabsTrigger value="users">Users & Access</TabsTrigger>
          <TabsTrigger value="security">Security Events</TabsTrigger>
          <TabsTrigger value="ai">AI / ML Monitoring</TabsTrigger>
          <TabsTrigger value="audit">Global Audit Log</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4 space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Services</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {services.map((s) => (
                  <div key={s.name} className="flex items-center justify-between gap-3 border-b border-border/60 pb-3 last:border-0 last:pb-0">
                    <div>
                      <p className="text-sm text-fg">{s.name}</p>
                      <p className="mt-0.5 font-mono text-[11px] text-fg-subtle">
                        Load {s.loadPercent}% · {s.failedJobsToday} failed job{s.failedJobsToday === 1 ? '' : 's'} today
                      </p>
                    </div>
                    <StatusBadge status={s.status} />
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Storage</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="font-mono text-2xl font-bold text-fg">{formatBytes(storageUsed)}</p>
                <p className="text-xs text-fg-subtle">of {formatBytes(storageTotal)} across all registered devices</p>
                <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-surface-elevated">
                  <div className="h-full rounded-full bg-accent" style={{ width: `${Math.round((storageUsed / storageTotal) * 100)}%` }} />
                </div>
                <p className="mt-4 text-xs font-medium text-fg-subtle">Case Management</p>
                <p className="mt-1 text-sm text-fg-muted">{devices.length} devices registered across active investigations.</p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="users" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Access Matrix</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs text-fg-subtle">
                      <th className="px-4 py-2.5 font-medium">User ID</th>
                      <th className="px-4 py-2.5 font-medium">Name</th>
                      <th className="px-4 py-2.5 font-medium">Role</th>
                      <th className="px-4 py-2.5 font-medium">Clearance</th>
                      <th className="px-4 py-2.5 font-medium">Assigned Cases</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id} className="border-b border-border/60 last:border-0">
                        <td className="px-4 py-3 font-mono text-xs text-accent">{u.id}</td>
                        <td className="px-4 py-3 text-fg">{u.name}</td>
                        <td className="px-4 py-3 text-fg-muted">{u.roleLabel}</td>
                        <td className="px-4 py-3">
                          <Badge tone={u.clearance === 'L3' ? 'accent' : 'neutral'}>{u.clearance}</Badge>
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-fg-subtle">{u.caseIds.length === 0 ? '—' : u.caseIds.join(', ')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="security" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Security Events</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {security.map((event) => (
                <div
                  key={event.id}
                  className={cn(
                    'flex items-start gap-2.5 rounded-md border p-3',
                    event.severity === 'Critical' ? 'border-critical/30 bg-critical/5' : 'border-warning/30 bg-warning/5',
                  )}
                >
                  <ShieldAlert className={cn('mt-0.5 h-4 w-4 shrink-0', event.severity === 'Critical' ? 'text-critical' : 'text-warning')} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className={cn('text-xs font-semibold uppercase tracking-wide', event.severity === 'Critical' ? 'text-critical' : 'text-warning')}>
                        {event.type}
                      </p>
                      <span className="font-mono text-[11px] text-fg-subtle">{formatDateTime(event.timestamp)}</span>
                    </div>
                    <p className="mt-1 text-sm text-fg">{event.message}</p>
                    <p className="mt-0.5 font-mono text-[11px] text-fg-subtle">Actor: {event.actor}</p>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="ai" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>AI / ML Service Monitoring</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[700px] text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs text-fg-subtle">
                      <th className="px-4 py-2.5 font-medium">Model</th>
                      <th className="px-4 py-2.5 font-medium">Version</th>
                      <th className="px-4 py-2.5 font-medium">Status</th>
                      <th className="px-4 py-2.5 font-medium">Queue</th>
                      <th className="px-4 py-2.5 font-medium">Processed Today</th>
                      <th className="px-4 py-2.5 font-medium">Failed Jobs</th>
                    </tr>
                  </thead>
                  <tbody>
                    {aiServices.map((s) => (
                      <tr key={s.model} className="border-b border-border/60 last:border-0">
                        <td className="px-4 py-3 text-fg">{s.model}</td>
                        <td className="px-4 py-3 font-mono text-xs text-fg-muted">{s.version}</td>
                        <td className="px-4 py-3">
                          <StatusBadge status={s.status} />
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-fg-subtle">{s.queueLength}</td>
                        <td className="px-4 py-3 font-mono text-xs text-fg-subtle">{s.processedToday}</td>
                        <td className="px-4 py-3 font-mono text-xs text-fg-subtle">{s.failedJobs}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="border-t border-border p-3 text-[11px] uppercase tracking-wide text-fg-subtle">
                DEMO ANALYSIS — all AI models and inference activity shown are simulated
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="audit" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Global Audit Log</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs text-fg-subtle">
                      <th className="px-4 py-2.5 font-medium">Timestamp</th>
                      <th className="px-4 py-2.5 font-medium">User</th>
                      <th className="px-4 py-2.5 font-medium">Action</th>
                      <th className="px-4 py-2.5 font-medium">Resource</th>
                      <th className="px-4 py-2.5 font-medium">Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activity.map((a) => (
                      <tr key={a.id} className="border-b border-border/60 last:border-0">
                        <td className="px-4 py-3 font-mono text-xs text-fg-subtle">{formatDateTime(a.timestamp)}</td>
                        <td className="px-4 py-3 text-fg-muted">{a.user}</td>
                        <td className="px-4 py-3 text-fg">{a.action}</td>
                        <td className="px-4 py-3 font-mono text-xs text-fg-subtle">{a.resource} · {a.resourceId}</td>
                        <td className="px-4 py-3">
                          <StatusBadge status={a.result} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </>
  )
}

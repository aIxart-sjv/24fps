import { useEffect, useMemo, useState } from 'react'
import { HardDrive, Search } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { DeviceTable } from '@/components/devices/DeviceTable'
import { DeviceDetailsPanel } from '@/components/devices/DeviceDetailsPanel'
import { EmptyState } from '@/components/common/EmptyState'
import { TableSkeleton } from '@/components/common/LoadingState'
import { getDevices, getEvidence, getRecordings } from '@/services/mockApi'
import type { Device, DeviceStatus, DeviceType, Evidence, Recording } from '@/services/types'

const DEVICE_TYPES: DeviceType[] = ['CCTV DVR', 'NVR', 'Camera', 'Storage Device', 'Mobile Device', 'Forensic Image Source']
const DEVICE_STATUSES: DeviceStatus[] = ['Online', 'Offline', 'Analyzing', 'Error']

export function Devices() {
  const [devices, setDevices] = useState<Device[] | null>(null)
  const [evidence, setEvidence] = useState<Evidence[]>([])
  const [recordings, setRecordings] = useState<Recording[]>([])
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<DeviceType | 'All'>('All')
  const [statusFilter, setStatusFilter] = useState<DeviceStatus | 'All'>('All')
  const [selected, setSelected] = useState<Device | null>(null)

  useEffect(() => {
    getDevices().then(setDevices)
    getEvidence().then(setEvidence)
    getRecordings().then(setRecordings)
  }, [])

  const filtered = useMemo(() => {
    if (!devices) return []
    return devices.filter((d) => {
      const matchesSearch =
        !search.trim() ||
        d.id.toLowerCase().includes(search.toLowerCase()) ||
        d.model.toLowerCase().includes(search.toLowerCase())
      const matchesType = typeFilter === 'All' || d.type === typeFilter
      const matchesStatus = statusFilter === 'All' || d.status === statusFilter
      return matchesSearch && matchesType && matchesStatus
    })
  }, [devices, search, typeFilter, statusFilter])

  return (
    <>
      <PageHeader title="Devices" description="Forensic devices registered across all investigations." />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-subtle" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search devices..."
            className="h-9 w-64 rounded-md border border-border bg-surface pl-8 pr-3 text-sm text-fg placeholder:text-fg-subtle focus:border-accent/50 focus:outline-none"
          />
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as DeviceType | 'All')}
          className="h-9 rounded-md border border-border bg-surface px-3 text-sm text-fg focus:border-accent/50 focus:outline-none"
        >
          <option value="All">All Types</option>
          {DEVICE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as DeviceStatus | 'All')}
          className="h-9 rounded-md border border-border bg-surface px-3 text-sm text-fg focus:border-accent/50 focus:outline-none"
        >
          <option value="All">All Statuses</option>
          {DEVICE_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <span className="ml-auto text-xs text-fg-subtle">{filtered.length} devices</span>
      </div>

      {!devices ? (
        <TableSkeleton />
      ) : filtered.length === 0 ? (
        <EmptyState icon={HardDrive} title="No devices found" description="Try adjusting your search or filters." />
      ) : (
        <DeviceTable devices={filtered} onSelect={setSelected} />
      )}

      <DeviceDetailsPanel
        device={selected}
        evidence={selected ? evidence.filter((e) => e.originalSource === selected.id) : []}
        recordings={selected ? recordings.filter((r) => r.deviceId === selected.id) : []}
        onClose={() => setSelected(null)}
      />
    </>
  )
}

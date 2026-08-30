import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Download } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Card, CardContent } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/common/EmptyState'
import { LoadingState } from '@/components/common/LoadingState'
import { useToast } from '@/hooks/useToast'
import { formatDateTime } from '@/lib/utils'
import { getReports } from '@/services/mockApi'
import type { Report, ReportType } from '@/services/types'

const TYPES: ReportType[] = ['Case Summary', 'Evidence Integrity', 'Media Analysis', 'Timeline', 'Full Forensic Report']

export function Reports() {
  const [reports, setReports] = useState<Report[] | null>(null)
  const [typeFilter, setTypeFilter] = useState<ReportType | 'All'>('All')
  const [selected, setSelected] = useState<Report | null>(null)
  const { notify } = useToast()
  const navigate = useNavigate()

  function handleOpen(report: Report) {
    if (report.type === 'Full Forensic Report') {
      navigate(`/reports/${report.id}`)
    } else {
      setSelected(report)
    }
  }

  useEffect(() => {
    getReports().then(setReports)
  }, [])

  const filtered = reports?.filter((r) => typeFilter === 'All' || r.type === typeFilter) ?? []

  return (
    <>
      <PageHeader title="Reports" description="Generated forensic reports across all investigations." />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <button
          onClick={() => setTypeFilter('All')}
          className={`rounded-md border px-3 py-1.5 text-xs font-medium ${
            typeFilter === 'All' ? 'border-accent/40 bg-accent/10 text-accent' : 'border-border text-fg-muted hover:bg-surface-elevated'
          }`}
        >
          All
        </button>
        {TYPES.map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(t)}
            className={`rounded-md border px-3 py-1.5 text-xs font-medium ${
              typeFilter === t ? 'border-accent/40 bg-accent/10 text-accent' : 'border-border text-fg-muted hover:bg-surface-elevated'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {!reports ? (
        <LoadingState label="Loading reports..." />
      ) : filtered.length === 0 ? (
        <EmptyState icon={FileText} title="No reports found" description="No reports match the selected filter." />
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {filtered.map((report) => (
            <Card
              key={report.id}
              className="cursor-pointer transition-colors hover:border-border-strong"
              onClick={() => handleOpen(report)}
            >
              <CardContent className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-surface-elevated">
                    <FileText className="h-4 w-4 text-fg-subtle" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-fg">{report.name}</p>
                    <p className="mt-0.5 font-mono text-[11px] text-fg-subtle">
                      {report.id} · {report.caseId}
                    </p>
                    <p className="mt-1 text-xs text-fg-subtle">
                      {report.generatedAt ? formatDateTime(report.generatedAt) : 'Not yet generated'}
                    </p>
                  </div>
                </div>
                <StatusBadge status={report.status} />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog
        open={!!selected}
        onOpenChange={(open) => !open && setSelected(null)}
        title={selected?.name ?? ''}
        description={selected ? `${selected.id} · ${selected.type}` : undefined}
      >
        {selected && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <StatusBadge status={selected.status} />
              <span className="text-xs text-fg-subtle">
                {selected.generatedAt ? formatDateTime(selected.generatedAt) : 'Pending generation'}
              </span>
            </div>
            <p className="text-sm leading-relaxed text-fg-muted">{selected.summary}</p>
            <div className="rounded-md border border-dashed border-border bg-surface-elevated p-4 text-center">
              <p className="text-xs text-fg-subtle">Report preview rendering is not available in this prototype.</p>
            </div>
            <Button
              variant="primary"
              size="sm"
              disabled={selected.status !== 'Ready'}
              onClick={() => notify('Report download started', { description: `${selected.id}.pdf`, tone: 'success' })}
            >
              <Download className="h-4 w-4" />
              Download Report
            </Button>
          </div>
        )}
      </Dialog>
    </>
  )
}

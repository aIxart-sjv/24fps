import { useEffect, useState } from 'react'
import { ArrowRight, Boxes } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { LoadingState } from '@/components/common/LoadingState'
import { cn } from '@/lib/utils'
import { getVendorProfiles } from '@/services/mockApi'
import type { VendorProfile, VendorSupportLevel } from '@/services/types'

const SUPPORT_TONE: Record<VendorSupportLevel, 'success' | 'warning' | 'info'> = {
  Full: 'success',
  Partial: 'warning',
  Experimental: 'info',
}

const PIPELINE = ['Vendor', 'Vendor Adapter', 'Normalized Evidence', 'Shared Forensic Engine', 'Standard Report']

export function Vendors() {
  const [vendors, setVendors] = useState<VendorProfile[] | null>(null)

  useEffect(() => {
    getVendorProfiles().then(setVendors)
  }, [])

  if (!vendors) {
    return (
      <>
        <PageHeader title="Vendor Normalization" description="Loading vendor profiles..." />
        <LoadingState label="Loading vendor profiles..." />
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="Vendor Normalization"
        description="Vendor-agnostic architecture: any supported source is normalized into a shared evidence model before analysis. This is a mock representation of the intended architecture, not a claim of full vendor coverage."
      />

      <Card className="mb-4">
        <CardHeader>
          <CardTitle>Normalization Pipeline</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center justify-center gap-2 py-4">
            {PIPELINE.map((stage, i) => (
              <div key={stage} className="flex items-center gap-2">
                <div className="rounded-md border border-border bg-surface-elevated px-4 py-3 text-center">
                  <p className="text-xs font-semibold uppercase tracking-wide text-fg">{stage}</p>
                </div>
                {i < PIPELINE.length - 1 && <ArrowRight className="h-4 w-4 shrink-0 text-fg-subtle" />}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {vendors.map((v) => (
          <Card key={v.vendor}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Boxes className="h-4 w-4 text-accent" />
                {v.vendor}
              </CardTitle>
              <Badge tone={SUPPORT_TONE[v.supportLevel]}>{v.supportLevel} Support</Badge>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <p className="text-xs font-medium text-fg-subtle">Adapter</p>
                <p className="mt-0.5 font-mono text-sm text-fg">{v.adapter}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-fg-subtle">Supported Models</p>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {v.supportedModels.map((m) => (
                    <Badge key={m} tone="neutral">
                      {m}
                    </Badge>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs font-medium text-fg-subtle">Formats Supported</p>
                <ul className="mt-1 space-y-1">
                  {v.formatsSupported.map((f) => (
                    <li key={f} className={cn('text-xs text-fg-muted')}>
                      · {f}
                    </li>
                  ))}
                </ul>
              </div>
              <p className="border-t border-border pt-2.5 text-xs text-fg-subtle">{v.notes}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  )
}

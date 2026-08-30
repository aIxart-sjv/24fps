import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ChevronLeft, FileJson, History, ShieldCheck, Download } from 'lucide-react'
import { EvidenceHeader } from '@/components/evidence/EvidenceHeader'
import { HashCard } from '@/components/evidence/HashCard'
import { VerificationTimeline } from '@/components/evidence/VerificationTimeline'
import { ManifestViewer } from '@/components/evidence/ManifestViewer'
import { CustodyTimeline } from '@/components/evidence/CustodyTimeline'
import { BlockchainAnchorCard } from '@/components/evidence/BlockchainAnchorCard'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { useToast } from '@/hooks/useToast'
import { getEvidenceById, verifyEvidenceHash } from '@/services/mockApi'
import { formatBytes, formatDateTime } from '@/lib/utils'
import type { Evidence } from '@/services/types'

export function EvidenceDetails() {
  const { evidenceId } = useParams<{ evidenceId: string }>()
  const navigate = useNavigate()
  const { notify } = useToast()
  const [evidence, setEvidence] = useState<Evidence | null | undefined>(undefined)
  const [verifying, setVerifying] = useState(false)
  const [manifestOpen, setManifestOpen] = useState(false)
  const [custodyOpen, setCustodyOpen] = useState(false)

  useEffect(() => {
    if (!evidenceId) return
    getEvidenceById(evidenceId).then((e) => setEvidence(e ?? null))
  }, [evidenceId])

  if (evidence === undefined) {
    return <LoadingState label="Loading evidence metadata..." />
  }

  if (evidence === null) {
    return (
      <ErrorState
        title="Evidence not found"
        description={`No evidence record exists for ${evidenceId}.`}
        onRetry={() => navigate('/evidence')}
      />
    )
  }

  async function handleVerify() {
    if (!evidence) return
    setVerifying(true)
    const updated = await verifyEvidenceHash(evidence.id)
    setVerifying(false)
    if (updated) {
      setEvidence({ ...updated })
      notify('SHA-256 verification completed', { description: `${updated.id} hash integrity confirmed.`, tone: 'success' })
    }
  }

  function handleExportMetadata() {
    if (!evidence) return
    const payload = {
      evidence_id: evidence.id,
      case_id: evidence.caseId,
      file_name: evidence.fileName,
      source_type: evidence.sourceType,
      original_source: evidence.originalSource,
      file_size_bytes: evidence.fileSize,
      hashes: { sha256: evidence.sha256, md5: evidence.md5 },
      registered_by: evidence.registeredBy,
      registered_at: evidence.registeredAt,
      status: evidence.status,
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${evidence.id}_metadata.json`
    a.click()
    URL.revokeObjectURL(url)
    notify('Metadata exported', { description: `${evidence.id}_metadata.json downloaded.`, tone: 'success' })
  }

  return (
    <>
      <Link to="/evidence" className="mb-4 inline-flex items-center gap-1 text-xs text-fg-muted hover:text-fg">
        <ChevronLeft className="h-3.5 w-3.5" />
        Back to Evidence
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <EvidenceHeader evidence={evidence} />
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" size="sm" onClick={handleVerify} disabled={verifying}>
            <ShieldCheck className="h-4 w-4" />
            {verifying ? 'Verifying...' : 'Verify Hash'}
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setManifestOpen(true)}>
            <FileJson className="h-4 w-4" />
            Generate Manifest
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setCustodyOpen(true)}>
            <History className="h-4 w-4" />
            Chain of Custody
          </Button>
          <Button variant="outline" size="sm" onClick={handleExportMetadata}>
            <Download className="h-4 w-4" />
            Export Metadata
          </Button>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Evidence Information</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
            <InfoField label="Evidence ID" value={evidence.id} mono />
            <InfoField label="Case" value={evidence.caseId} mono link={`/cases/${evidence.caseId}`} />
            <InfoField label="Source Type" value={evidence.sourceType} />
            <InfoField label="Original Source" value={evidence.originalSource} mono />
            <InfoField label="File Size" value={formatBytes(evidence.fileSize)} mono />
            <InfoField label="Registration Date" value={formatDateTime(evidence.registeredAt)} />
            <InfoField label="Registered By" value={evidence.registeredBy} />
            <div>
              <p className="text-xs font-medium text-fg-subtle">Current Status</p>
              <div className="mt-1.5">
                <StatusBadge status={evidence.status} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Integrity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <HashCard algorithm="SHA-256" value={evidence.sha256} status={evidence.sha256Status} />
            <HashCard algorithm="MD5" value={evidence.md5} status={evidence.md5Status} />
            <BlockchainAnchorCard anchor={evidence.blockchainAnchor} />
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Integrity Verification History</CardTitle>
        </CardHeader>
        <CardContent>
          <VerificationTimeline events={evidence.verificationHistory} />
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Evidence Manifest</CardTitle>
        </CardHeader>
        <CardContent>
          <ManifestViewer evidence={evidence} />
        </CardContent>
      </Card>

      <Dialog open={manifestOpen} onOpenChange={setManifestOpen} title="Evidence Manifest" description={evidence.id}>
        <ManifestViewer evidence={evidence} />
      </Dialog>

      <Dialog open={custodyOpen} onOpenChange={setCustodyOpen} title="Chain of Custody" description={evidence.id}>
        <CustodyTimeline log={evidence.custodyLog} />
      </Dialog>
    </>
  )
}

function InfoField({ label, value, mono, link }: { label: string; value: string; mono?: boolean; link?: string }) {
  const content = <p className={mono ? 'font-mono text-sm text-fg' : 'text-sm text-fg'}>{value}</p>
  return (
    <div>
      <p className="text-xs font-medium text-fg-subtle">{label}</p>
      <div className="mt-1">
        {link ? (
          <Link to={link} className="font-mono text-sm text-accent hover:underline">
            {value}
          </Link>
        ) : (
          content
        )}
      </div>
    </div>
  )
}

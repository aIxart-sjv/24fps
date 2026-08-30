import type { Evidence } from '@/services/types'

export function ManifestViewer({ evidence }: { evidence: Evidence }) {
  const manifest = {
    evidence_id: evidence.id,
    case_id: evidence.caseId,
    file_name: evidence.fileName,
    source_type: evidence.sourceType,
    hashes: {
      sha256: evidence.sha256,
      md5: evidence.md5,
    },
    registered_by: evidence.registeredBy,
    registered_at: evidence.registeredAt,
    generated_at: new Date().toISOString(),
  }

  return (
    <pre className="overflow-x-auto rounded-lg border border-border bg-[#0c0c0e] p-4 font-mono text-xs leading-relaxed text-fg-muted">
      <code>{JSON.stringify(manifest, null, 2)}</code>
    </pre>
  )
}

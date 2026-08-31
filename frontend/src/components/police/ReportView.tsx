import React, { useState } from 'react';
import { useApiQuery } from '../../hooks/useApiQuery';
import { casesApi, reportsApi, saveBlob, ApiError } from '../../lib/api';
import { LoadingState, ErrorState, EmptyState, StatusBadge } from '../common/CommonUI';
import { FileText, Sparkles, Download, Loader2 } from 'lucide-react';
import type { CaseResponse } from '../../lib/apiTypes';

interface ReportViewProps {
  caseId: number;
  caseData: CaseResponse;
}

export const ReportView: React.FC<ReportViewProps> = ({ caseId, caseData }) => {
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  const { data: reports, loading, refetch } = useApiQuery(() => casesApi.reports(caseId), [caseId]);

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      await casesApi.generateReports(caseId);
      refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Report generation failed.');
    } finally {
      setGenerating(false);
    }
  };

  const download = async (reportId: number, reportType: string) => {
    setDownloadingId(reportId);
    try {
      const blob = await reportsApi.downloadBlob(reportId);
      saveBlob(blob, `${caseData.case_id}_report_${reportId}.${reportType}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Download failed.');
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-neutral-800">
          <div>
            <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2">
              <FileText className="w-4 h-4 text-yellow-400" />
              <span>STANDARDIZED FORENSIC REPORT</span>
            </h2>
            <p className="text-xs text-neutral-400 font-mono mt-0.5">
              JSON + PDF, including hashes, provenance, findings, recovery, AI, timeline, and limitations.
            </p>
          </div>
          <button
            onClick={generate}
            disabled={generating}
            className="px-6 py-2.5 rounded bg-yellow-400 hover:bg-yellow-300 disabled:opacity-50 text-neutral-950 font-bold text-xs font-mono uppercase tracking-wider flex items-center gap-2 transition-all"
          >
            {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            <span>{generating ? 'GENERATING…' : 'GENERATE REPORT (JSON + PDF)'}</span>
          </button>
        </div>

        {error && <ErrorState message={error} />}

        {loading && <LoadingState label="Loading reports…" />}
        {!loading && (!reports || reports.length === 0) && (
          <EmptyState message="No reports generated for this case yet." />
        )}
        {!loading && reports && reports.length > 0 && (
          <div className="space-y-2">
            {reports.map((r) => (
              <div key={r.id} className="bg-neutral-900 border border-neutral-800 rounded p-3.5 flex items-center justify-between gap-3 font-mono text-xs">
                <div>
                  <div className="font-bold text-neutral-100">
                    Report #{r.id} · {r.report_type.toUpperCase()}
                  </div>
                  <div className="text-neutral-400 mt-0.5">
                    {r.created_at ? new Date(r.created_at).toLocaleString() : ''}
                    {r.report_hash && ` · sha256: ${r.report_hash.slice(0, 16)}…`}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={r.status} />
                  <button
                    onClick={() => download(r.id, r.report_type)}
                    disabled={downloadingId === r.id || r.status !== 'completed'}
                    className="px-3 py-1.5 rounded bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 text-neutral-200 flex items-center gap-1.5 disabled:opacity-40"
                  >
                    {downloadingId === r.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                    <span>DOWNLOAD</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

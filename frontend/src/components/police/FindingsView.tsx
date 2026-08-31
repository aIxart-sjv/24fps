import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { useApiQuery } from '../../hooks/useApiQuery';
import { casesApi, findingsApi, ApiError } from '../../lib/api';
import { LoadingState, ErrorState, EmptyState, StatusBadge } from '../common/CommonUI';
import { Bell, ChevronDown, ChevronUp, Eye } from 'lucide-react';
import type { FindingResponse } from '../../lib/apiTypes';

interface FindingsViewProps {
  caseId: number;
}

const LIFECYCLE_OPTIONS = ['open', 'acknowledged', 'in_review', 'resolved', 'dismissed'];

const FindingCard: React.FC<{ finding: FindingResponse; onUpdated: (f: FindingResponse) => void }> = ({
  finding,
  onUpdated,
}) => {
  const { requestSeek, setActiveCaseTab } = useApp();
  const [expanded, setExpanded] = useState(false);
  const [notes, setNotes] = useState(finding.resolution_notes ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateStatus = async (status: string) => {
    setSaving(true);
    setError(null);
    try {
      const updated = await findingsApi.update(finding.id, { status, resolution_notes: notes || undefined });
      onUpdated(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Update failed.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded p-4 space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <StatusBadge status={finding.severity} />
          <span className="text-xs font-semibold text-neutral-100 font-sans">{finding.title}</span>
        </div>
        <button onClick={() => setExpanded((v) => !v)} className="text-neutral-400 hover:text-neutral-200">
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>
      <div className="text-[10px] font-mono text-neutral-500 uppercase">
        {finding.finding_type.replace(/_/g, ' ')} · confidence: {finding.confidence} · status: {finding.status}
        {finding.occurrence_count > 1 && ` · seen ${finding.occurrence_count}x`}
      </div>
      <p className="text-xs text-neutral-300 font-sans leading-relaxed">{finding.description}</p>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] font-mono text-neutral-500">
        <span>evidence: {finding.evidence_id ?? 'n/a'}</span>
        <span>recording: {finding.recording_id ?? finding.resolved_recording_id ?? 'n/a'}</span>
        <span>source job: {finding.source_job_id ?? 'n/a'}</span>
        <span>
          timestamp: {finding.resolved_timestamp ? new Date(finding.resolved_timestamp).toLocaleString() : 'NOT AVAILABLE'}
        </span>
        {finding.resolved_recording_id !== null && (
          <button
            onClick={() => {
              requestSeek(finding.resolved_recording_id!, 0);
              setActiveCaseTab('evidence');
            }}
            className="inline-flex items-center gap-1 text-yellow-400 hover:text-yellow-300"
          >
            <Eye className="w-3 h-3" />
            <span>VIEW RECORDING</span>
          </button>
        )}
      </div>

      {expanded && (
        <div className="pt-2 border-t border-neutral-800 space-y-2">
          {finding.limitations && finding.limitations.length > 0 && (
            <div className="text-[11px] font-mono text-amber-400">
              Limitations: {finding.limitations.join('; ')}
            </div>
          )}
          {error && <ErrorState message={error} />}
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Review notes..."
            rows={2}
            className="w-full bg-neutral-950 border border-neutral-800 rounded px-2.5 py-1.5 text-xs font-mono text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-yellow-400 resize-none"
          />
          <div className="flex flex-wrap gap-1.5">
            {LIFECYCLE_OPTIONS.map((opt) => (
              <button
                key={opt}
                onClick={() => updateStatus(opt)}
                disabled={saving || finding.status === opt}
                className={`px-2.5 py-1 rounded text-[10px] font-mono border transition-colors disabled:opacity-40 ${
                  finding.status === opt ? 'border-yellow-400 bg-yellow-400/10 text-yellow-300' : 'border-neutral-700 bg-neutral-950 text-neutral-300 hover:border-neutral-600'
                }`}
              >
                {opt.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
          {finding.resolved_by && (
            <div className="text-[10px] font-mono text-neutral-500">
              Resolved by {finding.resolved_by} at {finding.resolved_at ? new Date(finding.resolved_at).toLocaleString() : '—'}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export const FindingsView: React.FC<FindingsViewProps> = ({ caseId }) => {
  const { data: findings, loading, error, refetch } = useApiQuery(() => casesApi.findings(caseId), [caseId]);
  const [overrides, setOverrides] = useState<Record<number, FindingResponse>>({});

  if (loading) return <LoadingState label="Loading findings…" />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;
  if (!findings || findings.length === 0) {
    return (
      <EmptyState
        icon={<Bell className="w-6 h-6" />}
        message="No findings for this case yet. Findings are generated automatically during processing (integrity mismatches, partial recovery, unsupported formats, timestamp inconsistencies, AI detections, audit-chain issues, and more)."
      />
    );
  }

  const merged = findings.map((f) => overrides[f.id] ?? f);

  return (
    <div className="space-y-3 animate-in fade-in duration-200">
      <div className="text-[11px] font-mono text-neutral-400 pb-2">
        Findings are review-level summaries, ordered most urgent/unresolved first. Severity
        describes review urgency, not proof of any specific cause.
      </div>
      {merged.map((finding) => (
        <FindingCard
          key={finding.id}
          finding={finding}
          onUpdated={(updated) => setOverrides((prev) => ({ ...prev, [updated.id]: updated }))}
        />
      ))}
    </div>
  );
};

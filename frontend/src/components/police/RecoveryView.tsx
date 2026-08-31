import React, { useMemo, useState } from 'react';
import { useApp } from '../../context/AppContext';
import { useApiQuery } from '../../hooks/useApiQuery';
import { casesApi, evidenceApi } from '../../lib/api';
import { StatusBadge, LoadingState, ErrorState, EmptyState } from '../common/CommonUI';
import { ArrowRight, AlertTriangle } from 'lucide-react';
import type { RecoveryResultResponse } from '../../lib/apiTypes';

interface RecoveryViewProps {
  caseId: number;
}

const STATUS_FILTERS = ['ALL', 'recovered', 'partial', 'no_recovery_found', 'unsupported', 'failed'];

// Human-readable labels + a one-line reliability note per recovery
// method, so a raw enum value never has to speak for itself (Phase 24
// task scope, "Recovery UI -- Honest Status").
const METHOD_LABELS: Record<string, { label: string; note: string }> = {
  filesystem_index: {
    label: 'Filesystem/index recovery',
    note: 'Recovery framework only -- see the validation caution below.',
  },
  vendor_damaged_recovery: {
    label: 'Damaged-record reconstruction',
    note: 'Recovers a damaged/truncated record using vendor-specific structure parsing.',
  },
  carving: {
    label: 'Signature carving',
    note: 'Recovers a record by locating its byte signature directly, without index metadata.',
  },
  fragment_reconstruction: {
    label: 'Fragment reconstruction',
    note: 'Reassembles a recording from multiple segment fragments.',
  },
};

export const RecoveryView: React.FC<RecoveryViewProps> = ({ caseId }) => {
  const { setActiveCaseTab, setActiveRecordingId } = useApp();
  const [filterStatus, setFilterStatus] = useState<string>('ALL');

  const { data: evidenceList, loading, error } = useApiQuery(() => casesApi.listEvidence(caseId), [caseId]);

  const { data: allResults, loading: resultsLoading } = useApiQuery(() => {
    if (!evidenceList) return null;
    return Promise.all(evidenceList.map((e) => evidenceApi.recoveryResults(e.id))).then((lists) =>
      lists.flat()
    );
  }, [evidenceList]);

  const counts = useMemo(() => {
    const tally: Record<string, number> = {};
    for (const r of allResults ?? []) tally[r.status] = (tally[r.status] ?? 0) + 1;
    return tally;
  }, [allResults]);

  const filteredResults = (allResults ?? []).filter((r) => filterStatus === 'ALL' || r.status === filterStatus);

  if (loading) return <LoadingState label="Loading evidence…" />;
  if (error) return <ErrorState message={error} />;

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {(['recovered', 'partial', 'no_recovery_found', 'failed'] as const).map((status) => (
          <div key={status} className="bg-neutral-950 border border-neutral-800 rounded p-4 text-left">
            <div className="text-[10px] font-mono text-neutral-400 uppercase tracking-wider">
              {status.replace(/_/g, ' ')}
            </div>
            <div className="text-xl font-bold font-mono text-neutral-100 mt-1">{counts[status] ?? 0}</div>
          </div>
        ))}
      </div>

      <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-neutral-800">
          <h3 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200">
            LAYERED RECOVERY RESULTS
          </h3>
          <div className="flex flex-wrap items-center gap-1 bg-neutral-900 border border-neutral-800 p-1 rounded text-xs font-mono">
            {STATUS_FILTERS.map((st) => (
              <button
                key={st}
                onClick={() => setFilterStatus(st)}
                className={`px-2.5 py-1 rounded transition-colors ${
                  filterStatus === st ? 'bg-yellow-400 text-black font-bold' : 'text-neutral-400 hover:text-neutral-200'
                }`}
              >
                {st.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </div>

        {resultsLoading && <LoadingState label="Loading recovery results…" />}
        {!resultsLoading && filteredResults.length === 0 && (
          <EmptyState message="No recovery attempts recorded yet for this case. Recovery is only valid for evidence formats the backend can structurally parse (currently CP Plus). Run automatic processing to attempt it." />
        )}

        <div className="space-y-3">
          {filteredResults.map((rec: RecoveryResultResponse) => (
            <div
              key={rec.id}
              className="bg-neutral-900 border border-neutral-800 rounded p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:border-neutral-700 transition-colors"
            >
              <div className="space-y-1.5 flex-1">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-sm font-bold text-yellow-400">Result #{rec.id}</span>
                  <StatusBadge status={rec.status} />
                </div>
                <div className="text-xs font-mono text-neutral-400">
                  METHOD: <span className="text-neutral-200">{METHOD_LABELS[rec.method]?.label ?? rec.method}</span>
                  {rec.frame_continuity !== null && (
                    <span> · CONTINUITY: {(rec.frame_continuity * 100).toFixed(0)}%</span>
                  )}
                </div>
                {METHOD_LABELS[rec.method] && (
                  <div className="text-[11px] text-neutral-500 font-sans">{METHOD_LABELS[rec.method].note}</div>
                )}
                {rec.validation_warning && (
                  <div className="flex items-start gap-2 bg-amber-950/30 border border-amber-500/40 rounded p-2.5 mt-1">
                    <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                    <div className="text-[11px] font-mono text-amber-300 leading-snug">{rec.validation_warning}</div>
                  </div>
                )}
                {rec.notes && (
                  <details className="text-[11px] text-neutral-500 font-mono">
                    <summary className="cursor-pointer hover:text-neutral-300">Per-layer debug trace</summary>
                    <div className="mt-1 whitespace-pre-wrap font-sans text-neutral-500">{rec.notes}</div>
                  </details>
                )}
              </div>

              <div className="flex items-center gap-4 shrink-0">
                <div className="text-right">
                  <div className="text-[10px] font-mono text-neutral-400 uppercase">Confidence</div>
                  <div className="text-base font-bold font-mono text-emerald-400">
                    {rec.confidence !== null ? `${Math.round(rec.confidence * 100)}%` : '—'}
                  </div>
                  {rec.frames_recovered !== null && (
                    <div className="text-[10px] font-mono text-neutral-400">
                      {rec.frames_recovered} frame(s) recovered
                    </div>
                  )}
                </div>
                <button
                  onClick={() => {
                    setActiveRecordingId(rec.recording_id);
                    setActiveCaseTab('evidence');
                  }}
                  className="px-3.5 py-2 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-100 hover:text-yellow-400 border border-neutral-700 text-xs font-mono font-bold flex items-center gap-1.5 transition-colors"
                >
                  <span>REVIEW EVIDENCE</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

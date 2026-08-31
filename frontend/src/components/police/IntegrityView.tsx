import React, { useState } from 'react';
import { useApiQuery } from '../../hooks/useApiQuery';
import { casesApi, evidenceApi, ApiError } from '../../lib/api';
import { LoadingState, ErrorState, EmptyState, StatusBadge } from '../common/CommonUI';
import { ShieldCheck, CheckCircle2, XCircle, Loader2 } from 'lucide-react';

interface IntegrityViewProps {
  caseId: number;
}

export const IntegrityView: React.FC<IntegrityViewProps> = ({ caseId }) => {
  const [verifyingId, setVerifyingId] = useState<number | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  const { data: evidenceList, loading, error } = useApiQuery(() => casesApi.listEvidence(caseId), [caseId]);
  const { data: chain, refetch: refetchChain } = useApiQuery(
    () => casesApi.verifyAuditChain(caseId),
    [caseId]
  );
  const { data: events } = useApiQuery(() => casesApi.auditEvents(caseId), [caseId]);
  const { data: validationMetrics } = useApiQuery(() => casesApi.validationMetrics(caseId), [caseId]);

  const { data: hashesByEvidence, refetch: refetchHashes } = useApiQuery(() => {
    if (!evidenceList) return null;
    return Promise.all(evidenceList.map((e) => evidenceApi.hashes(e.id))).then((lists) =>
      Object.fromEntries(evidenceList.map((e, i) => [e.id, lists[i]]))
    );
  }, [evidenceList]);

  const runVerify = async (evidenceId: number) => {
    setVerifyingId(evidenceId);
    setVerifyError(null);
    try {
      await evidenceApi.verify(evidenceId);
      refetchHashes();
    } catch (err) {
      setVerifyError(err instanceof ApiError ? err.message : 'Verification failed.');
    } finally {
      setVerifyingId(null);
    }
  };

  if (loading) return <LoadingState label="Loading evidence…" />;
  if (error) return <ErrorState message={error} />;

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-neutral-800">
          <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-yellow-400" />
            <span>HASH-LINKED AUDIT CHAIN</span>
          </h2>
          {chain && (
            <span
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-bold border ${
                chain.valid ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-400' : 'bg-red-950/30 border-red-500/40 text-red-400'
              }`}
            >
              {chain.valid ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
              <span>{chain.valid ? 'VALID' : 'INVALID'}</span>
            </span>
          )}
        </div>
        {chain && (
          <div className="text-xs font-mono text-neutral-400">
            {chain.event_count} event(s) in chain
            {!chain.valid && chain.failure && (
              <span className="text-red-400"> · first failure at event {chain.failure.event_id}: {chain.failure.reason}</span>
            )}
          </div>
        )}
        <button onClick={refetchChain} className="text-[11px] font-mono text-neutral-400 hover:text-yellow-400 transition-colors">
          Re-verify chain
        </button>
      </div>

      <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-4">
        <h3 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 pb-2 border-b border-neutral-800">
          EVIDENCE HASHES (SHA-256 PRIMARY)
        </h3>
        {verifyError && <ErrorState message={verifyError} />}
        {(evidenceList ?? []).map((e) => {
          const hashes = hashesByEvidence?.[e.id] ?? [];
          const sha256 = hashes.find((h) => h.algorithm === 'sha256');
          const md5 = hashes.find((h) => h.algorithm === 'md5');
          return (
            <div key={e.id} className="bg-neutral-900 border border-neutral-800 rounded p-4 space-y-2 text-xs font-mono">
              <div className="flex items-center justify-between">
                <span className="font-bold text-yellow-400">{e.evidence_id}</span>
                <button
                  onClick={() => runVerify(e.id)}
                  disabled={verifyingId === e.id}
                  className="px-2.5 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-[10px] font-mono flex items-center gap-1.5 border border-neutral-700"
                >
                  {verifyingId === e.id && <Loader2 className="w-3 h-3 animate-spin" />}
                  <span>RE-VERIFY</span>
                </button>
              </div>
              {sha256 ? (
                <div className="flex items-center justify-between gap-2">
                  <span className="text-neutral-400">SHA-256:</span>
                  <StatusBadge status={sha256.verification_status} />
                </div>
              ) : (
                <div className="text-neutral-500">No hash computed yet -- run automatic processing.</div>
              )}
              {sha256 && <div className="text-neutral-300 break-all bg-neutral-950 p-1.5 rounded">{sha256.hash_value}</div>}
              {md5 && (
                <div className="text-neutral-500 text-[10px]">
                  MD5 (compatibility digest only, not the primary integrity mechanism): {md5.hash_value}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-3">
        <h3 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 pb-2 border-b border-neutral-800">
          PROVENANCE / PROCESSING HISTORY
        </h3>
        {!events || events.length === 0 ? (
          <EmptyState message="No processing events recorded yet." />
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {events.map((ev) => (
              <div key={ev.id} className="bg-neutral-900 border border-neutral-800 rounded p-3 text-xs font-mono flex items-center justify-between gap-3">
                <div>
                  <span className="text-neutral-200 font-semibold">{ev.operation.replace(/_/g, ' ')}</span>
                  <span className="text-neutral-500"> by {ev.actor} ({ev.actor_type})</span>
                </div>
                <StatusBadge status={ev.status} />
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-3">
        <h3 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 pb-2 border-b border-neutral-800">
          VALIDATION METRICS
        </h3>
        {!validationMetrics || validationMetrics.length === 0 ? (
          <EmptyState message="No validation has been run for this case -- validation requires a configured ground-truth dataset. No score is fabricated in its absence." />
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {validationMetrics.map((m) => (
              <div key={m.id} className="bg-neutral-900 border border-neutral-800 rounded p-3 text-xs font-mono">
                <div className="text-neutral-400 truncate">{m.metric_name}</div>
                <div className="text-neutral-100 font-bold">{m.metric_value?.toFixed(3) ?? '—'}</div>
                <div className="text-[9px] text-neutral-500">{m.validation_type} · {m.dataset_id}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

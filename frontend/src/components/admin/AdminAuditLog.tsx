import React, { useState } from 'react';
import { useApiQuery } from '../../hooks/useApiQuery';
import { casesApi } from '../../lib/api';
import { LoadingState, ErrorState, EmptyState, StatusBadge } from '../common/CommonUI';
import { Clock } from 'lucide-react';

export const AdminAuditLog: React.FC = () => {
  const { data: cases } = useApiQuery(() => casesApi.list(), []);
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(null);

  const effectiveCaseId = selectedCaseId ?? cases?.[0]?.id ?? null;

  const { data: events, loading, error } = useApiQuery(
    () => (effectiveCaseId !== null ? casesApi.auditEvents(effectiveCaseId) : null),
    [effectiveCaseId]
  );

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-neutral-800">
          <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2">
            <Clock className="w-4 h-4 text-yellow-400" />
            <span>PROCESSING / CUSTODY AUDIT TRAIL</span>
          </h2>
          <select
            value={effectiveCaseId ?? ''}
            onChange={(e) => setSelectedCaseId(Number(e.target.value))}
            className="bg-neutral-900 border border-neutral-800 rounded px-3 py-1.5 text-xs font-mono text-neutral-200"
          >
            {(cases ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.case_id}
              </option>
            ))}
          </select>
        </div>

        <p className="text-[10px] font-mono text-neutral-500">
          Audit history is scoped per case (no cross-case activity endpoint exists in the
          backend). Select a case above to view its hash-linked processing/custody events.
        </p>

        {loading && <LoadingState />}
        {error && <ErrorState message={error} />}
        {!loading && !error && (!events || events.length === 0) && (
          <EmptyState message="No processing events recorded for this case yet." />
        )}
        {!loading && events && events.length > 0 && (
          <div className="divide-y divide-neutral-900 max-h-[600px] overflow-y-auto">
            {events.map((log) => (
              <div key={log.id} className="py-3 flex items-start justify-between gap-4 font-mono text-xs">
                <div className="flex items-start gap-3">
                  <span className="font-bold text-yellow-400 bg-neutral-900 px-2 py-0.5 rounded border border-neutral-800 whitespace-nowrap">
                    {new Date(log.created_at).toLocaleString()}
                  </span>
                  <div>
                    <div className="text-neutral-200">
                      <span className="text-neutral-400">{log.actor}</span> ·{' '}
                      <span className="text-yellow-400">{log.operation}</span>
                    </div>
                    {log.description && <div className="text-[11px] text-neutral-400 font-sans mt-0.5">{log.description}</div>}
                  </div>
                </div>
                <StatusBadge status={log.status} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

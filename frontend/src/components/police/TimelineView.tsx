import React, { useMemo, useState } from 'react';
import { useApp } from '../../context/AppContext';
import { useApiQuery } from '../../hooks/useApiQuery';
import { casesApi } from '../../lib/api';
import { LoadingState, ErrorState, EmptyState, StatusBadge } from '../common/CommonUI';
import { Clock, Eye } from 'lucide-react';
import type { TimelineEventResponse } from '../../lib/apiTypes';

interface TimelineViewProps {
  caseId: number;
}

export const TimelineView: React.FC<TimelineViewProps> = ({ caseId }) => {
  const { setActiveCaseTab, requestSeek } = useApp();
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);

  const { data: events, loading, error } = useApiQuery(() => casesApi.timeline(caseId), [caseId]);
  const { data: correlations } = useApiQuery(
    () => casesApi.correlationEvents(caseId).catch(() => []),
    [caseId]
  );

  const byCamera = useMemo(() => {
    const grouped = new Map<string, TimelineEventResponse[]>();
    for (const event of events ?? []) {
      const camera = event.camera_id ?? 'unassigned';
      if (!grouped.has(camera)) grouped.set(camera, []);
      grouped.get(camera)!.push(event);
    }
    return grouped;
  }, [events]);

  const selectedEvent = (events ?? []).find((e) => e.id === selectedEventId) ?? (events ?? [])[0] ?? null;

  if (loading) return <LoadingState label="Loading timeline…" />;
  if (error) return <ErrorState message={error} />;
  if (!events || events.length === 0) {
    return (
      <EmptyState message="No timeline events recorded yet. Timeline events are ingested automatically from recording start/end times, examiner markers, and correlation runs during automatic processing." />
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-neutral-800">
          <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2">
            <Clock className="w-4 h-4 text-yellow-400" />
            <span>CANONICAL TIMELINE</span>
          </h2>
          <span className="text-[11px] font-mono text-neutral-400">{events.length} event(s)</span>
        </div>

        <div className="space-y-4">
          {Array.from(byCamera.entries()).map(([camera, camEvents]) => (
            <div key={camera} className="space-y-1.5">
              <div className="text-[10px] font-mono uppercase text-neutral-400 font-bold">{camera}</div>
              <div className="flex flex-wrap gap-2">
                {camEvents.map((evt) => (
                  <button
                    key={evt.id}
                    onClick={() => setSelectedEventId(evt.id)}
                    className={`px-2.5 py-1.5 rounded border text-left text-[10px] font-mono transition-all ${
                      evt.id === selectedEventId
                        ? 'border-yellow-400 bg-yellow-400/10 text-yellow-300'
                        : 'border-neutral-800 bg-neutral-900 text-neutral-300 hover:border-neutral-700'
                    }`}
                    title={evt.description ?? evt.event_type}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-bold">{evt.event_type.replace(/_/g, ' ')}</span>
                      <StatusBadge status={evt.timestamp_status} className="scale-90 origin-right" />
                    </div>
                    <div className="text-neutral-400">
                      {evt.normalized_timestamp
                        ? new Date(evt.normalized_timestamp).toLocaleTimeString()
                        : evt.original_timestamp
                          ? new Date(evt.original_timestamp).toLocaleTimeString() + ' (raw)'
                          : 'unresolved time'}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {selectedEvent && (
        <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-neutral-800">
            <div className="flex items-center gap-3">
              <span className="font-mono text-base font-bold text-yellow-400">
                {selectedEvent.event_type.replace(/_/g, ' ')}
              </span>
              <span className="text-neutral-400">•</span>
              <span className="font-mono text-xs text-neutral-300">{selectedEvent.camera_id ?? 'unassigned'}</span>
            </div>

            {selectedEvent.recording_id !== null && (
              <button
                onClick={() => {
                  requestSeek(selectedEvent.recording_id!, 0);
                  setActiveCaseTab('evidence');
                }}
                className="px-4 py-2 rounded bg-yellow-400 hover:bg-yellow-300 text-black font-bold text-xs font-mono flex items-center gap-2 transition-all"
              >
                <Eye className="w-3.5 h-3.5" />
                <span>VIEW RECORDING</span>
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
            <div className="md:col-span-2 bg-neutral-900 border border-neutral-800 rounded p-3.5 space-y-2">
              <div className="text-[10px] text-neutral-400 uppercase font-bold">DESCRIPTION</div>
              <div className="text-sm text-neutral-100 font-sans">
                {selectedEvent.description ?? 'No description recorded.'}
              </div>
            </div>

            <div className="bg-neutral-900 border border-neutral-800 rounded p-3.5 space-y-2">
              <div className="text-[10px] text-neutral-400 uppercase font-bold">SOURCE / CONFIDENCE</div>
              <div className="text-neutral-200">{selectedEvent.source ?? 'unknown'}</div>
              <div className="text-neutral-400">
                {selectedEvent.confidence !== null ? `${Math.round(selectedEvent.confidence * 100)}%` : 'confidence unavailable'}
              </div>
              {selectedEvent.recovery_status && (
                <div className="text-amber-400">recovery: {selectedEvent.recovery_status}</div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 text-xs font-mono">
            <div className="bg-neutral-900 border border-neutral-800 rounded p-3">
              <div className="text-[10px] text-neutral-400 uppercase font-bold">ORIGINAL TIMESTAMP</div>
              <div className="text-neutral-200 mt-1">
                {selectedEvent.original_timestamp ? new Date(selectedEvent.original_timestamp).toLocaleString() : '—'}
              </div>
            </div>
            <div className="bg-neutral-900 border border-neutral-800 rounded p-3">
              <div className="text-[10px] text-neutral-400 uppercase font-bold">NORMALIZED TIMESTAMP</div>
              <div className="text-neutral-200 mt-1">
                {selectedEvent.normalized_timestamp
                  ? new Date(selectedEvent.normalized_timestamp).toLocaleString()
                  : 'NOT AVAILABLE'}
              </div>
            </div>
            <div className="bg-neutral-900 border border-neutral-800 rounded p-3">
              <div className="text-[10px] text-neutral-400 uppercase font-bold">TIMESTAMP STATUS</div>
              <div className="mt-1"><StatusBadge status={selectedEvent.timestamp_status} /></div>
            </div>
            <div className="bg-neutral-900 border border-neutral-800 rounded p-3">
              <div className="text-[10px] text-neutral-400 uppercase font-bold">TIMESTAMP SOURCE</div>
              <div className="text-neutral-200 mt-1">
                {selectedEvent.timestamp_source ? selectedEvent.timestamp_source.replace(/_/g, ' ') : 'NOT AVAILABLE'}
              </div>
            </div>
            <div className="bg-neutral-900 border border-neutral-800 rounded p-3">
              <div className="text-[10px] text-neutral-400 uppercase font-bold">TIMEZONE STATUS</div>
              <div className="mt-1"><StatusBadge status={selectedEvent.timezone_status} /></div>
              {selectedEvent.timezone_basis && (
                <div className="text-neutral-500 mt-1 leading-snug">{selectedEvent.timezone_basis}</div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-3">
        <div className="pb-2 border-b border-neutral-800">
          <h3 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200">
            CROSS-CAMERA CORRELATION
          </h3>
          <p className="text-[10px] font-mono text-neutral-400 mt-0.5">
            Temporal correlation only -- never identity confirmation.
          </p>
        </div>
        {!correlations || correlations.length === 0 ? (
          <EmptyState message="No correlation candidates yet. Correlation requires at least two camera/event sources and runs automatically during case processing, or via POST /cases/{id}/correlation/run." />
        ) : (
          <div className="space-y-2">
            {correlations.map((c) => (
              <div key={c.correlation_event_id} className="bg-neutral-900 border border-neutral-800 rounded p-3 text-xs font-mono">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-yellow-400">Candidate #{c.correlation_event_id}</span>
                  <span className="text-neutral-400">
                    confidence {c.confidence !== null ? `${Math.round(c.confidence * 100)}%` : 'n/a'}
                  </span>
                </div>
                <div className="text-neutral-400 mt-1">{c.event_ids.length} linked event(s) · method: {c.method}</div>
                {c.warnings.length > 0 && <div className="text-amber-400 mt-1">{c.warnings.join('; ')}</div>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

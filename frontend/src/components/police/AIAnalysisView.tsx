import React, { useMemo, useState } from 'react';
import { useApp } from '../../context/AppContext';
import { useApiQuery } from '../../hooks/useApiQuery';
import { casesApi, evidenceApi, aiApi, ApiError } from '../../lib/api';
import { LoadingState, ErrorState, EmptyState } from '../common/CommonUI';
import { VideoSearchView } from './VideoSearchView';
import { resolveSeekSeconds } from '../../lib/videoMapping';
import { Sparkles, ShieldAlert, Loader2, Play, Search } from 'lucide-react';

interface AIAnalysisViewProps {
  caseId: number;
}

const ANALYSIS_TYPES = ['object_detection', 'motion_detection', 'face_detection', 'object_tracking'];

// The investigator's primary AI workflow is AI -> analysis -> visual
// search, all in one workspace (Phase 24 task scope, "Search Location":
// "the investigator should NOT have to leave the AI workspace to perform
// the primary search workflow") -- this sub-tab embeds the existing
// `VideoSearchView` implementation directly rather than duplicating it.
type AISubTab = 'detections' | 'search';

export const AIAnalysisView: React.FC<AIAnalysisViewProps> = ({ caseId }) => {
  const { requestSeekWithHighlight, setActiveCaseTab, addToast } = useApp();
  const [subTab, setSubTab] = useState<AISubTab>('detections');
  const [selectedTypes, setSelectedTypes] = useState<string[]>(['object_detection', 'motion_detection']);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const { data: results, loading, error, refetch } = useApiQuery(() => casesApi.aiResults(caseId), [caseId]);
  const { data: evidenceList } = useApiQuery(() => casesApi.listEvidence(caseId), [caseId]);

  const { data: allRecordings } = useApiQuery(() => {
    if (!evidenceList) return null;
    return Promise.all(evidenceList.map((e) => evidenceApi.recordings(e.id))).then((lists) => lists.flat());
  }, [evidenceList]);

  const classCounts = useMemo<Record<string, { count: number; avgConfidence: number }>>(() => {
    const tally: Record<string, { count: number; avgConfidence: number }> = {};
    for (const r of results ?? []) {
      const entry = tally[r.class_name] ?? { count: 0, avgConfidence: 0 };
      entry.avgConfidence = (entry.avgConfidence * entry.count + r.confidence) / (entry.count + 1);
      entry.count += 1;
      tally[r.class_name] = entry;
    }
    return tally;
  }, [results]);

  const toggleType = (type: string) => {
    setSelectedTypes((prev) => (prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]));
  };

  const runAnalysis = async () => {
    if (!allRecordings || allRecordings.length === 0 || selectedTypes.length === 0) return;
    setRunning(true);
    setRunError(null);
    try {
      const job = await aiApi.runJob({
        case_id: caseId,
        recording_ids: allRecordings.map((r) => r.id),
        analysis_types: selectedTypes,
      });
      addToast({
        title: 'AI analysis complete',
        description: `${job.results_count} result(s) produced (status: ${job.status}).`,
        type: job.status === 'failed' ? 'error' : 'success',
      });
      refetch();
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : 'AI job failed.');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col gap-5 min-h-0 animate-in fade-in duration-200">
      <div className="bg-neutral-950 border border-neutral-800 rounded p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-yellow-400" />
            <span>RUN AI ANALYSIS</span>
          </h2>
          <button
            onClick={runAnalysis}
            disabled={running || !allRecordings || allRecordings.length === 0 || selectedTypes.length === 0}
            className="px-4 py-2 rounded bg-yellow-400 hover:bg-yellow-300 disabled:opacity-50 text-neutral-950 font-bold text-xs font-mono uppercase tracking-wider flex items-center gap-2 transition-all"
          >
            {running ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
            <span>{running ? 'RUNNING…' : 'RUN ON ALL RECORDINGS'}</span>
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {ANALYSIS_TYPES.map((type) => (
            <button
              key={type}
              onClick={() => toggleType(type)}
              className={`px-2.5 py-1 rounded text-[10px] font-mono border transition-colors ${
                selectedTypes.includes(type)
                  ? 'border-yellow-400 bg-yellow-400/10 text-yellow-300'
                  : 'border-neutral-800 bg-neutral-900 text-neutral-400'
              }`}
            >
              {type.replace(/_/g, ' ')}
            </button>
          ))}
        </div>
        {runError && <ErrorState message={runError} />}
      </div>

      <div className="flex items-center gap-1 bg-neutral-900 border border-neutral-800 p-1 rounded text-xs font-mono w-fit">
        <button
          onClick={() => setSubTab('detections')}
          className={`px-3 py-1.5 rounded flex items-center gap-1.5 transition-colors ${
            subTab === 'detections' ? 'bg-yellow-400 text-black font-bold' : 'text-neutral-400 hover:text-neutral-200'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>DETECTIONS</span>
        </button>
        <button
          onClick={() => setSubTab('search')}
          className={`px-3 py-1.5 rounded flex items-center gap-1.5 transition-colors ${
            subTab === 'search' ? 'bg-yellow-400 text-black font-bold' : 'text-neutral-400 hover:text-neutral-200'
          }`}
        >
          <Search className="w-3.5 h-3.5" />
          <span>VISUAL SEARCH</span>
        </button>
      </div>

      {subTab === 'search' ? (
        <VideoSearchView caseId={caseId} />
      ) : (
        <>
          <div className="p-3 rounded bg-amber-950/20 border border-amber-500/30 text-amber-300 text-xs font-mono flex items-start gap-2.5">
            <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5 text-amber-400" />
            <div className="leading-snug">
              <strong className="text-amber-200">AI-ASSISTED FINDING PROTOCOL:</strong> Automated object
              detection is an assistive tool only, not a forensic conclusion. Final evidentiary
              validation requires human investigator review.
            </div>
          </div>

          <div className="bg-neutral-950 border border-neutral-800 rounded p-4 flex-1 min-h-0 overflow-y-auto space-y-4">
            {loading && <LoadingState label="Loading AI results…" />}
            {error && <ErrorState message={error} />}
            {!loading && !error && (!results || results.length === 0) && (
              <EmptyState message="No AI results yet for this case. Run analysis above, or via automatic processing." />
            )}

            {!loading && results && results.length > 0 && (
              <>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {Object.entries(classCounts).map(([className, stats]: [string, { count: number; avgConfidence: number }]) => (
                    <div key={className} className="bg-neutral-900 border border-neutral-800 rounded p-2.5 flex items-center justify-between font-mono text-xs">
                      <span className="text-neutral-200">{className}</span>
                      <span className="text-emerald-400 font-bold">
                        {stats.count} · {Math.round(stats.avgConfidence * 100)}%
                      </span>
                    </div>
                  ))}
                </div>

                <div className="space-y-1.5">
                  {results.slice(0, 100).map((r) => (
                    <button
                      key={r.id}
                      onClick={() => {
                        const recording = allRecordings?.find((rec) => rec.id === r.recording_id);
                        // Preferred seek order (task: "Do NOT invent a
                        // timestamp"): (A) the backend-anchored absolute
                        // timestamp, already tied to this exact frame; (B)
                        // frame_number / the recording's actual source fps.
                        // `null` (never a fabricated 0) when neither the
                        // recording nor an exact mapping is available.
                        const seconds = recording ? resolveSeekSeconds(r, recording) : null;
                        if (seconds === null) {
                          addToast({
                            title: 'Exact position unavailable',
                            description: `No timestamp or frame rate is recorded for this ${r.class_name} detection -- opening the recording without seeking.`,
                            type: 'warning',
                          });
                        }
                        requestSeekWithHighlight(r.recording_id, seconds, [r.id], `${r.class_name} detection`);
                        setActiveCaseTab('evidence');
                      }}
                      className="w-full text-left p-2.5 rounded border border-neutral-800 bg-neutral-900/50 hover:border-neutral-700 transition-all flex items-center justify-between font-mono text-[11px]"
                    >
                      <span className="text-neutral-200">
                        {r.class_name} · frame {r.frame_number}
                        {r.timestamp && ` · ${new Date(r.timestamp).toLocaleTimeString()}`}
                      </span>
                      <span className="text-emerald-400 font-bold">{Math.round(r.confidence * 100)}%</span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
};

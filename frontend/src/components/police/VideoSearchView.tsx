import React, { useRef, useState } from 'react';
import { useApp } from '../../context/AppContext';
import { casesApi, recordingsApi, ApiError } from '../../lib/api';
import { LoadingState, ErrorState } from '../common/CommonUI';
import { Search, ShieldAlert, Info, Eye } from 'lucide-react';
import type { RecordingResponse, VideoSearchResponse, VideoSearchSightingResponse } from '../../lib/apiTypes';
import { resolveSeekSeconds } from '../../lib/videoMapping';

interface VideoSearchViewProps {
  caseId: number;
}

/** A sighting's start point, in the shape `resolveSeekSeconds` expects --
 * the recording's own frame 0 corresponds to its normalized/original start
 * time, the same convention `EvidenceView`'s overlay matching relies on. */
function computeSeekSeconds(sighting: VideoSearchSightingResponse, recording: RecordingResponse): number | null {
  return resolveSeekSeconds({ frame_number: sighting.start_frame, timestamp: sighting.start_timestamp }, recording);
}

/**
 * Deterministic visual-attribute search (task Phase 23 scope, "Required
 * Feature -- Natural-Language Video Search"). See
 * backend/app/ai/attribute_search.py's module docstring for why this is
 * a closed-vocabulary color/class matcher over already-computed AI
 * detections, not a vision-language model or open-ended semantic search.
 */
export const VideoSearchView: React.FC<VideoSearchViewProps> = ({ caseId }) => {
  const { requestSeekWithHighlight, setActiveCaseTab, addToast } = useApp();
  const [query, setQuery] = useState('red shirt guy');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VideoSearchResponse | null>(null);
  const [openingIndex, setOpeningIndex] = useState<number | null>(null);
  const recordingCache = useRef<Map<number, RecordingResponse>>(new Map());

  const runSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const response = await casesApi.videoSearch(caseId, query.trim());
      setResult(response);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Search failed.');
    } finally {
      setLoading(false);
    }
  };

  const openSighting = async (sighting: VideoSearchSightingResponse, index: number) => {
    setOpeningIndex(index);
    setError(null);
    try {
      let recording = recordingCache.current.get(sighting.recording_id);
      if (!recording) {
        recording = await recordingsApi.get(sighting.recording_id);
        recordingCache.current.set(sighting.recording_id, recording);
      }
      const seconds = computeSeekSeconds(sighting, recording);
      if (seconds === null) {
        addToast({
          title: 'Exact position unavailable',
          description: 'No timestamp or frame rate is recorded for this sighting -- opening the recording without seeking.',
          type: 'warning',
        });
      }
      requestSeekWithHighlight(sighting.recording_id, seconds, sighting.ai_result_ids, query.trim());
      setActiveCaseTab('evidence');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not open this recording.');
    } finally {
      setOpeningIndex(null);
    }
  };

  return (
    <div className="flex-1 flex flex-col gap-5 min-h-0 animate-in fade-in duration-200">
      <div className="bg-neutral-950 border border-neutral-800 rounded p-4 space-y-3">
        <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2">
          <Search className="w-4 h-4 text-yellow-400" />
          <span>VISUAL ATTRIBUTE SEARCH</span>
        </h2>
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runSearch()}
            placeholder="e.g. red shirt guy, blue car"
            className="flex-1 bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-sm font-mono text-neutral-100 placeholder-neutral-500 focus:outline-none focus:border-yellow-400"
          />
          <button
            onClick={runSearch}
            disabled={loading}
            className="px-5 py-2 rounded bg-yellow-400 hover:bg-yellow-300 disabled:opacity-50 text-neutral-950 font-bold text-xs font-mono uppercase tracking-wider transition-all"
          >
            {loading ? 'SEARCHING…' : 'SEARCH'}
          </button>
        </div>
      </div>

      <div className="p-3 rounded bg-amber-950/20 border border-amber-500/30 text-amber-300 text-xs font-mono flex items-start gap-2.5">
        <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5 text-amber-400" />
        <div className="leading-snug">
          This is a deterministic clothing-color attribute match over existing AI object
          detections -- not identity recognition. Appearance similarity is evidence, not proof:
          multiple people may share the same detected color.
        </div>
      </div>

      {loading && <LoadingState label="Classifying detections…" />}
      {error && <ErrorState message={error} />}

      {result && !loading && (
        <div className="bg-neutral-950 border border-neutral-800 rounded p-4 flex-1 min-h-0 overflow-y-auto space-y-4">
          {!result.recognized ? (
            <div className="p-3 rounded bg-neutral-900 border border-neutral-800 text-xs font-mono text-neutral-300 flex items-start gap-2">
              <Info className="w-4 h-4 text-neutral-400 shrink-0 mt-0.5" />
              <div>
                No recognized color attribute in that query. Supported colors:{' '}
                <span className="text-yellow-400">{result.supported_colors.join(', ')}</span>. Supported
                classes: <span className="text-yellow-400">{result.supported_classes.join(', ')}</span>.
              </div>
            </div>
          ) : result.sightings.length === 0 ? (
            <div className="p-3 rounded bg-neutral-900 border border-neutral-800 text-xs font-mono text-neutral-300">
              {result.detections_examined} detection(s) examined for color{' '}
              <span className="text-yellow-400">{result.recognized_color}</span>; no matches.
              {result.warnings.map((w, i) => (
                <div key={i} className="text-neutral-400 mt-1">
                  {w}
                </div>
              ))}
            </div>
          ) : (
            <>
              <div className="text-[11px] font-mono text-neutral-400">
                {result.sightings.length} sighting(s) across {result.detections_examined} examined
                detection(s), matching color <span className="text-yellow-400">{result.recognized_color}</span>.
              </div>
              <div className="space-y-2">
                {result.sightings.map((s, idx) => (
                  <button
                    key={idx}
                    onClick={() => openSighting(s, idx)}
                    disabled={openingIndex !== null}
                    className="w-full text-left p-3.5 rounded border border-neutral-800 bg-neutral-900/60 hover:border-yellow-400/60 transition-all font-mono text-xs disabled:opacity-60"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-yellow-400">{s.camera_id ?? `recording ${s.recording_id}`}</span>
                      <span className="text-emerald-400">{Math.round(s.match_confidence * 100)}% match</span>
                    </div>
                    <div className="text-neutral-400 mt-1">
                      {s.start_timestamp ? new Date(s.start_timestamp).toLocaleTimeString() : `frame ${s.start_frame}`}
                      {' – '}
                      {s.end_timestamp ? new Date(s.end_timestamp).toLocaleTimeString() : `frame ${s.end_frame}`}
                    </div>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-neutral-500">
                        {s.class_name} · {s.ai_result_ids.length} detection(s) · track {s.track_id ?? 'n/a'} · artifact{' '}
                        {s.source_artifact}
                      </span>
                      <span className="flex items-center gap-1 text-yellow-400/90">
                        <Eye className="w-3 h-3" />
                        {openingIndex === idx ? 'OPENING…' : 'VIEW IN EVIDENCE'}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </>
          )}
          <div className="text-[10px] font-mono text-neutral-500 pt-2 border-t border-neutral-850">
            method: {result.method} v{result.method_version}
          </div>
        </div>
      )}
    </div>
  );
};

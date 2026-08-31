import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useApp } from '../../context/AppContext';
import { useApiQuery } from '../../hooks/useApiQuery';
import { useVideoDisplayRect } from '../../hooks/useVideoDisplayRect';
import { casesApi, evidenceApi, recordingsApi, artifactDownloadUrl } from '../../lib/api';
import { StatusBadge, LoadingState, ErrorState, EmptyState } from '../common/CommonUI';
import { SubmitEvidenceModal } from './SubmitEvidenceModal';
import { Plus, Search, Layers, ShieldCheck, FileVideo, RefreshCw, X } from 'lucide-react';
import type { RecordingResponse } from '../../lib/apiTypes';
import { hasUsableBox, frameDistance, computeOverlayBoxRect } from '../../lib/videoMapping';

interface EvidenceViewProps {
  caseId: number;
}

// Human-readable labels distinguishing derived master/preview/recovered
// media from each other -- never implying any of these is the preserved
// source evidence itself (Phase 24 task scope, "Evidence Details": "Make
// source vs derived relationships obvious").
const ARTIFACT_TYPE_LABELS: Record<string, string> = {
  cp_plus_hevc_master_mp4: 'H.265 Master (derived)',
  cp_plus_h264_preview_mp4: 'H.264 Browser Preview (derived)',
  cp_plus_hevc_elementary_stream: 'HEVC Elementary Stream (derived)',
  cp_plus_recovered_hevc_elementary_stream: 'Recovered HEVC Elementary Stream (derived)',
};

function usePreviewArtifactId(recordingId: number | null) {
  return useApiQuery(() => {
    if (recordingId === null) return null;
    return recordingsApi.metadata(recordingId).then((entries) => {
      const entry = entries.find((e) => e.key === 'preview_artifact_id');
      return entry?.value ? Number(entry.value) : null;
    });
  }, [recordingId]);
}

const FRAME_MATCH_TOLERANCE = 1; // seconds worth of frames, converted via fps below

const RecordingPlayer: React.FC<{ recording: RecordingResponse; caseId: number }> = ({ recording, caseId }) => {
  const {
    pendingSeekSeconds,
    consumePendingSeek,
    highlightedAiResultIds,
    highlightedQuery,
    clearHighlight,
  } = useApp();
  const videoRef = useRef<HTMLVideoElement>(null);
  const displayRect = useVideoDisplayRect(videoRef);
  const [showAllDetections, setShowAllDetections] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);

  const { data: previewArtifactId, loading: metaLoading } = usePreviewArtifactId(recording.id);
  const { data: aiResults } = useApiQuery(
    () => casesApi.aiResults(caseId, recording.id).catch(() => []),
    [caseId, recording.id]
  );

  // `videoRef.current` is null until the <video> element actually mounts
  // (this component shows a loading state until its preview-artifact
  // fetch resolves), and a plain `[pendingSeekSeconds, consumePendingSeek]`
  // dependency array never re-fires once the node later appears -- a
  // detection click landing before that fetch resolves would set
  // `pendingSeekSeconds` but never actually seek, leaving the video at
  // its natural start (task: "Do NOT always seek to 0"). Re-checking on
  // every render via a ref-mirrored render tick closes that race; once a
  // seek is applied it's also only safe once the browser has decoded the
  // (possibly just-swapped) source's metadata, so wait for `loadedmetadata`
  // when it hasn't loaded yet rather than assigning `currentTime` blind.
  const [videoMounted, setVideoMounted] = useState(false);
  useEffect(() => {
    setVideoMounted(videoRef.current !== null);
  });
  useEffect(() => {
    const video = videoRef.current;
    if (pendingSeekSeconds === null || !video) return undefined;

    const applySeek = () => {
      video.currentTime = pendingSeekSeconds;
      consumePendingSeek();
    };

    if (video.readyState >= HTMLMediaElement.HAVE_METADATA) {
      applySeek();
      return undefined;
    }
    video.addEventListener('loadedmetadata', applySeek, { once: true });
    return () => video.removeEventListener('loadedmetadata', applySeek);
  }, [pendingSeekSeconds, consumePendingSeek, videoMounted]);

  const validResults = useMemo(
    () => (aiResults ?? []).filter((r) => hasUsableBox(r.bbox)),
    [aiResults]
  );

  const currentFrame = recording.fps ? Math.round(currentTime * recording.fps) : null;
  const toleranceFrames = recording.fps ? Math.max(1, Math.round(recording.fps * FRAME_MATCH_TOLERANCE)) : null;

  const { boxes: displayedBoxes, primary: primaryBox } = useMemo(() => {
    // `frameDistance` returns a frame count when fps is known, or a
    // "seconds" distance (scaled by fps||1, i.e. just seconds) otherwise
    // -- the tolerance below is expressed in the same matching unit.
    const tolerance = toleranceFrames !== null ? toleranceFrames : 0.75;
    const nearby = validResults.filter((r) => frameDistance(r, currentFrame, currentTime, recording) <= tolerance);
    // Prefer an exact-frame match over a within-tolerance one (task:
    // "Prefer exact frame matching").
    const exact = currentFrame !== null ? nearby.filter((r) => r.frame_number === currentFrame) : [];
    const frameCandidates = exact.length > 0 ? exact : nearby;

    if (highlightedAiResultIds && !showAllDetections) {
      const highlightedSet = new Set(highlightedAiResultIds);
      const highlightedNearby = frameCandidates.filter((r) => highlightedSet.has(r.id));
      if (highlightedNearby.length > 0) {
        return { boxes: highlightedNearby, primary: highlightedNearby[0] };
      }
      // Nothing highlighted is close to the current frame yet (e.g. the
      // seek just landed) -- fall back to the single nearest highlighted
      // detection so a box still appears, per "video jumps to the match".
      const allHighlighted = validResults.filter((r) => highlightedSet.has(r.id));
      if (allHighlighted.length === 0) return { boxes: [], primary: null };
      const nearest = allHighlighted.reduce((best, r) =>
        frameDistance(r, currentFrame, currentTime, recording) < frameDistance(best, currentFrame, currentTime, recording)
          ? r
          : best
      );
      return { boxes: [nearest], primary: nearest };
    }

    return { boxes: frameCandidates, primary: frameCandidates[0] ?? null };
  }, [validResults, currentFrame, currentTime, recording, toleranceFrames, highlightedAiResultIds, showAllDetections]);

  if (metaLoading) return <LoadingState label="Loading recording…" />;

  if (!previewArtifactId) {
    return (
      <div className="aspect-video w-full bg-black rounded border border-neutral-800 flex items-center justify-center">
        <EmptyState message="No browser-playable preview has been extracted for this recording yet. Run automatic processing or POST /recordings/{id}/extract." />
      </div>
    );
  }

  // The video source's authoritative decoded resolution -- prefer the
  // element's own intrinsic size (always correct once metadata has
  // loaded) over the possibly-null/stale `Recording.width/height` (task:
  // "Do not hardcode 1920x1080... support different video resolutions").
  const sourceWidth = displayRect?.videoWidth ?? recording.width ?? null;
  const sourceHeight = displayRect?.videoHeight ?? recording.height ?? null;
  const canRenderBoxes = displayRect !== null && sourceWidth !== null && sourceHeight !== null;

  return (
    <div className="space-y-2">
      <div className="relative aspect-video w-full bg-black rounded border border-neutral-800 overflow-hidden">
        <video
          ref={videoRef}
          src={artifactDownloadUrl(previewArtifactId)}
          controls
          className="w-full h-full"
          style={{ objectFit: 'contain' }}
          onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
          onSeeked={(e) => setCurrentTime(e.currentTarget.currentTime)}
        />
        {/* Overlay layer: absolutely positioned over the actual displayed
            video rectangle (letterbox-aware), never over the raw container
            (task: "The overlay must remain over the actual video content,
            including when letterbox padding exists"). Never intercepts
            clicks, so playback controls keep working underneath. */}
        {canRenderBoxes && (
          <div className="absolute inset-0 pointer-events-none">
            {displayedBoxes.map((box) => {
              const rect = computeOverlayBoxRect(box.bbox, sourceWidth!, sourceHeight!, displayRect!);
              if (rect === null) return null;
              const { left, top, width, height } = rect;

              const isPrimary = highlightedAiResultIds?.includes(box.id) ?? false;

              return (
                <div
                  key={box.id}
                  className={`absolute border-2 rounded-sm ${
                    isPrimary ? 'border-yellow-400 shadow-[0_0_0_1px_rgba(0,0,0,0.6)]' : 'border-cyan-400/70'
                  }`}
                  style={{ left, top, width, height }}
                >
                  <span
                    className={`absolute -top-5 left-0 text-[9px] font-mono font-bold px-1 rounded-xs whitespace-nowrap ${
                      isPrimary ? 'text-black bg-yellow-400' : 'text-black bg-cyan-400'
                    }`}
                  >
                    {box.class_name.toUpperCase()} [{Math.round(box.confidence * 100)}%]
                    {box.track_id !== null && ` · #${box.track_id}`}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {highlightedAiResultIds && (
          <div className="absolute top-2 left-2 flex items-center gap-2">
            <label className="flex items-center gap-1.5 px-2 py-1 rounded bg-black/70 border border-neutral-700 text-[10px] font-mono text-neutral-200 cursor-pointer">
              <input
                type="checkbox"
                checked={showAllDetections}
                onChange={(e) => setShowAllDetections(e.target.checked)}
                className="accent-yellow-400"
              />
              <span>SHOW ALL DETECTIONS</span>
            </label>
            <button
              onClick={clearHighlight}
              title="Clear search highlight"
              className="p-1 rounded bg-black/70 border border-neutral-700 text-neutral-300 hover:text-yellow-400"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        )}
      </div>

      {highlightedAiResultIds && primaryBox && (
        <div className="bg-neutral-900 border border-yellow-400/40 rounded p-3 text-xs font-mono grid grid-cols-2 sm:grid-cols-4 gap-2">
          {highlightedQuery && (
            <div className="col-span-2 sm:col-span-4 text-neutral-400">
              Search: <span className="text-yellow-400">"{highlightedQuery}"</span>
            </div>
          )}
          <div>
            <div className="text-[9px] text-neutral-500 uppercase">Class</div>
            <div className="text-neutral-100">{primaryBox.class_name}</div>
          </div>
          <div>
            <div className="text-[9px] text-neutral-500 uppercase">Confidence</div>
            <div className="text-emerald-400">{Math.round(primaryBox.confidence * 100)}%</div>
          </div>
          <div>
            <div className="text-[9px] text-neutral-500 uppercase">Frame</div>
            <div className="text-neutral-100">{primaryBox.frame_number}</div>
          </div>
          <div>
            <div className="text-[9px] text-neutral-500 uppercase">Track</div>
            <div className="text-neutral-100">{primaryBox.track_id ?? 'n/a'}</div>
          </div>
          <div>
            <div className="text-[9px] text-neutral-500 uppercase">Timestamp</div>
            <div className="text-neutral-100">
              {primaryBox.timestamp ? new Date(primaryBox.timestamp).toLocaleTimeString() : 'unresolved'}
            </div>
          </div>
          <div className="col-span-1 sm:col-span-3">
            <div className="text-[9px] text-neutral-500 uppercase">Source Recording</div>
            <div className="text-neutral-100 truncate">{recording.recording_id}</div>
          </div>
        </div>
      )}
    </div>
  );
};

export const EvidenceView: React.FC<EvidenceViewProps> = ({ caseId }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<number | null>(null);
  const [selectedRecordingId, setSelectedRecordingId] = useState<number | null>(null);
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState(false);
  const { activeRecordingId, setActiveRecordingId, clearHighlight, addToast } = useApp();

  const { data: evidenceList, loading, error, refetch } = useApiQuery(
    () => casesApi.listEvidence(caseId),
    [caseId]
  );

  useEffect(() => {
    if (evidenceList && evidenceList.length > 0 && selectedEvidenceId === null) {
      setSelectedEvidenceId(evidenceList[0].id);
    }
  }, [evidenceList, selectedEvidenceId]);

  // A recording jump requested from Timeline/AI/Search (`activeRecordingId`)
  // is a one-shot navigation signal, not persistent "current" state: it
  // may belong to an evidence item other than the one currently selected,
  // so resolve its owning evidence first, then consume (clear) the
  // signal so a later manual evidence/recording switch isn't immediately
  // overridden back to it.
  useEffect(() => {
    if (activeRecordingId === null) return;
    let cancelled = false;
    recordingsApi
      .get(activeRecordingId)
      .then((recording) => {
        if (cancelled) return;
        setSelectedEvidenceId(recording.evidence_id);
        setSelectedRecordingId(recording.id);
        setActiveRecordingId(null);
      })
      .catch(() => {
        if (cancelled) return;
        // Honest failure, not a silent no-op: the requested recording
        // doesn't exist/isn't reachable, so there's nothing to seek.
        addToast({
          title: 'Recording not found',
          description: 'Could not open the recording for this detection/result.',
          type: 'error',
        });
        setActiveRecordingId(null);
      });
    return () => {
      cancelled = true;
    };
  }, [activeRecordingId, setActiveRecordingId]);

  const { data: recordings, loading: recordingsLoading, refetch: refetchRecordings } = useApiQuery(
    () => (selectedEvidenceId !== null ? evidenceApi.recordings(selectedEvidenceId) : null),
    [selectedEvidenceId]
  );

  const { data: hashes } = useApiQuery(
    () => (selectedEvidenceId !== null ? evidenceApi.hashes(selectedEvidenceId) : null),
    [selectedEvidenceId]
  );
  const { data: artifacts } = useApiQuery(
    () => (selectedEvidenceId !== null ? evidenceApi.artifacts(selectedEvidenceId) : null),
    [selectedEvidenceId]
  );

  useEffect(() => {
    if (recordings && recordings.length > 0 && selectedRecordingId === null) {
      setSelectedRecordingId(recordings[0].id);
    }
  }, [recordings, selectedRecordingId]);

  const filteredEvidence = (evidenceList ?? []).filter(
    (item) =>
      searchQuery.trim() === '' ||
      item.evidence_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (item.source_description ?? '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  const selectedEvidence = (evidenceList ?? []).find((e) => e.id === selectedEvidenceId) ?? null;
  const selectedRecording = (recordings ?? []).find((r) => r.id === selectedRecordingId) ?? null;
  // Explicitly matched by algorithm -- never assume list order, since a
  // hash list mixes SHA-256 and MD5 rows and this project's own rule is
  // "SHA-256 = primary integrity hash, MD5 = additional compatibility/
  // legacy digest" (never the reverse, and never mislabeled).
  const sha256Hash = (hashes ?? []).find((h) => h.algorithm === 'sha256') ?? null;
  const md5Hash = (hashes ?? []).find((h) => h.algorithm === 'md5') ?? null;

  return (
    <div className="flex-1 flex flex-col gap-4 min-h-0 animate-in fade-in duration-200">
      <div className="bg-neutral-950 border border-neutral-800 rounded p-3 sm:p-4 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-neutral-400 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search evidence by ID or description..."
            className="w-full bg-neutral-900 border border-neutral-800 rounded pl-8 pr-3 py-1.5 text-xs font-mono text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-yellow-400"
          />
        </div>
        <button
          onClick={() => setIsSubmitModalOpen(true)}
          className="px-4 py-2 rounded bg-yellow-400 hover:bg-yellow-300 text-neutral-950 font-bold text-xs font-mono uppercase tracking-wider flex items-center justify-center gap-1.5 transition-all active:scale-98 shadow-md cursor-pointer shrink-0"
        >
          <Plus className="w-4 h-4 stroke-[3]" />
          <span>SUBMIT EVIDENCE</span>
        </button>
      </div>

      <div className="flex-1 flex flex-col lg:flex-row gap-4 min-h-0">
        <div className="w-full lg:w-72 xl:w-80 shrink-0 bg-neutral-950 border border-neutral-800 rounded flex flex-col max-h-[350px] lg:max-h-none">
          <div className="p-3.5 border-b border-neutral-800 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-yellow-400" />
              <h2 className="text-xs font-mono uppercase font-bold text-neutral-200">EVIDENCE ITEMS</h2>
            </div>
            <span className="text-[11px] font-mono text-neutral-400">{filteredEvidence.length}</span>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-neutral-900/80 p-2 space-y-1">
            {loading && <LoadingState />}
            {error && <ErrorState message={error} onRetry={refetch} />}
            {!loading && !error && filteredEvidence.length === 0 && (
              <EmptyState message="No evidence has been registered for this case yet." />
            )}
            {!loading &&
              !error &&
              filteredEvidence.map((item) => {
                const isSelected = item.id === selectedEvidenceId;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      setSelectedEvidenceId(item.id);
                      setSelectedRecordingId(null);
                      clearHighlight();
                    }}
                    className={`w-full text-left p-3 rounded border transition-all flex flex-col gap-1.5 cursor-pointer ${
                      isSelected
                        ? 'bg-neutral-900 border-yellow-400/80 shadow-sm'
                        : 'bg-neutral-950/60 border-neutral-800/80 hover:bg-neutral-900/60 hover:border-neutral-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className={`font-mono text-xs font-bold ${isSelected ? 'text-yellow-400' : 'text-neutral-200'}`}>
                        {item.evidence_id}
                      </span>
                      <StatusBadge status={item.status} />
                    </div>
                    <div className="text-[11px] font-mono text-neutral-400 truncate">{item.source_type}</div>
                    {item.source_description && (
                      <div className="text-[10px] text-neutral-500 truncate">{item.source_description}</div>
                    )}
                  </button>
                );
              })}
          </div>
        </div>

        <div className="flex-1 flex flex-col bg-neutral-950 border border-neutral-800 rounded min-h-0 overflow-y-auto">
          {!selectedEvidence ? (
            <div className="p-8 text-center text-xs font-mono text-neutral-400">
              Select or submit evidence to view details.
            </div>
          ) : (
            <div className="p-4 sm:p-5 flex flex-col gap-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-neutral-800">
                <div>
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-base font-bold text-yellow-400">{selectedEvidence.evidence_id}</span>
                    <StatusBadge status={selectedEvidence.status} />
                  </div>
                  <div className="text-[11px] font-mono text-neutral-400 mt-1">
                    SOURCE TYPE: {selectedEvidence.source_type} · REGISTERED{' '}
                    {new Date(selectedEvidence.created_at).toLocaleString()}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  {sha256Hash ? (
                    <span
                      className="inline-flex items-center gap-1 text-[11px] font-mono text-emerald-400 bg-emerald-950/30 border border-emerald-500/30 px-2 py-0.5 rounded"
                      title={sha256Hash.hash_value}
                    >
                      <ShieldCheck className="w-3.5 h-3.5" />
                      <span>SHA-256 (primary): {sha256Hash.verification_status.toUpperCase()}</span>
                    </span>
                  ) : (
                    <span className="text-[11px] font-mono text-neutral-500">SHA-256: NOT AVAILABLE</span>
                  )}
                  {md5Hash && (
                    <span
                      className="inline-flex items-center gap-1 text-[10px] font-mono text-neutral-400"
                      title={md5Hash.hash_value}
                    >
                      <span>MD5 (compatibility/legacy): {md5Hash.verification_status.toUpperCase()}</span>
                    </span>
                  )}
                </div>
              </div>

              <div className="bg-neutral-900/60 border border-neutral-800 rounded p-3">
                <div className="text-[10px] font-mono uppercase text-neutral-400 tracking-wider mb-2">
                  SOURCE / DERIVED CHAIN
                </div>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-[11px] font-mono gap-3">
                    <span className="text-neutral-200 font-bold">SOURCE — {selectedEvidence.source_type}</span>
                    <span className="text-neutral-500 truncate" title={sha256Hash?.hash_value ?? undefined}>
                      {sha256Hash ? `sha256:${sha256Hash.hash_value.slice(0, 12)}…` : 'hash NOT AVAILABLE'}
                    </span>
                  </div>
                  {!artifacts || artifacts.length === 0 ? (
                    <div className="text-[11px] font-mono text-neutral-500 pl-4">
                      No derived artifacts produced yet for this evidence item.
                    </div>
                  ) : (
                    artifacts.map((a) => (
                      <div key={a.id} className="flex items-center justify-between text-[11px] font-mono gap-3 pl-4">
                        <span className="text-neutral-300">
                          {ARTIFACT_TYPE_LABELS[a.artifact_type] ?? `${a.artifact_type} (derived)`}
                          {a.parent_artifact_id !== null && (
                            <span className="text-neutral-500"> ← from artifact #{a.parent_artifact_id}</span>
                          )}
                        </span>
                        <span className="flex items-center gap-2 shrink-0">
                          <StatusBadge status={a.status} />
                          <span className="text-neutral-500 truncate max-w-[10rem]" title={a.sha256 ?? undefined}>
                            {a.sha256 ? `sha256:${a.sha256.slice(0, 10)}…` : 'hash n/a'}
                          </span>
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {recordingsLoading && <LoadingState label="Loading recordings…" />}
              {!recordingsLoading && (!recordings || recordings.length === 0) && (
                <EmptyState
                  icon={<FileVideo className="w-6 h-6" />}
                  message="No recordings have been enumerated for this evidence item yet. Run automatic processing from the case overview."
                />
              )}
              {selectedRecording && <RecordingPlayer recording={selectedRecording} caseId={caseId} />}

              {recordings && recordings.length > 1 && (
                <div>
                  <div className="text-[10px] font-mono uppercase text-neutral-400 mb-2 tracking-wider">
                    RECORDINGS ({recordings.length}):
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {recordings.map((rec) => (
                      <button
                        key={rec.id}
                        onClick={() => {
                          setSelectedRecordingId(rec.id);
                          clearHighlight();
                        }}
                        className={`p-2.5 rounded border text-left transition-all cursor-pointer ${
                          rec.id === selectedRecordingId
                            ? 'border-yellow-400 bg-yellow-400/10 text-neutral-100'
                            : 'border-neutral-800 bg-neutral-900/70 text-neutral-400 hover:border-neutral-700'
                        }`}
                      >
                        <div className="font-mono text-xs font-bold">{rec.recording_id}</div>
                        <div className="text-[9px] font-mono text-neutral-400 mt-0.5">
                          {rec.camera_id ?? (rec.channel !== null ? `CH${rec.channel}` : 'unknown channel')}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {selectedRecording && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                  <div className="bg-neutral-900 border border-neutral-800 rounded p-4 space-y-2.5 text-xs font-mono">
                    <div className="text-[10px] uppercase font-bold text-neutral-400 pb-1.5 border-b border-neutral-800">
                      RECORDING SPECIFICATION
                    </div>
                    <div className="flex justify-between">
                      <span className="text-neutral-400">Codec / Container:</span>
                      <span className="text-neutral-200 font-semibold">
                        {selectedRecording.codec ?? '—'} / {selectedRecording.container ?? '—'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-neutral-400">Resolution:</span>
                      <span className="text-neutral-200 font-semibold">
                        {selectedRecording.width && selectedRecording.height
                          ? `${selectedRecording.width}x${selectedRecording.height}`
                          : '—'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-neutral-400">Duration:</span>
                      <span className="text-neutral-200 font-semibold">
                        {selectedRecording.duration_ms ? `${(selectedRecording.duration_ms / 1000).toFixed(1)}s` : '—'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-neutral-400">Original Start (raw):</span>
                      <span className="text-neutral-200 font-semibold">
                        {selectedRecording.start_original ? new Date(selectedRecording.start_original).toLocaleString() : '—'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-neutral-400">Normalized Start:</span>
                      <span className="text-neutral-200 font-semibold">
                        {selectedRecording.start_normalized
                          ? new Date(selectedRecording.start_normalized).toLocaleString()
                          : 'unresolved'}
                      </span>
                    </div>
                  </div>

                  <div className="bg-neutral-900 border border-neutral-800 rounded p-4 space-y-2.5 text-xs font-mono">
                    <div className="text-[10px] uppercase font-bold text-neutral-400 pb-1.5 border-b border-neutral-800">
                      RECOVERY STATUS
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-neutral-400">Status:</span>
                      <StatusBadge status={selectedRecording.recovery_status ?? 'not_attempted'} />
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-neutral-400">Method:</span>
                      <span className="text-neutral-200">{selectedRecording.recovery_method ?? '—'}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-neutral-400">Confidence:</span>
                      <span className="text-neutral-200">
                        {selectedRecording.confidence !== null
                          ? `${Math.round(selectedRecording.confidence * 100)}%`
                          : '—'}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              <button
                onClick={() => refetchRecordings()}
                className="self-start flex items-center gap-1.5 text-[11px] font-mono text-neutral-400 hover:text-yellow-400 transition-colors"
              >
                <RefreshCw className="w-3 h-3" />
                <span>Refresh recordings</span>
              </button>
            </div>
          )}
        </div>
      </div>

      <SubmitEvidenceModal
        caseId={caseId}
        isOpen={isSubmitModalOpen}
        onClose={() => setIsSubmitModalOpen(false)}
        onSuccess={(newEvid) => {
          setSelectedEvidenceId(newEvid.id);
          refetch();
        }}
      />
    </div>
  );
};

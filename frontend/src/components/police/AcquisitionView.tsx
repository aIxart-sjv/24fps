import React, { useState } from 'react';
import { useApiQuery } from '../../hooks/useApiQuery';
import { casesApi, evidenceApi, ApiError } from '../../lib/api';
import { LoadingState, ErrorState, EmptyState } from '../common/CommonUI';
import { HardDrive, Play, Loader2, Fingerprint } from 'lucide-react';

interface AcquisitionViewProps {
  caseId: number;
}

const AcquisitionForEvidence: React.FC<{ evidenceId: number; label: string }> = ({ evidenceId, label }) => {
  const [capturing, setCapturing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data: manifest, refetch } = useApiQuery(
    () => evidenceApi.getAcquisitionManifest(evidenceId).catch(() => null),
    [evidenceId]
  );
  const { data: device } = useApiQuery(() => evidenceApi.device(evidenceId).catch(() => null), [evidenceId]);

  const capture = async () => {
    setCapturing(true);
    setError(null);
    try {
      await evidenceApi.captureAcquisitionManifest(evidenceId);
      refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to capture acquisition metadata.');
    } finally {
      setCapturing(false);
    }
  };

  const readerMetadata = manifest?.reader_metadata as Record<string, unknown> | undefined;
  const embeddedHashes = manifest?.embedded_hash_values as Record<string, unknown> | undefined;

  return (
    <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-neutral-800">
        <div className="flex items-center gap-2">
          <HardDrive className="w-4 h-4 text-yellow-400" />
          <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200">{label}</h2>
        </div>
        <button
          onClick={capture}
          disabled={capturing}
          className="px-4 py-2 rounded bg-yellow-400 hover:bg-yellow-300 disabled:opacity-50 text-neutral-950 font-bold text-xs font-mono uppercase tracking-wider flex items-center gap-2 transition-all"
        >
          {capturing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
          <span>{capturing ? 'CAPTURING…' : manifest ? 'RE-CAPTURE MANIFEST' : 'CAPTURE ACQUISITION MANIFEST'}</span>
        </button>
      </div>

      {error && <ErrorState message={error} />}

      {device && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            ['Vendor', device.vendor ?? 'unknown'],
            ['Device Type', device.device_type ?? 'unknown'],
            ['Identification Method', device.identification_method ?? 'unknown'],
            ['Confidence', device.confidence !== null ? `${Math.round((device.confidence ?? 0) * 100)}%` : '—'],
          ].map(([k, v]) => (
            <div key={k} className="bg-neutral-900 border border-neutral-800 rounded p-3 text-left">
              <div className="text-[10px] font-mono text-neutral-400 uppercase">{k}</div>
              <div className="text-sm font-bold font-mono text-neutral-100 mt-1">{v}</div>
            </div>
          ))}
        </div>
      )}

      {!manifest ? (
        <EmptyState message="No acquisition manifest captured yet. This reads real reader metadata (size, format, sector size, embedded hashes) from the already-registered evidence file -- it never accesses a live hardware device." />
      ) : (
        <div className="bg-black border border-neutral-800 rounded p-4 font-mono text-xs text-neutral-300 space-y-1.5">
          <div className="text-neutral-400 flex items-center gap-2 pb-1 border-b border-neutral-850">
            <Fingerprint className="w-3.5 h-3.5 text-yellow-400" />
            <span>Acquisition manifest (reader_metadata)</span>
          </div>
          {readerMetadata &&
            Object.entries(readerMetadata).map(([key, value]) => (
              <div key={key} className="flex justify-between gap-4">
                <span className="text-neutral-400">{key}:</span>
                <span className="text-neutral-200 truncate">{String(value)}</span>
              </div>
            ))}
          {embeddedHashes && Object.keys(embeddedHashes).length > 0 && (
            <>
              <div className="text-neutral-400 pt-2 border-t border-neutral-850">embedded_hash_values:</div>
              {Object.entries(embeddedHashes).map(([key, value]) => (
                <div key={key} className="flex justify-between gap-4">
                  <span className="text-neutral-400">{key}:</span>
                  <span className="text-yellow-400/90 truncate">{String(value)}</span>
                </div>
              ))}
            </>
          )}
          <div className="text-neutral-400 pt-1">generated_at: {String(manifest.generated_at)}</div>
        </div>
      )}
    </div>
  );
};

export const AcquisitionView: React.FC<AcquisitionViewProps> = ({ caseId }) => {
  const { data: evidenceList, loading, error } = useApiQuery(() => casesApi.listEvidence(caseId), [caseId]);

  if (loading) return <LoadingState label="Loading evidence…" />;
  if (error) return <ErrorState message={error} />;
  if (!evidenceList || evidenceList.length === 0) {
    return <EmptyState message="No evidence registered for this case yet." />;
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {evidenceList.map((e) => (
        <AcquisitionForEvidence key={e.id} evidenceId={e.id} label={`${e.evidence_id} — ${e.source_type}`} />
      ))}
    </div>
  );
};


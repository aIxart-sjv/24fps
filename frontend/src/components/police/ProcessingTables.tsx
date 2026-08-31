import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { StatusBadge, LoadingState, ErrorState, EmptyState } from '../common/CommonUI';
import { useApiQuery } from '../../hooks/useApiQuery';
import { processingApi } from '../../lib/api';
import type { ProcessingRunResponse } from '../../lib/apiTypes';

const STAGE_TITLES: Record<string, string> = {
  integrity: 'Integrity verification',
  identification: 'Identification',
  enumeration: 'Enumeration',
  extraction: 'Extraction',
  recovery: 'Recovery',
  timestamp_normalization: 'Timestamp normalization',
  timeline: 'Timeline',
  ai: 'AI',
  correlation: 'Correlation',
  validation: 'Validation',
};

function stageTitle(jobType: string): string {
  return STAGE_TITLES[jobType] ?? jobType.replace(/_/g, ' ');
}

function formatTime(iso: string | null): string {
  return iso ? new Date(iso).toLocaleTimeString() : '—';
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '—';
  if (seconds < 1) return `${(seconds * 1000).toFixed(2)} ms`;
  return `${seconds.toFixed(3)} s`;
}

function formatBytes(size: number | null, unit: string | null): string {
  if (size === null) return '—';
  if (unit === 'bytes') {
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(2)} MB`;
  }
  return `${size} ${unit ?? ''}`.trim();
}

function formatRssKb(kb: number | null): string {
  if (kb === null) return '—';
  if (Math.abs(kb) < 1024) return `${kb} KB`;
  return `${(kb / 1024).toFixed(2)} MB`;
}

/**
 * Real, measured per-stage timing and resource usage for one processing
 * run (task: "Processing Performance ... from REAL runtime data"). Every
 * value is a genuine OS-level measurement (`time.perf_counter()`,
 * `resource.getrusage()`, `/proc/self/status`) -- never estimated, never
 * a placeholder. No accuracy/quality claim appears in this table.
 */
export const ProcessingPerformanceTable: React.FC<{ run: ProcessingRunResponse }> = ({ run }) => {
  return (
    <div className="bg-neutral-950 border border-neutral-800 rounded p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200">
          Processing Performance
        </h3>
        <div className="text-[11px] font-mono text-neutral-400">
          Total: <span className="text-neutral-200 font-bold">{formatDuration(run.total_duration_seconds)}</span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[11px] font-mono">
          <thead>
            <tr className="text-neutral-500 uppercase tracking-wider border-b border-neutral-800">
              <th className="text-left py-1.5 pr-3">Module</th>
              <th className="text-left py-1.5 pr-3">Start</th>
              <th className="text-left py-1.5 pr-3">End</th>
              <th className="text-left py-1.5 pr-3">Runtime</th>
              <th className="text-left py-1.5 pr-3">Input</th>
              <th className="text-left py-1.5 pr-3">CPU (u/s)</th>
              <th className="text-left py-1.5 pr-3">Peak RSS</th>
              <th className="text-left py-1.5 pr-3">RSS Δ</th>
              <th className="text-left py-1.5">Status</th>
            </tr>
          </thead>
          <tbody>
            {run.stages.map((stage) => (
              <tr key={stage.id} className="border-b border-neutral-900 last:border-0">
                <td className="py-1.5 pr-3 text-neutral-200 whitespace-nowrap">
                  {stageTitle(stage.job_type)}
                  {stage.evidence_id !== null && (
                    <span className="text-neutral-500"> · evidence #{stage.evidence_id}</span>
                  )}
                </td>
                <td className="py-1.5 pr-3 text-neutral-400 whitespace-nowrap">{formatTime(stage.started_at)}</td>
                <td className="py-1.5 pr-3 text-neutral-400 whitespace-nowrap">{formatTime(stage.completed_at)}</td>
                <td className="py-1.5 pr-3 text-neutral-200 whitespace-nowrap">
                  {formatDuration(stage.duration_seconds)}
                  {stage.high_resolution_timing === false && (
                    <span className="text-neutral-600" title="Wall-clock fallback, not high-resolution">
                      {' '}
                      (wall-clock)
                    </span>
                  )}
                </td>
                <td className="py-1.5 pr-3 text-neutral-400 whitespace-nowrap">
                  {stage.input_type ? (
                    <span title={stage.input_type}>{formatBytes(stage.input_size, stage.input_size_unit)}</span>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="py-1.5 pr-3 text-neutral-400 whitespace-nowrap">
                  {stage.cpu_user_seconds !== null
                    ? `${stage.cpu_user_seconds.toFixed(3)}/${(stage.cpu_system_seconds ?? 0).toFixed(3)}s`
                    : '—'}
                </td>
                <td className="py-1.5 pr-3 text-neutral-400 whitespace-nowrap" title="Process peak RSS since start, not stage-exclusive">
                  {formatRssKb(stage.peak_rss_kb)}
                </td>
                <td className="py-1.5 pr-3 text-neutral-400 whitespace-nowrap">
                  {stage.rss_delta_kb !== null ? formatRssKb(stage.rss_delta_kb) : '—'}
                </td>
                <td className="py-1.5">
                  <div className="flex items-center gap-1.5">
                    <StatusBadge status={stage.status} />
                    {stage.warnings && stage.warnings.length > 0 && (
                      <span title={stage.warnings.join('; ')}>
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[10px] font-mono text-neutral-600 mt-2">
        Runtime is high-resolution (monotonic <code>perf_counter</code>) unless marked "wall-clock". Peak RSS is the
        process's cumulative high-water mark since start, not this stage's own exclusive peak; RSS Δ isolates this
        stage's own memory growth where measurable. Hover the ⚠ icon for a stage's warnings.
      </p>
    </div>
  );
};

/**
 * Every measured accuracy/quality/validation signal from one processing
 * run -- deliberately separate from timing (`ProcessingPerformanceTable`)
 * and from raw output (`OutputParametersTable`). Precision/recall/F1
 * appear only where a real ground-truth basis exists; confidence is
 * always labeled as confidence, never accuracy; every row carries an
 * explicit status from a closed vocabulary instead of an implied
 * universal percentage.
 */
export const AccuracyValidationTable: React.FC<{ rootJobId: number }> = ({ rootJobId }) => {
  const { data, loading, error, refetch } = useApiQuery(
    () => processingApi.accuracy(rootJobId),
    [rootJobId]
  );

  return (
    <div className="bg-neutral-950 border border-neutral-800 rounded p-5">
      <h3 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 mb-3">
        Accuracy / Validation
      </h3>
      {loading && <LoadingState label="Loading accuracy/validation signals…" />}
      {!loading && error && <ErrorState message={error} onRetry={refetch} />}
      {!loading && !error && data && data.metrics.length === 0 && (
        <EmptyState message="This processing run produced no accuracy/validation signals (count-only stages have no correctness claim to make)." />
      )}
      {!loading && !error && data && data.metrics.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-[11px] font-mono">
            <thead>
              <tr className="text-neutral-500 uppercase tracking-wider border-b border-neutral-800">
                <th className="text-left py-1.5 pr-3">Module</th>
                <th className="text-left py-1.5 pr-3">Metric</th>
                <th className="text-left py-1.5 pr-3">Value</th>
                <th className="text-left py-1.5 pr-3">Status</th>
                <th className="text-left py-1.5 pr-3">Basis</th>
                <th className="text-left py-1.5">Notes</th>
              </tr>
            </thead>
            <tbody>
              {data.metrics.map((m, idx) => (
                <tr key={idx} className="border-b border-neutral-900 last:border-0 align-top">
                  <td className="py-1.5 pr-3 text-neutral-200 whitespace-nowrap">{m.module}</td>
                  <td className="py-1.5 pr-3 text-neutral-300 whitespace-nowrap">{m.metric}</td>
                  <td className="py-1.5 pr-3 text-neutral-100 font-bold">{m.value}</td>
                  <td className="py-1.5 pr-3">
                    <StatusBadge status={m.status} />
                  </td>
                  <td className="py-1.5 pr-3 text-neutral-500 max-w-xs">{m.basis}</td>
                  <td className="py-1.5 text-neutral-500 max-w-xs">{m.notes ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

/**
 * Every real, persisted output value produced by one processing run --
 * what was produced, never how well or how fast. Deliberately separate
 * from both timing and accuracy tables.
 */
export const OutputParametersTable: React.FC<{ rootJobId: number }> = ({ rootJobId }) => {
  const { data, loading, error, refetch } = useApiQuery(
    () => processingApi.outputs(rootJobId),
    [rootJobId]
  );

  return (
    <div className="bg-neutral-950 border border-neutral-800 rounded p-5">
      <h3 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 mb-3">
        Output Parameters
      </h3>
      {loading && <LoadingState label="Loading output parameters…" />}
      {!loading && error && <ErrorState message={error} onRetry={refetch} />}
      {!loading && !error && data && data.parameters.length === 0 && (
        <EmptyState message="This processing run produced no recorded output parameters." />
      )}
      {!loading && !error && data && data.parameters.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-[11px] font-mono">
            <thead>
              <tr className="text-neutral-500 uppercase tracking-wider border-b border-neutral-800">
                <th className="text-left py-1.5 pr-3">Module</th>
                <th className="text-left py-1.5 pr-3">Parameter</th>
                <th className="text-left py-1.5 pr-3">Value</th>
                <th className="text-left py-1.5 pr-3">Source</th>
                <th className="text-left py-1.5">Notes</th>
              </tr>
            </thead>
            <tbody>
              {data.parameters.map((p, idx) => (
                <tr key={idx} className="border-b border-neutral-900 last:border-0 align-top">
                  <td className="py-1.5 pr-3 text-neutral-200 whitespace-nowrap">{p.module}</td>
                  <td className="py-1.5 pr-3 text-neutral-300 whitespace-nowrap">{p.parameter}</td>
                  <td className="py-1.5 pr-3 text-neutral-100 font-bold break-all max-w-sm">{p.value}</td>
                  <td className="py-1.5 pr-3 text-neutral-500 whitespace-nowrap">{p.source}</td>
                  <td className="py-1.5 text-neutral-500 max-w-xs">{p.notes ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

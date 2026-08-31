import React from 'react';
import { useApiQuery } from '../../hooks/useApiQuery';
import { devicesApi } from '../../lib/api';
import { LoadingState, ErrorState, EmptyState } from '../common/CommonUI';
import { HardDrive } from 'lucide-react';

// Purely presentational: color-codes the real `support_level` integer
// `AdapterRegistry.support_matrix()` reports (0-4) -- never invents a
// "supported"/"unsupported" label of its own (Phase 24 task scope, "OEM
// Support": "Do not turn adapter existence into full support.").
const LEVEL_STYLES: Record<number, string> = {
  0: 'text-neutral-500 border-neutral-700 bg-neutral-900',
  1: 'text-amber-400 border-amber-500/30 bg-amber-950/20',
  2: 'text-amber-300 border-amber-500/40 bg-amber-950/30',
  3: 'text-cyan-300 border-cyan-500/30 bg-cyan-950/20',
  4: 'text-emerald-400 border-emerald-500/30 bg-emerald-950/20',
};

export const AdminOemSupport: React.FC = () => {
  const { data: matrix, loading, error, refetch } = useApiQuery(() => devicesApi.supportMatrix(), []);

  return (
    <div className="flex-1 flex flex-col gap-5 min-h-0 animate-in fade-in duration-200">
      <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-1">
        <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2">
          <HardDrive className="w-4 h-4 text-yellow-400" />
          <span>OEM / VENDOR SUPPORT MATRIX</span>
        </h2>
        <p className="text-[11px] font-mono text-neutral-400 leading-relaxed">
          Each vendor's real, declared support level -- not a "supported" checkbox. A registered adapter
          can range from research-only detection to fully validated recording extraction; the level and
          its evidence basis come directly from that adapter's own declaration, never inferred here.
        </p>
      </div>

      {loading && <LoadingState label="Loading support matrix…" />}
      {error && <ErrorState message={error} onRetry={refetch} />}
      {!loading && !error && (!matrix || matrix.length === 0) && (
        <EmptyState message="No vendor adapters are registered." />
      )}

      {matrix && matrix.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {matrix.map((v) => (
            <div key={`${v.vendor}-${v.model_pattern}`} className="bg-neutral-950 border border-neutral-800 rounded p-4 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-bold font-mono text-neutral-100">{v.vendor}</div>
                  <div className="text-[10px] font-mono text-neutral-500">
                    {v.model_scope === 'all' ? 'all models' : v.model_pattern}
                    {v.firmware_pattern ? ` · firmware ${v.firmware_pattern}` : ''}
                  </div>
                </div>
                <span
                  className={`shrink-0 px-2.5 py-1 rounded border text-[11px] font-mono font-bold uppercase ${
                    LEVEL_STYLES[v.support_level] ?? LEVEL_STYLES[0]
                  }`}
                >
                  LEVEL {v.support_level} — {v.support_level_label.replace(/_/g, ' ')}
                </span>
              </div>

              <div>
                <div className="text-[10px] font-mono text-neutral-500 uppercase mb-1">Evidence basis</div>
                {v.evidence_basis.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {v.evidence_basis.map((b) => (
                      <span key={b} className="text-[10px] font-mono text-neutral-300 bg-neutral-900 border border-neutral-800 rounded px-1.5 py-0.5">
                        {b.replace(/_/g, ' ')}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="text-[10px] font-mono text-neutral-600">NOT AVAILABLE</span>
                )}
              </div>

              <div>
                <div className="text-[10px] font-mono text-neutral-500 uppercase mb-1">Capabilities</div>
                {v.capabilities.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {v.capabilities.map((c) => (
                      <span key={c} className="text-[10px] font-mono text-emerald-300 bg-emerald-950/20 border border-emerald-500/20 rounded px-1.5 py-0.5">
                        {c.replace(/_/g, ' ')}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="text-[10px] font-mono text-neutral-600">NONE DECLARED</span>
                )}
              </div>

              {v.limitations.length > 0 && (
                <div>
                  <div className="text-[10px] font-mono text-neutral-500 uppercase mb-1">Limitations</div>
                  <ul className="text-[11px] text-neutral-400 font-sans leading-relaxed list-disc list-inside space-y-0.5">
                    {v.limitations.map((l, idx) => (
                      <li key={idx}>{l}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="text-[10px] font-mono text-neutral-600 pt-1 border-t border-neutral-800/80">
                adapter v{v.adapter_version}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

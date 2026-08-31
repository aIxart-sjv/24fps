import React from 'react';
import { useApiQuery } from '../../hooks/useApiQuery';
import { systemApi } from '../../lib/api';
import { LoadingState, ErrorState } from '../common/CommonUI';
import { Server, CheckCircle2, XCircle, Database } from 'lucide-react';

export const AdminServices: React.FC = () => {
  const { data: health, loading: healthLoading, error: healthError, refetch: refetchHealth } = useApiQuery(
    () => systemApi.health(),
    []
  );
  const { data: info } = useApiQuery(() => systemApi.info(), []);
  const { data: capabilities, loading, error } = useApiQuery(() => systemApi.capabilities(), []);

  return (
    <div className="flex-1 flex flex-col gap-5 min-h-0 animate-in fade-in duration-200">
      <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-neutral-800">
          <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2">
            <Database className="w-4 h-4 text-yellow-400" />
            <span>DATABASE / BACKEND HEALTH</span>
          </h2>
          <button onClick={refetchHealth} className="text-[11px] font-mono text-neutral-400 hover:text-yellow-400">
            Re-check
          </button>
        </div>
        {healthLoading && <LoadingState />}
        {healthError && <ErrorState message={healthError} />}
        {health && (
          <div className="flex items-center gap-4 text-xs font-mono">
            <span
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded border ${
                health.database_connected ? 'text-emerald-400 border-emerald-500/30 bg-emerald-950/20' : 'text-red-400 border-red-500/30 bg-red-950/20'
              }`}
            >
              {health.database_connected ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
              <span>{health.status.toUpperCase()}</span>
            </span>
            <span className="text-neutral-400">checked {new Date(health.timestamp).toLocaleString()}</span>
          </div>
        )}
        {info && (
          <div className="text-[11px] font-mono text-neutral-500">
            version {info.app_version} · env {info.app_env} · db {info.database_url_scheme}
          </div>
        )}
      </div>

      <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-3 flex-1 min-h-0 overflow-y-auto">
        <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2 pb-2 border-b border-neutral-800">
          <Server className="w-4 h-4 text-yellow-400" />
          <span>BACKEND SUBSYSTEMS</span>
        </h2>
        {loading && <LoadingState />}
        {error && <ErrorState message={error} />}
        {capabilities && (
          <div className="space-y-2">
            {capabilities.subsystems.map((s) => (
              <div key={s.name} className="bg-neutral-900 border border-neutral-800 rounded p-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-neutral-200">{s.name.replace(/_/g, ' ')}</span>
                  {s.implemented ? (
                    <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" /> IMPLEMENTED
                    </span>
                  ) : (
                    <span className="text-[10px] font-mono text-neutral-500 flex items-center gap-1">
                      <XCircle className="w-3 h-3" /> NOT IMPLEMENTED
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-neutral-400 font-sans mt-1 leading-relaxed">{s.notes}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

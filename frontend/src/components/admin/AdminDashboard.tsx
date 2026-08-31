import React from 'react';
import { useApiQuery } from '../../hooks/useApiQuery';
import { casesApi, usersApi, systemApi } from '../../lib/api';
import { LoadingState, ErrorState } from '../common/CommonUI';
import { FolderLock, Layers, Users, ArrowRight, CheckCircle2, XCircle, Activity } from 'lucide-react';
import { AdminSection } from '../../types';

interface AdminDashboardProps {
  onNavigateSection: (section: AdminSection) => void;
}

export const AdminDashboard: React.FC<AdminDashboardProps> = ({ onNavigateSection }) => {
  const { data: cases, loading: casesLoading, error: casesError } = useApiQuery(() => casesApi.list(), []);
  const { data: users } = useApiQuery(() => usersApi.list(), []);
  const { data: health } = useApiQuery(() => systemApi.health(), []);
  const { data: capabilities } = useApiQuery(() => systemApi.capabilities(), []);

  const { data: evidenceTotal } = useApiQuery(() => {
    if (!cases) return null;
    return Promise.all(cases.map((c) => casesApi.listEvidence(c.id))).then((lists) =>
      lists.reduce((sum, l) => sum + l.length, 0)
    );
  }, [cases]);

  if (casesLoading) return <LoadingState label="Loading platform overview…" />;
  if (casesError) return <ErrorState message={casesError} />;

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-neutral-800">
          <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2">
            <Activity className="w-4 h-4 text-yellow-400" />
            <span>BACKEND HEALTH</span>
          </h2>
          <span
            className={`flex items-center gap-1.5 text-[11px] font-mono px-2 py-0.5 rounded border ${
              health?.database_connected ? 'text-emerald-400 border-emerald-500/30 bg-emerald-950/20' : 'text-red-400 border-red-500/30 bg-red-950/20'
            }`}
          >
            {health?.database_connected ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
            <span>{health ? health.status.toUpperCase() : 'CHECKING…'}</span>
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {(capabilities?.subsystems ?? []).map((s) => (
            <div key={s.name} className="bg-neutral-900 border border-neutral-800 rounded p-2.5">
              <div className="flex items-center justify-between text-[10px] font-mono">
                <span className="text-neutral-300 truncate">{s.name.replace(/_/g, ' ')}</span>
                {s.implemented ? (
                  <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
                ) : (
                  <XCircle className="w-3 h-3 text-neutral-500 shrink-0" />
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div
          onClick={() => onNavigateSection('cases')}
          className="bg-neutral-950 border border-neutral-800 hover:border-yellow-400/60 rounded p-5 cursor-pointer transition-all group"
        >
          <div className="flex items-center justify-between text-neutral-400 text-xs font-mono">
            <span className="uppercase font-bold">CASES</span>
            <FolderLock className="w-4 h-4 text-yellow-400" />
          </div>
          <div className="text-3xl font-black font-mono text-neutral-100 mt-2">{cases?.length ?? 0}</div>
          <div className="text-xs text-neutral-400 mt-1 flex items-center justify-between font-mono">
            <span>Real case count</span>
            <span className="text-yellow-400 flex items-center gap-0.5 group-hover:translate-x-0.5 transition-transform">
              MANAGE <ArrowRight className="w-3 h-3" />
            </span>
          </div>
        </div>

        <div className="bg-neutral-950 border border-neutral-800 rounded p-5">
          <div className="flex items-center justify-between text-neutral-400 text-xs font-mono">
            <span className="uppercase font-bold">EVIDENCE ITEMS</span>
            <Layers className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-black font-mono text-neutral-100 mt-2">{evidenceTotal ?? '—'}</div>
          <div className="text-xs text-neutral-400 mt-1 font-mono">Across all cases</div>
        </div>

        <div
          onClick={() => onNavigateSection('users')}
          className="bg-neutral-950 border border-neutral-800 hover:border-yellow-400/60 rounded p-5 cursor-pointer transition-all group"
        >
          <div className="flex items-center justify-between text-neutral-400 text-xs font-mono">
            <span className="uppercase font-bold">USERS</span>
            <Users className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-3xl font-black font-mono text-neutral-100 mt-2">{users?.length ?? '—'}</div>
          <div className="text-xs text-neutral-400 mt-1 flex items-center justify-between font-mono">
            <span>Real account count</span>
            <span className="text-yellow-400 flex items-center gap-0.5 group-hover:translate-x-0.5 transition-transform">
              MANAGE <ArrowRight className="w-3 h-3" />
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { useApiQuery } from '../../hooks/useApiQuery';
import { casesApi } from '../../lib/api';
import { StatusBadge, LoadingState, ErrorState, EmptyState } from '../common/CommonUI';
import { FolderLock, Search, Bell, ArrowRight } from 'lucide-react';

interface PoliceDashboardProps {
  onSelectCase: (caseId: number) => void;
  onOpenEvidence?: (evidenceId: string, caseId: number) => void;
}

export const PoliceDashboard: React.FC<PoliceDashboardProps> = ({ onSelectCase }) => {
  const {
    currentUser,
    activeCaseId,
    notifications,
    unreadNotificationCount,
    markNotificationRead,
    setActiveCaseTab,
    requestSeek,
  } = useApp();
  const [searchQuery, setSearchQuery] = useState('');

  const { data: cases, loading, error, refetch } = useApiQuery(() => casesApi.list(), []);

  const filteredCases = (cases ?? []).filter(
    (c) =>
      c.case_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-neutral-900 dark:bg-neutral-950 text-neutral-100 p-4 sm:p-6 overflow-y-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 mb-6 border-b border-neutral-800">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold font-sans tracking-tight text-neutral-100">
            INVESTIGATION WORKSPACE
          </h1>
          <p className="text-xs text-neutral-400 font-mono mt-1">
            Signed in as {currentUser?.display_name} · SURVEILLANCE EVIDENCE FORENSICS
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono">
          <div className="bg-neutral-950 border border-neutral-800 px-3 py-1.5 rounded flex items-center gap-2">
            <FolderLock className="w-4 h-4 text-yellow-400" />
            <span className="text-neutral-400">CASES:</span>
            <span className="font-bold text-neutral-100">{cases?.length ?? '—'}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 min-h-0">
        <div className="lg:col-span-5 flex flex-col bg-neutral-950 border border-neutral-800 rounded p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-300 flex items-center gap-2">
              <FolderLock className="w-4 h-4 text-yellow-400" />
              <span>CASES</span>
            </h2>
            <span className="text-[11px] font-mono text-neutral-400">{filteredCases.length} SHOWN</span>
          </div>

          <div className="relative mb-3">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-neutral-400 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search cases..."
              className="w-full bg-neutral-900 border border-neutral-800 rounded pl-9 pr-3 py-2 text-xs font-mono text-neutral-200 placeholder-neutral-400 focus:outline-none focus:border-yellow-400 focus:ring-1 focus:ring-yellow-400"
            />
          </div>

          <div className="flex-1 overflow-y-auto space-y-2.5 pr-1 min-h-[300px] max-h-[560px]">
            {loading && <LoadingState label="Loading cases…" />}
            {error && <ErrorState message={error} onRetry={refetch} />}
            {!loading && !error && filteredCases.length === 0 && (
              <EmptyState message="No cases found. Create one from the admin console or backend API." />
            )}
            {!loading &&
              !error &&
              filteredCases.map((caseItem) => {
                const isActive = caseItem.id === activeCaseId;
                return (
                  <div
                    key={caseItem.id}
                    onClick={() => onSelectCase(caseItem.id)}
                    className={`p-3.5 rounded border transition-all cursor-pointer group text-left border-l-[3px] ${
                      isActive
                        ? 'border-neutral-800 border-l-yellow-400 bg-neutral-900'
                        : 'border-neutral-800/80 border-l-transparent bg-neutral-900/40 hover:border-neutral-700 hover:bg-neutral-900/80'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <span className="font-mono text-xs font-bold text-yellow-400 group-hover:text-yellow-300">
                        {caseItem.case_id}
                      </span>
                      <StatusBadge status={caseItem.status} />
                    </div>

                    <h3 className="text-sm font-semibold text-neutral-200 group-hover:text-white font-sans line-clamp-1">
                      {caseItem.name}
                    </h3>

                    {caseItem.description && (
                      <p className="text-xs text-neutral-400 mt-1 line-clamp-2 leading-relaxed">
                        {caseItem.description}
                      </p>
                    )}

                    <div className="flex items-center justify-between pt-3 mt-2.5 border-t border-neutral-800/60 text-[11px] font-mono text-neutral-400">
                      <span>{caseItem.examiner || 'No examiner assigned'}</span>
                      <span className="flex items-center gap-1 text-yellow-400 font-sans font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                        OPEN <ArrowRight className="w-3 h-3" />
                      </span>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>

        <div className="lg:col-span-7 flex flex-col bg-neutral-950 border border-neutral-800 rounded p-4 sm:p-5">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-neutral-800">
            <div className="flex items-center gap-2">
              <Bell className="w-4 h-4 text-yellow-400" />
              <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200">
                FINDINGS REQUIRING ATTENTION
              </h2>
            </div>
            <span className="text-[11px] font-mono text-neutral-400">
              {unreadNotificationCount} unread
            </span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-3 pr-1">
            {notifications.length === 0 ? (
              <EmptyState message="No findings have been generated yet. Run automatic processing on a case to see results here." />
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  onClick={() => {
                    if (n.read_at === null) markNotificationRead(n.id);
                    onSelectCase(n.finding.case_id);
                    // Jump straight to the relevant recording when this
                    // finding resolves to one (Phase 24 task scope,
                    // "Officer Notification Flow") -- fall back to the
                    // findings tab, honestly, when no recording/timestamp
                    // is resolvable for this finding.
                    if (n.finding.resolved_recording_id !== null) {
                      requestSeek(n.finding.resolved_recording_id, 0);
                      setActiveCaseTab('evidence');
                    } else {
                      setActiveCaseTab('findings');
                    }
                  }}
                  className={`p-3.5 rounded border border-neutral-800 hover:bg-neutral-900 hover:border-neutral-700 transition-all cursor-pointer group ${
                    n.read_at === null ? 'bg-neutral-900/80' : 'bg-neutral-900/30 opacity-70'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <StatusBadge status={n.finding.severity} />
                    <span className="text-[11px] font-mono text-neutral-400 group-hover:text-yellow-400 transition-colors">
                      {new Date(n.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="text-xs font-semibold text-neutral-100 font-sans">
                    {n.finding.title}
                  </div>
                  <div className="text-xs text-neutral-400 mt-0.5 leading-relaxed line-clamp-2">
                    {n.finding.description}
                  </div>
                  {n.finding.resolved_recording_id !== null && (
                    <div className="text-[10px] font-mono text-yellow-400/80 mt-1.5 flex items-center gap-1">
                      <ArrowRight className="w-3 h-3" />
                      <span>
                        VIEW RECORDING
                        {n.finding.resolved_timestamp
                          ? ` · ${new Date(n.finding.resolved_timestamp).toLocaleString()}`
                          : ''}
                      </span>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { useApiQuery } from '../../hooks/useApiQuery';
import { casesApi } from '../../lib/api';
import { StatusBadge, LoadingState, ErrorState } from '../common/CommonUI';
import { FolderLock, Search, Clock, ChevronRight, X } from 'lucide-react';

interface PoliceCaseSidebarProps {
  onSelectCase: (caseId: number) => void;
  onReturnToDashboard: () => void;
  onCloseMobile?: () => void;
}

export const PoliceCaseSidebar: React.FC<PoliceCaseSidebarProps> = ({
  onSelectCase,
  onReturnToDashboard,
  onCloseMobile,
}) => {
  const { activeCaseId, isSidebarOpen, toggleSidebar } = useApp();
  const [searchQuery, setSearchQuery] = useState('');

  const { data: cases, loading, error } = useApiQuery(() => casesApi.list(), []);

  const filteredCases = (cases ?? []).filter(
    (c) =>
      c.case_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (!isSidebarOpen) return null;

  return (
    <aside className="w-72 sm:w-80 shrink-0 h-full border-r border-neutral-800 bg-neutral-950 flex flex-col justify-between text-neutral-100 select-none z-30 transition-all duration-200">
      <div className="p-3.5 border-b border-neutral-800">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-xs font-mono font-bold text-neutral-200">
            <FolderLock className="w-4 h-4 text-yellow-400" />
            <span>CASES</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-[11px] font-mono text-neutral-400">{cases?.length ?? '—'}</span>
            <button onClick={toggleSidebar} className="lg:hidden p-1 text-neutral-400 hover:text-neutral-200" title="Close sidebar">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2 text-neutral-400 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search cases..."
            className="w-full bg-neutral-900 border border-neutral-800 rounded pl-8 pr-2.5 py-1.5 text-xs font-mono text-neutral-200 placeholder-neutral-400 focus:outline-none focus:border-yellow-400 focus:ring-1 focus:ring-yellow-400"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto divide-y divide-neutral-900/60">
        {loading && <LoadingState label="Loading…" />}
        {error && <ErrorState message={error} />}
        {!loading &&
          !error &&
          filteredCases.map((caseItem) => {
            const isSelected = caseItem.id === activeCaseId;
            return (
              <button
                key={caseItem.id}
                onClick={() => {
                  onSelectCase(caseItem.id);
                  onCloseMobile?.();
                }}
                className={`w-full text-left p-3 transition-colors flex flex-col gap-1 relative border-l-[3px] ${
                  isSelected ? 'bg-neutral-900 border-l-yellow-400' : 'bg-transparent hover:bg-neutral-900/60 border-l-transparent'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`font-mono text-xs font-bold ${isSelected ? 'text-yellow-400' : 'text-neutral-300'}`}>
                    {caseItem.case_id}
                  </span>
                  <StatusBadge status={caseItem.status} />
                </div>
                <div className="text-xs font-medium text-neutral-200 truncate font-sans">{caseItem.name}</div>
              </button>
            );
          })}
      </div>

      <div className="p-3 border-t border-neutral-800 bg-neutral-950">
        <button
          onClick={() => {
            onReturnToDashboard();
            onCloseMobile?.();
          }}
          className="w-full py-2.5 px-3 rounded bg-neutral-900 hover:bg-neutral-850 border border-neutral-800 hover:border-yellow-400/60 text-neutral-200 hover:text-yellow-400 text-xs font-mono font-bold flex items-center justify-between transition-colors group"
        >
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-yellow-400" />
            <span>DASHBOARD</span>
          </div>
          <ChevronRight className="w-4 h-4 text-neutral-400 group-hover:translate-x-0.5 group-hover:text-yellow-400 transition-transform" />
        </button>
      </div>
    </aside>
  );
};

import React from 'react';
import { useApp } from '../../context/AppContext';
import { useApiQuery } from '../../hooks/useApiQuery';
import { casesApi } from '../../lib/api';
import { CaseTab } from '../../types';
import { CaseOverview } from './CaseOverview';
import { EvidenceView } from './EvidenceView';
import { AcquisitionView } from './AcquisitionView';
import { RecoveryView } from './RecoveryView';
import { TimelineView } from './TimelineView';
import { AIAnalysisView } from './AIAnalysisView';
import { IntegrityView } from './IntegrityView';
import { CustodyView } from './CustodyView';
import { FindingsView } from './FindingsView';
import { ReportView } from './ReportView';
import { LoadingState, ErrorState, AccessDeniedState, StatusBadge } from '../common/CommonUI';
import {
  Layers,
  HardDrive,
  Cpu,
  Clock,
  Sparkles,
  ShieldCheck,
  FileText,
  Info,
  QrCode,
  Bell,
} from 'lucide-react';

export const CaseWorkspace: React.FC = () => {
  const { activeCaseId, activeCaseTab, setActiveCaseTab } = useApp();

  const { data: activeCase, loading, error, errorStatus, refetch } = useApiQuery(
    () => (activeCaseId !== null ? casesApi.get(activeCaseId) : null),
    [activeCaseId]
  );

  const tabs: Array<{ id: CaseTab; label: string; icon: React.ReactNode }> = [
    { id: 'overview', label: 'OVERVIEW', icon: <Info className="w-3.5 h-3.5" /> },
    { id: 'evidence', label: 'EVIDENCE', icon: <Layers className="w-3.5 h-3.5" /> },
    { id: 'acquisition', label: 'ACQUISITION', icon: <HardDrive className="w-3.5 h-3.5" /> },
    { id: 'recovery', label: 'RECOVERY', icon: <Cpu className="w-3.5 h-3.5" /> },
    { id: 'timeline', label: 'TIMELINE', icon: <Clock className="w-3.5 h-3.5" /> },
    { id: 'ai', label: 'AI', icon: <Sparkles className="w-3.5 h-3.5" /> },
    { id: 'integrity', label: 'INTEGRITY', icon: <ShieldCheck className="w-3.5 h-3.5" /> },
    { id: 'custody', label: 'CUSTODY', icon: <QrCode className="w-3.5 h-3.5" /> },
    { id: 'findings', label: 'FINDINGS', icon: <Bell className="w-3.5 h-3.5" /> },
    { id: 'report', label: 'REPORT', icon: <FileText className="w-3.5 h-3.5" /> },
  ];

  if (activeCaseId === null) {
    return <ErrorState message="No case selected." />;
  }
  if (loading) return <LoadingState label="Loading case…" />;
  if (errorStatus === 403) return <AccessDeniedState message={error ?? undefined} />;
  if (error || !activeCase) return <ErrorState message={error ?? 'Case not found.'} onRetry={refetch} />;

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-neutral-900 dark:bg-neutral-900 text-neutral-100 p-3 sm:p-5 overflow-y-auto">
      <div className="bg-neutral-950 border border-neutral-800 rounded mb-5 p-3.5 sm:p-4 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm font-bold text-yellow-400 bg-neutral-900 px-2 py-0.5 rounded border border-neutral-800">
              {activeCase.case_id}
            </span>
            <h1 className="text-base sm:text-lg font-bold text-neutral-100 font-sans truncate">
              {activeCase.name}
            </h1>
          </div>
          <StatusBadge status={activeCase.status} />
        </div>

        <nav
          aria-label="Case sections"
          className="flex items-center gap-1 sm:gap-2 overflow-x-auto pt-2 border-t border-neutral-850 pb-0.5"
        >
          {tabs.map((tab) => {
            const isActive = activeCaseTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveCaseTab(tab.id)}
                className={`px-3 py-1.5 rounded text-xs font-mono font-bold uppercase tracking-wider flex items-center gap-1.5 shrink-0 transition-all cursor-pointer ${
                  isActive ? 'bg-yellow-400 text-black shadow-sm' : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900'
                }`}
              >
                {tab.icon}
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      <div className="flex-1 flex flex-col min-h-0">
        {activeCaseTab === 'overview' && (
          <CaseOverview caseData={activeCase} onNavigateTab={(tab) => setActiveCaseTab(tab)} />
        )}
        {activeCaseTab === 'evidence' && <EvidenceView caseId={activeCase.id} />}
        {activeCaseTab === 'acquisition' && <AcquisitionView caseId={activeCase.id} />}
        {activeCaseTab === 'recovery' && <RecoveryView caseId={activeCase.id} />}
        {activeCaseTab === 'timeline' && <TimelineView caseId={activeCase.id} />}
        {activeCaseTab === 'ai' && <AIAnalysisView caseId={activeCase.id} />}
        {activeCaseTab === 'integrity' && <IntegrityView caseId={activeCase.id} />}
        {activeCaseTab === 'custody' && <CustodyView caseId={activeCase.id} />}
        {activeCaseTab === 'findings' && <FindingsView caseId={activeCase.id} />}
        {activeCaseTab === 'report' && <ReportView caseId={activeCase.id} caseData={activeCase} />}
      </div>
    </div>
  );
};

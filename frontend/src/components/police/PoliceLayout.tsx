import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { TopBar } from '../common/TopBar';
import { PoliceDashboard } from './PoliceDashboard';
import { PoliceCaseSidebar } from './PoliceCaseSidebar';
import { CaseWorkspace } from './CaseWorkspace';

interface PoliceLayoutProps {
  onNavigate: (path: string) => void;
}

export const PoliceLayout: React.FC<PoliceLayoutProps> = ({ onNavigate }) => {
  const { activeCaseId, setActiveCaseId, setActiveCaseTab } = useApp();

  const [inCaseWorkspace, setInCaseWorkspace] = useState<boolean>(false);

  const handleSelectCase = (caseId: number) => {
    setActiveCaseId(caseId);
    setActiveCaseTab('overview');
    setInCaseWorkspace(true);
  };

  const handleReturnToDashboard = () => {
    setInCaseWorkspace(false);
  };

  return (
    <div className="min-h-screen w-full flex flex-col bg-neutral-900 text-neutral-100 font-sans">
      <TopBar onNavigate={onNavigate} />

      <div className="flex-1 flex min-h-0 overflow-hidden relative">
        {inCaseWorkspace && activeCaseId !== null ? (
          <>
            <PoliceCaseSidebar onSelectCase={handleSelectCase} onReturnToDashboard={handleReturnToDashboard} />
            <main className="flex-1 flex flex-col min-h-0 overflow-hidden bg-neutral-900">
              <CaseWorkspace />
            </main>
          </>
        ) : (
          <main className="flex-1 flex flex-col min-h-0 overflow-hidden bg-neutral-900">
            <PoliceDashboard onSelectCase={handleSelectCase} />
          </main>
        )}
      </div>
    </div>
  );
};

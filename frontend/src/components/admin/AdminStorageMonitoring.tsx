import React from 'react';
import { UnavailableState } from '../common/CommonUI';
import { HardDrive } from 'lucide-react';

export const AdminStorageMonitoring: React.FC = () => {
  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="bg-neutral-950 border border-neutral-800 rounded p-5">
        <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2 pb-2 mb-3 border-b border-neutral-800">
          <HardDrive className="w-4 h-4 text-yellow-400" />
          <span>STORAGE MONITORING</span>
        </h2>
        <UnavailableState
          title="Disk capacity / WORM volume monitoring"
          reason="The backend has no disk-usage or storage-capacity reporting endpoint -- EVIDENCE_ROOT/ARTIFACT_ROOT/REPORT_ROOT are plain configured filesystem directories with no capacity API. Per-artifact size is real and available (Artifact.size_bytes on every derived artifact), but there is no aggregate volume/capacity dashboard to surface here honestly."
        />
      </div>
    </div>
  );
};

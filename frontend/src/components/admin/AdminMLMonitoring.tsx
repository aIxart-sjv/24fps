import React from 'react';
import { UnavailableState } from '../common/CommonUI';
import { Sparkles } from 'lucide-react';

export const AdminMLMonitoring: React.FC = () => {
  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="bg-neutral-950 border border-neutral-800 rounded p-5">
        <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2 pb-2 mb-3 border-b border-neutral-800">
          <Sparkles className="w-4 h-4 text-yellow-400" />
          <span>ML PIPELINE MONITORING</span>
        </h2>
        <UnavailableState
          title="Cross-case ML job queue/monitoring"
          reason="The backend has no endpoint that lists AI jobs across every case, only per-case results (GET /cases/{id}/ai-results) and per-job status (GET /jobs/{id}). AI analysis itself is real (Phase 13 object/face/motion detection + tracking) -- view real results per case under that case's AI tab. A live inference queue with GPU utilization telemetry does not exist in this backend."
        />
      </div>
    </div>
  );
};

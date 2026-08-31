import React from 'react';
import { UnavailableState } from '../common/CommonUI';
import { ShieldAlert } from 'lucide-react';

export const AdminSecurityEvents: React.FC = () => {
  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="bg-neutral-950 border border-neutral-800 rounded p-5">
        <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2 pb-2 mb-3 border-b border-neutral-800">
          <ShieldAlert className="w-4 h-4 text-red-500" />
          <span>SECURITY EVENTS</span>
        </h2>
        <UnavailableState
          title="Security event log"
          reason="The backend does not currently record a security-event stream (failed logins, access-denied attempts, hash-mismatch alerts as discrete events). Authentication failures are rejected with a 401 but not logged as a queryable event; hash mismatches are surfaced instead as INTEGRITY_MISMATCH findings on the relevant case (see the case Findings tab)."
        />
      </div>
    </div>
  );
};

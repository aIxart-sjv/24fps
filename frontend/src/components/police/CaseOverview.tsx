import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { useApiQuery } from '../../hooks/useApiQuery';
import { casesApi } from '../../lib/api';
import { StatusBadge, ErrorState } from '../common/CommonUI';
import { ProcessingPerformanceTable, AccuracyValidationTable, OutputParametersTable } from './ProcessingTables';
import { ApiError } from '../../lib/api';
import {
  ArrowRight,
  ShieldCheck,
  Video,
  HardDrive,
  Cpu,
  FileText,
  Clock,
  PlayCircle,
  Loader2,
} from 'lucide-react';
import { CaseTab } from '../../types';
import type { CaseResponse } from '../../lib/apiTypes';

interface CaseOverviewProps {
  caseData: CaseResponse;
  onNavigateTab: (tab: CaseTab) => void;
}

export const CaseOverview: React.FC<CaseOverviewProps> = ({ caseData, onNavigateTab }) => {
  const { addToast } = useApp();
  const [processing, setProcessing] = useState(false);
  const [processError, setProcessError] = useState<string | null>(null);

  const { data: evidenceList } = useApiQuery(() => casesApi.listEvidence(caseData.id), [caseData.id]);
  const { data: findings, refetch: refetchFindings } = useApiQuery(
    () => casesApi.findings(caseData.id),
    [caseData.id]
  );
  const { data: runs, refetch: refetchRuns } = useApiQuery(
    () => casesApi.processingRuns(caseData.id),
    [caseData.id]
  );
  const { data: auditChain } = useApiQuery(() => casesApi.verifyAuditChain(caseData.id), [caseData.id]);
  const { data: reports } = useApiQuery(() => casesApi.reports(caseData.id), [caseData.id]);
  const { data: timelineEvents } = useApiQuery(() => casesApi.timeline(caseData.id), [caseData.id]);

  const latestRun = runs && runs.length > 0 ? runs[0] : null;
  const unresolvedHighSeverity =
    findings?.filter((f) => (f.severity === 'high' || f.severity === 'critical') && f.status === 'open').length ?? 0;

  // Real per-stage status from the latest processing run -- never a
  // constant label regardless of what actually happened (Phase 24 task
  // scope, "Case Overview").
  const recoveryStage = latestRun?.stages.find((s) => s.job_type === 'recovery');
  const aiStage = latestRun?.stages.find((s) => s.job_type === 'ai');

  const recoveryStatus = !latestRun
    ? 'not yet run'
    : recoveryStage
      ? recoveryStage.status.replace(/_/g, ' ')
      : 'no stage recorded';

  const aiStatus = aiStage
    ? `${aiStage.status.replace(/_/g, ' ')} (assistive only)`
    : 'not run (opt-in)';

  const reportStatus =
    reports === null || reports === undefined
      ? '—'
      : reports.length > 0
        ? `${reports.length} report(s) generated`
        : 'none generated yet';

  const unresolvedTimestamps =
    timelineEvents?.filter((e) => e.timestamp_status !== 'verified').length ?? null;

  const handleProcess = async () => {
    setProcessing(true);
    setProcessError(null);
    try {
      const result = await casesApi.process(caseData.id);
      addToast({
        title: 'Automatic processing complete',
        description: `${result.new_finding_ids.length} finding(s) generated; ${result.stages_total} pipeline stage(s) ran.`,
        type: result.root_job.status === 'failed' ? 'error' : 'success',
      });
      refetchFindings();
      refetchRuns();
    } catch (err) {
      setProcessError(err instanceof ApiError ? err.message : 'Processing failed.');
    } finally {
      setProcessing(false);
    }
  };

  const workflowSteps: Array<{
    id: CaseTab;
    label: string;
    description: string;
    icon: React.ReactNode;
    status: string;
  }> = [
    {
      id: 'evidence',
      label: 'EVIDENCE',
      description: 'Register, upload, and inspect source evidence items.',
      icon: <HardDrive className="w-5 h-5 text-yellow-400" />,
      status: `${evidenceList?.length ?? 0} item(s)`,
    },
    {
      id: 'recovery',
      label: 'RECOVERY',
      description: 'Layered recovery of damaged/partial recordings.',
      icon: <Cpu className="w-5 h-5 text-emerald-400" />,
      status: recoveryStatus,
    },
    {
      id: 'ai',
      label: 'ANALYSIS',
      description: 'Object/face/motion detection and attribute-based search.',
      icon: <Video className="w-5 h-5 text-cyan-400" />,
      status: aiStatus,
    },
    {
      id: 'integrity',
      label: 'INTEGRITY',
      description: 'SHA-256 evidence hashing and hash-linked audit chain.',
      icon: <ShieldCheck className="w-5 h-5 text-emerald-400" />,
      status: auditChain ? (auditChain.valid ? 'chain valid' : 'chain INVALID') : '—',
    },
    {
      id: 'report',
      label: 'REPORT',
      description: 'Standardized JSON/PDF forensic report generation.',
      icon: <FileText className="w-5 h-5 text-amber-400" />,
      status: reportStatus,
    },
  ];

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="bg-neutral-950 border border-neutral-800 rounded p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-neutral-800">
          <div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-lg font-bold text-yellow-400">{caseData.case_id}</span>
              <StatusBadge status={caseData.status} />
            </div>
            <h2 className="text-xl font-bold text-neutral-100 font-sans mt-1.5">{caseData.name}</h2>
            <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-neutral-400 mt-2">
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-neutral-400" />
                CREATED: {new Date(caseData.created_at).toLocaleString()}
              </span>
              {caseData.examiner && (
                <>
                  <span>•</span>
                  <span>EXAMINER: {caseData.examiner}</span>
                </>
              )}
            </div>
          </div>

          <button
            onClick={handleProcess}
            disabled={processing}
            className="px-5 py-2.5 rounded bg-yellow-400 hover:bg-yellow-300 disabled:opacity-50 text-neutral-950 font-bold text-xs font-mono uppercase tracking-wider flex items-center gap-2 transition-all active:scale-98 shadow-md cursor-pointer shrink-0"
          >
            {processing ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlayCircle className="w-4 h-4" />}
            <span>{processing ? 'PROCESSING…' : 'RUN AUTOMATIC PROCESSING'}</span>
          </button>
        </div>

        {processError && <div className="mt-3"><ErrorState message={processError} /></div>}

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mt-4 pt-1">
          <div className="bg-neutral-900 border border-neutral-800 rounded p-3 text-left">
            <div className="text-[10px] font-mono text-neutral-400 uppercase tracking-wider">EVIDENCE ITEMS</div>
            <div className="text-sm font-bold font-mono text-neutral-100 mt-1">{evidenceList?.length ?? '—'}</div>
          </div>
          <div className="bg-neutral-900 border border-neutral-800 rounded p-3 text-left">
            <div className="text-[10px] font-mono text-neutral-400 uppercase tracking-wider">FINDINGS</div>
            <div className="text-sm font-bold font-mono text-neutral-100 mt-1">{findings?.length ?? '—'}</div>
          </div>
          <div className="bg-neutral-900 border border-neutral-800 rounded p-3 text-left">
            <div className="text-[10px] font-mono text-neutral-400 uppercase tracking-wider">HIGH/CRITICAL OPEN</div>
            <div className={`text-sm font-bold font-mono mt-1 ${unresolvedHighSeverity > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
              {unresolvedHighSeverity}
            </div>
          </div>
          <div className="bg-neutral-900 border border-neutral-800 rounded p-3 text-left">
            <div className="text-[10px] font-mono text-neutral-400 uppercase tracking-wider">AUDIT CHAIN</div>
            <div className={`text-sm font-bold font-mono mt-1 ${auditChain?.valid ? 'text-emerald-400' : 'text-red-400'}`}>
              {auditChain ? (auditChain.valid ? 'VALID' : 'INVALID') : '—'}
            </div>
          </div>
          <div className="bg-neutral-900 border border-neutral-800 rounded p-3 text-left">
            <div className="text-[10px] font-mono text-neutral-400 uppercase tracking-wider">TIMELINE</div>
            <div
              className={`text-sm font-bold font-mono mt-1 ${
                unresolvedTimestamps === null ? 'text-neutral-100' : unresolvedTimestamps > 0 ? 'text-amber-400' : 'text-emerald-400'
              }`}
            >
              {unresolvedTimestamps === null
                ? '—'
                : unresolvedTimestamps > 0
                  ? `${unresolvedTimestamps} unresolved`
                  : 'all verified'}
            </div>
          </div>
        </div>

        {caseData.description && (
          <div className="mt-4 pt-3 border-t border-neutral-800/80 text-xs text-neutral-300 leading-relaxed font-sans">
            <span className="font-mono text-neutral-400 font-bold uppercase mr-2">Case Summary:</span>
            {caseData.description}
          </div>
        )}
      </div>

      <div className="bg-neutral-950 border border-neutral-800 rounded p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200">
              FORENSIC EVIDENCE WORKFLOW
            </h3>
            <p className="text-xs text-neutral-400 font-mono mt-0.5">
              EVIDENCE → RECOVER → ANALYZE → VERIFY → REPORT
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          {workflowSteps.map((step, idx) => (
            <div
              key={step.id}
              onClick={() => onNavigateTab(step.id)}
              className="bg-neutral-900 border border-neutral-800 hover:border-yellow-400/80 rounded p-3.5 flex flex-col justify-between cursor-pointer group transition-all"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="p-2 rounded bg-neutral-950 border border-neutral-800 group-hover:border-neutral-700">
                    {step.icon}
                  </div>
                  <span className="text-[10px] font-mono font-bold text-yellow-400/80 bg-neutral-950 px-1.5 py-0.5 rounded border border-neutral-800">
                    0{idx + 1}
                  </span>
                </div>
                <div className="text-xs font-bold font-mono text-neutral-100 group-hover:text-yellow-400 transition-colors">
                  {step.label}
                </div>
                <p className="text-[11px] text-neutral-400 mt-1 line-clamp-3 leading-snug">{step.description}</p>
              </div>
              <div className="mt-3 pt-2.5 border-t border-neutral-800/80 flex items-center justify-between text-[10px] font-mono">
                <span className="text-neutral-400">{step.status}</span>
                <span className="text-yellow-400 flex items-center gap-0.5 group-hover:translate-x-0.5 transition-transform">
                  VIEW <ArrowRight className="w-2.5 h-2.5" />
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {latestRun && (
        <>
          <ProcessingPerformanceTable run={latestRun} />
          <AccuracyValidationTable rootJobId={latestRun.root_job.id} />
          <OutputParametersTable rootJobId={latestRun.root_job.id} />
        </>
      )}
    </div>
  );
};

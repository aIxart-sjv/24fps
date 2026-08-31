import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { useApiQuery } from '../../hooks/useApiQuery';
import { casesApi, evidenceApi, usersApi, custodyApi, ApiError } from '../../lib/api';
import { LoadingState, ErrorState, EmptyState, StatusBadge } from '../common/CommonUI';
import { QrCode, Send, CheckCircle2, XCircle, Loader2, History } from 'lucide-react';
import type { EvidenceResponse } from '../../lib/apiTypes';

interface CustodyViewProps {
  caseId: number;
}

const EvidenceCustodyPanel: React.FC<{ evidence: EvidenceResponse }> = ({ evidence }) => {
  const { addToast } = useApp();
  const [recipientId, setRecipientId] = useState<number | ''>('');
  const [location, setLocation] = useState('');
  const [qr, setQr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tokenInput, setTokenInput] = useState('');

  const { data: users } = useApiQuery(() => usersApi.list(), []);
  const { data: current, refetch: refetchCurrent } = useApiQuery(
    () => evidenceApi.currentCustodian(evidence.id),
    [evidence.id]
  );
  const { data: history, refetch: refetchHistory } = useApiQuery(
    () => evidenceApi.custodyHistory(evidence.id),
    [evidence.id]
  );

  const refreshAll = () => {
    refetchCurrent();
    refetchHistory();
  };

  const initiate = async () => {
    if (!recipientId) return;
    setBusy(true);
    setError(null);
    try {
      const result = await evidenceApi.initiateHandoff(evidence.id, Number(recipientId), location || undefined);
      setQr(result.qr_code_png_base64);
      addToast({ title: 'Handoff initiated', description: `Transfer #${result.transfer.id} pending acceptance.`, type: 'success' });
      refreshAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not initiate handoff.');
    } finally {
      setBusy(false);
    }
  };

  const intake = async () => {
    if (!recipientId) return;
    setBusy(true);
    setError(null);
    try {
      await evidenceApi.recordIntake(evidence.id, Number(recipientId), location || undefined);
      refreshAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not record intake.');
    } finally {
      setBusy(false);
    }
  };

  const acceptToken = async () => {
    if (!tokenInput.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await custodyApi.acceptByToken(tokenInput.trim());
      setTokenInput('');
      refreshAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not accept handoff.');
    } finally {
      setBusy(false);
    }
  };

  const rejectToken = async () => {
    if (!tokenInput.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await custodyApi.rejectByToken(tokenInput.trim());
      setTokenInput('');
      refreshAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reject handoff.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-4">
      <div className="flex items-center justify-between pb-2 border-b border-neutral-800">
        <span className="font-mono text-sm font-bold text-yellow-400">{evidence.evidence_id}</span>
        {current ? (
          <span className="text-[11px] font-mono text-emerald-400">
            Current custodian: {current.receiving_user_display_name}
          </span>
        ) : (
          <span className="text-[11px] font-mono text-neutral-500">No recorded custody yet</span>
        )}
      </div>

      {error && <ErrorState message={error} />}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-2">
          <div className="text-[10px] font-mono uppercase text-neutral-400 font-bold">
            {current ? 'INITIATE QR HANDOFF' : 'RECORD INITIAL INTAKE'}
          </div>
          <select
            value={recipientId}
            onChange={(e) => setRecipientId(e.target.value ? Number(e.target.value) : '')}
            className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-xs font-mono text-neutral-200 focus:outline-none focus:border-yellow-400"
          >
            <option value="">Select recipient...</option>
            {(users ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.display_name} ({u.username})
              </option>
            ))}
          </select>
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Location (optional)"
            className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-xs font-mono text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-yellow-400"
          />
          <button
            onClick={current ? initiate : intake}
            disabled={busy || !recipientId}
            className="w-full px-4 py-2 rounded bg-yellow-400 hover:bg-yellow-300 disabled:opacity-50 text-neutral-950 font-bold text-xs font-mono uppercase tracking-wider flex items-center justify-center gap-2 transition-all"
          >
            {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
            <span>{current ? 'GENERATE HANDOFF QR' : 'RECORD INTAKE'}</span>
          </button>

          {qr && (
            <div className="p-3 bg-white rounded flex flex-col items-center gap-2">
              <img src={`data:image/png;base64,${qr}`} alt="Custody handoff QR code" className="w-40 h-40" />
              <span className="text-[10px] font-mono text-neutral-700">
                Opaque handoff token only -- no evidence data encoded.
              </span>
            </div>
          )}
        </div>

        <div className="space-y-2">
          <div className="text-[10px] font-mono uppercase text-neutral-400 font-bold flex items-center gap-1.5">
            <QrCode className="w-3.5 h-3.5" />
            <span>ACCEPT/REJECT A SCANNED HANDOFF</span>
          </div>
          <p className="text-[10px] font-mono text-neutral-500 leading-relaxed">
            No camera-based QR scanner is wired into this browser session (see Phase 23 final
            report). Paste the token here -- typically read from the receiving device's own scan.
          </p>
          <input
            type="text"
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
            placeholder="Paste handoff token..."
            className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-xs font-mono text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-yellow-400"
          />
          <div className="flex gap-2">
            <button
              onClick={acceptToken}
              disabled={busy || !tokenInput.trim()}
              className="flex-1 px-3 py-2 rounded bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 text-xs font-mono font-bold flex items-center justify-center gap-1.5 disabled:opacity-50"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>ACCEPT</span>
            </button>
            <button
              onClick={rejectToken}
              disabled={busy || !tokenInput.trim()}
              className="flex-1 px-3 py-2 rounded bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-300 text-xs font-mono font-bold flex items-center justify-center gap-1.5 disabled:opacity-50"
            >
              <XCircle className="w-3.5 h-3.5" />
              <span>REJECT</span>
            </button>
          </div>
        </div>
      </div>

      <div className="pt-2 border-t border-neutral-800 space-y-1.5">
        <div className="text-[10px] font-mono uppercase text-neutral-400 font-bold flex items-center gap-1.5">
          <History className="w-3.5 h-3.5" />
          <span>CUSTODY HISTORY</span>
        </div>
        {!history || history.length === 0 ? (
          <div className="text-[11px] font-mono text-neutral-500">No custody events recorded.</div>
        ) : (
          history.map((h) => (
            <div key={h.id} className="flex items-center justify-between text-[11px] font-mono bg-neutral-900 border border-neutral-800 rounded p-2">
              <span className="text-neutral-300">
                {h.transfer_type} · {h.releasing_user_display_name ?? 'intake'} → {h.receiving_user_display_name}
              </span>
              <StatusBadge status={h.status} />
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export const CustodyView: React.FC<CustodyViewProps> = ({ caseId }) => {
  const { data: evidenceList, loading, error } = useApiQuery(() => casesApi.listEvidence(caseId), [caseId]);

  if (loading) return <LoadingState label="Loading evidence…" />;
  if (error) return <ErrorState message={error} />;
  if (!evidenceList || evidenceList.length === 0) {
    return <EmptyState message="No evidence registered for this case yet." />;
  }

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {evidenceList.map((e) => (
        <EvidenceCustodyPanel key={e.id} evidence={e} />
      ))}
    </div>
  );
};

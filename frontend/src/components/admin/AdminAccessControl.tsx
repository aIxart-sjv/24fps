import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { useApiQuery } from '../../hooks/useApiQuery';
import { caseAccessApi, usersApi, ApiError } from '../../lib/api';
import { LoadingState, ErrorState, StatusBadge } from '../common/CommonUI';
import { Key, Users, Check, X, Loader2, ShieldAlert } from 'lucide-react';

/**
 * Real, backend-enforced per-case access matrix (Phase 25, "Case-Level
 * Access Control / Admin Permission Matrix"). Every cell reflects an
 * actual `CaseUserAccess` row (or an admin's unconditional access) --
 * clicking a cell calls the real grant/revoke API and re-reads the
 * matrix, never a client-side-only toggle. A prior version of this
 * screen disclosed that no such backend model existed at all; that
 * limitation is what this replaces.
 *
 * Deliberately shows only two states, active/inactive -- there is no
 * "L1/L2/L3 clearance" concept here (task: "Do not claim OFFICER = L1...
 * unless those clearance levels are genuinely implemented and enforced").
 * The only two axes that exist are role (fixed per account) and case
 * access (this matrix).
 */
export const AdminAccessControl: React.FC = () => {
  const { currentUser, addToast } = useApp();
  const isAdmin = currentUser?.role === 'admin';
  const { data: users, loading: usersLoading } = useApiQuery(() => usersApi.list(), []);
  const {
    data: matrix,
    loading: matrixLoading,
    error: matrixError,
    refetch: refetchMatrix,
  } = useApiQuery(() => caseAccessApi.matrix(), []);
  const [pendingCell, setPendingCell] = useState<string | null>(null);

  const toggleCell = async (caseId: number, userId: number, currentlyActive: boolean, role: string) => {
    if (!isAdmin || role === 'admin') return; // admin rows are unconditional, never editable
    const cellKey = `${caseId}:${userId}`;
    setPendingCell(cellKey);
    try {
      if (currentlyActive) {
        await caseAccessApi.revoke(caseId, userId);
        addToast({ title: 'Access revoked', type: 'success' });
      } else {
        await caseAccessApi.grant(caseId, userId);
        addToast({ title: 'Access granted', type: 'success' });
      }
      await refetchMatrix();
    } catch (err) {
      addToast({
        title: 'Access change failed',
        description: err instanceof ApiError ? err.message : 'Unexpected error.',
        type: 'error',
      });
    } finally {
      setPendingCell(null);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="bg-neutral-950 border border-neutral-800 rounded p-5 space-y-4">
        <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2 pb-2 border-b border-neutral-800">
          <Users className="w-4 h-4 text-yellow-400" />
          <span>ACCOUNT ROLES</span>
        </h2>
        {usersLoading ? (
          <LoadingState />
        ) : (
          <div className="space-y-1.5">
            {(users ?? []).map((u) => (
              <div key={u.id} className="flex items-center justify-between bg-neutral-900 border border-neutral-800 rounded p-2.5 text-xs font-mono">
                <span className="text-neutral-200">{u.display_name} ({u.username})</span>
                <StatusBadge status={u.role} type="info" />
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-neutral-950 border border-neutral-800 rounded p-5">
        <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2 pb-2 mb-1 border-b border-neutral-800">
          <Key className="w-4 h-4 text-yellow-400" />
          <span>CASE ACCESS MATRIX</span>
        </h2>
        <p className="text-[10px] font-mono text-neutral-500 mb-3">
          Real, backend-enforced case assignments (app.core.case_authorization_service). ADMIN rows
          are unconditional and cannot be edited. {isAdmin ? 'Click a cell to grant/revoke access.' : 'Read-only for your role.'}
        </p>

        {matrixLoading && <LoadingState label="Loading access matrix…" />}
        {matrixError && <ErrorState message={matrixError} onRetry={refetchMatrix} />}

        {!matrixLoading && !matrixError && matrix && (
          matrix.cases.length === 0 ? (
            <div className="p-3 rounded bg-neutral-900 border border-neutral-800 text-xs font-mono text-neutral-400 flex items-start gap-2">
              <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5 text-neutral-500" />
              <span>No cases exist yet -- the matrix will populate once cases are created.</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="border-collapse text-xs font-mono min-w-full">
                <thead>
                  <tr className="border-b border-neutral-800 bg-neutral-900/80 text-neutral-400">
                    <th className="py-2.5 px-3 text-left font-semibold uppercase sticky left-0 bg-neutral-900/95 z-10">
                      Officer / Role
                    </th>
                    {matrix.cases.map((c) => (
                      <th key={c.id} className="py-2.5 px-3 text-center font-semibold uppercase whitespace-nowrap" title={c.name}>
                        {c.case_id}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-900">
                  {matrix.users.map((u) => (
                    <tr key={u.user_id} className="text-neutral-300">
                      <td className="py-2 px-3 sticky left-0 bg-neutral-950 z-10">
                        <div className="text-neutral-200 font-semibold">{u.display_name}</div>
                        <div className="text-neutral-500 text-[10px]">{u.username} · {u.role.toUpperCase()}</div>
                      </td>
                      {matrix.cases.map((c) => {
                        const active = u.access_by_case_id[String(c.id)] ?? false;
                        const isAdminRow = u.role === 'admin';
                        const cellKey = `${c.id}:${u.user_id}`;
                        const isPending = pendingCell === cellKey;
                        const editable = isAdmin && !isAdminRow;
                        return (
                          <td key={c.id} className="py-2 px-3 text-center">
                            <button
                              type="button"
                              disabled={!editable || isPending}
                              onClick={() => toggleCell(c.id, u.user_id, active, u.role)}
                              title={
                                isAdminRow
                                  ? 'Admins have unconditional access'
                                  : editable
                                    ? active
                                      ? 'Click to revoke'
                                      : 'Click to grant'
                                    : undefined
                              }
                              className={`w-7 h-7 rounded flex items-center justify-center transition-colors border ${
                                active
                                  ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-400'
                                  : 'bg-neutral-900 border-neutral-800 text-neutral-600'
                              } ${editable ? 'cursor-pointer hover:border-yellow-400/60' : 'cursor-default'}`}
                            >
                              {isPending ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : active ? (
                                <Check className="w-3.5 h-3.5" />
                              ) : (
                                <X className="w-3.5 h-3.5 opacity-40" />
                              )}
                            </button>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>
    </div>
  );
};

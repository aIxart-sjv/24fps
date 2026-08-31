import React, { useState } from 'react';
import { useApiQuery } from '../../hooks/useApiQuery';
import { casesApi, ApiError } from '../../lib/api';
import { StatusBadge, LoadingState, ErrorState, EmptyState } from '../common/CommonUI';
import { FolderLock, Search, Plus, Loader2 } from 'lucide-react';

export const AdminCases: React.FC = () => {
  const { data: cases, loading, error, refetch } = useApiQuery(() => casesApi.list(), []);
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [newCaseId, setNewCaseId] = useState('');
  const [newCaseName, setNewCaseName] = useState('');
  const [newExaminer, setNewExaminer] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const { data: evidenceCounts } = useApiQuery(() => {
    if (!cases) return null;
    return Promise.all(cases.map((c) => casesApi.listEvidence(c.id))).then((lists) =>
      Object.fromEntries(cases.map((c, i) => [c.id, lists[i].length]))
    );
  }, [cases]);

  const filteredCases = (cases ?? []).filter(
    (c) =>
      c.case_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.name.toLowerCase().includes(searchQuery.toLowerCase())
  );
  const selectedCase = (cases ?? []).find((c) => c.id === selectedCaseId) ?? null;

  const createCase = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      await casesApi.create({ case_id: newCaseId, name: newCaseName, examiner: newExaminer || undefined });
      setShowCreate(false);
      setNewCaseId('');
      setNewCaseName('');
      setNewExaminer('');
      refetch();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : 'Failed to create case.');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col lg:flex-row gap-5 min-h-0 animate-in fade-in duration-200">
      <div className="flex-1 flex flex-col bg-neutral-950 border border-neutral-800 rounded min-h-0">
        <div className="p-4 border-b border-neutral-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2">
              <FolderLock className="w-4 h-4 text-yellow-400" />
              <span>CASES DIRECTORY</span>
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-neutral-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search cases..."
                className="w-full bg-neutral-900 border border-neutral-800 rounded pl-8 pr-3 py-1.5 text-xs font-mono text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-yellow-400"
              />
            </div>
            <button
              onClick={() => setShowCreate((v) => !v)}
              className="px-3 py-1.5 rounded bg-yellow-400 hover:bg-yellow-300 text-neutral-950 font-bold text-xs font-mono flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>NEW CASE</span>
            </button>
          </div>
        </div>

        {showCreate && (
          <form onSubmit={createCase} className="p-4 border-b border-neutral-800 bg-neutral-900/50 grid grid-cols-1 sm:grid-cols-3 gap-2">
            {createError && <div className="sm:col-span-3"><ErrorState message={createError} /></div>}
            <input
              value={newCaseId}
              onChange={(e) => setNewCaseId(e.target.value)}
              placeholder="Case ID (e.g. CASE-2026-010)"
              required
              className="bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-xs font-mono text-neutral-200 placeholder-neutral-500"
            />
            <input
              value={newCaseName}
              onChange={(e) => setNewCaseName(e.target.value)}
              placeholder="Case name"
              required
              className="bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-xs font-mono text-neutral-200 placeholder-neutral-500"
            />
            <input
              value={newExaminer}
              onChange={(e) => setNewExaminer(e.target.value)}
              placeholder="Examiner (optional)"
              className="bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-xs font-mono text-neutral-200 placeholder-neutral-500"
            />
            <button
              type="submit"
              disabled={creating}
              className="sm:col-span-3 px-4 py-2 rounded bg-yellow-400 hover:bg-yellow-300 text-neutral-950 font-bold text-xs font-mono flex items-center justify-center gap-2"
            >
              {creating && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>CREATE CASE</span>
            </button>
          </form>
        )}

        <div className="flex-1 overflow-y-auto">
          {loading && <LoadingState />}
          {error && <ErrorState message={error} onRetry={refetch} />}
          {!loading && !error && filteredCases.length === 0 && <EmptyState message="No cases yet." />}
          {!loading && !error && filteredCases.length > 0 && (
            <table className="w-full text-left border-collapse text-xs font-mono">
              <thead>
                <tr className="border-b border-neutral-800 bg-neutral-900/80 text-neutral-400">
                  <th className="py-2.5 px-4 font-semibold uppercase">CASE ID</th>
                  <th className="py-2.5 px-4 font-semibold uppercase">NAME</th>
                  <th className="py-2.5 px-4 font-semibold uppercase">STATUS</th>
                  <th className="py-2.5 px-4 font-semibold uppercase">EXAMINER</th>
                  <th className="py-2.5 px-4 font-semibold uppercase">EVIDENCE</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-900">
                {filteredCases.map((caseItem) => (
                  <tr
                    key={caseItem.id}
                    onClick={() => setSelectedCaseId(caseItem.id)}
                    className={`cursor-pointer transition-colors ${
                      caseItem.id === selectedCaseId ? 'bg-yellow-400/10 text-neutral-100' : 'hover:bg-neutral-900/60 text-neutral-300'
                    }`}
                  >
                    <td className="py-3 px-4 font-bold text-yellow-400 whitespace-nowrap">{caseItem.case_id}</td>
                    <td className="py-3 px-4 font-sans font-semibold text-neutral-200">{caseItem.name}</td>
                    <td className="py-3 px-4">
                      <StatusBadge status={caseItem.status} />
                    </td>
                    <td className="py-3 px-4 text-neutral-300">{caseItem.examiner ?? '—'}</td>
                    <td className="py-3 px-4 font-bold text-neutral-200">{evidenceCounts?.[caseItem.id] ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {selectedCase && (
        <div className="w-full lg:w-80 xl:w-96 shrink-0 bg-neutral-950 border border-neutral-800 rounded p-4 flex flex-col gap-4 overflow-y-auto">
          <div className="pb-3 border-b border-neutral-800">
            <div className="flex items-center justify-between">
              <span className="font-mono text-sm font-bold text-yellow-400">{selectedCase.case_id}</span>
              <StatusBadge status={selectedCase.status} />
            </div>
            <h3 className="text-sm font-bold text-neutral-100 font-sans mt-1">{selectedCase.name}</h3>
          </div>
          <div className="space-y-3 text-xs font-mono">
            <div className="bg-neutral-900 border border-neutral-800 rounded p-3 space-y-1.5">
              <div className="flex justify-between">
                <span className="text-neutral-400">Examiner:</span>
                <span className="text-neutral-200">{selectedCase.examiner ?? 'unassigned'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-neutral-400">Created:</span>
                <span className="text-neutral-200">{new Date(selectedCase.created_at).toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-neutral-400">Evidence Count:</span>
                <span className="text-neutral-200">{evidenceCounts?.[selectedCase.id] ?? '—'}</span>
              </div>
            </div>
            {selectedCase.description && (
              <div className="bg-neutral-900 border border-neutral-800 rounded p-3 space-y-1.5">
                <div className="text-[10px] text-neutral-400 uppercase font-bold">DESCRIPTION</div>
                <p className="text-xs text-neutral-300 font-sans leading-relaxed">{selectedCase.description}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

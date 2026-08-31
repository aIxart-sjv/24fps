import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { useApiQuery } from '../../hooks/useApiQuery';
import { usersApi, ApiError } from '../../lib/api';
import { LoadingState, ErrorState, StatusBadge } from '../common/CommonUI';
import { Users, UserPlus, Loader2 } from 'lucide-react';

export const AdminUsers: React.FC = () => {
  const { currentUser, addToast } = useApp();
  const { data: users, loading, error, refetch } = useApiQuery(() => usersApi.list(), []);

  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'officer' | 'lab_personnel' | 'admin'>('officer');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const isAdmin = currentUser?.role === 'admin';

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      await usersApi.create({ username, display_name: displayName, password, role });
      setUsername('');
      setDisplayName('');
      setPassword('');
      addToast({ title: 'User created', description: `${displayName} (${username}) provisioned.`, type: 'success' });
      refetch();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : 'Failed to create user.');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col lg:flex-row gap-5 min-h-0 animate-in fade-in duration-200">
      <div className="flex-1 flex flex-col bg-neutral-950 border border-neutral-800 rounded min-h-0">
        <div className="p-4 border-b border-neutral-800 flex items-center justify-between">
          <h2 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2">
            <Users className="w-4 h-4 text-yellow-400" />
            <span>FORENSIC PERSONNEL DIRECTORY</span>
          </h2>
          <span className="text-[11px] font-mono text-neutral-400">{users?.length ?? '—'} PERSONNEL</span>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading && <LoadingState />}
          {error && <ErrorState message={error} onRetry={refetch} />}
          {!loading && !error && (
            <table className="w-full text-left border-collapse text-xs font-mono">
              <thead>
                <tr className="border-b border-neutral-800 bg-neutral-900/80 text-neutral-400">
                  <th className="py-2.5 px-4 font-semibold uppercase">USERNAME</th>
                  <th className="py-2.5 px-4 font-semibold uppercase">DISPLAY NAME</th>
                  <th className="py-2.5 px-4 font-semibold uppercase">ROLE</th>
                  <th className="py-2.5 px-4 font-semibold uppercase">STATUS</th>
                  <th className="py-2.5 px-4 font-semibold uppercase">CREATED</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-900">
                {(users ?? []).map((u) => (
                  <tr key={u.id} className="text-neutral-300">
                    <td className="py-3 px-4 font-bold text-yellow-400">{u.username}</td>
                    <td className="py-3 px-4">{u.display_name}</td>
                    <td className="py-3 px-4 uppercase">{u.role}</td>
                    <td className="py-3 px-4">
                      <StatusBadge status={u.is_active ? 'active' : 'inactive'} />
                    </td>
                    <td className="py-3 px-4 text-neutral-500">{new Date(u.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="w-full lg:w-80 shrink-0 bg-neutral-950 border border-neutral-800 rounded p-4 space-y-3">
        <h3 className="text-xs font-mono uppercase tracking-wider font-bold text-neutral-200 flex items-center gap-2 pb-2 border-b border-neutral-800">
          <UserPlus className="w-4 h-4 text-yellow-400" />
          <span>PROVISION NEW USER</span>
        </h3>
        {!isAdmin ? (
          <p className="text-[11px] font-mono text-neutral-400">
            Only an administrator account can provision new users (POST /api/v1/users is admin-only).
          </p>
        ) : (
          <form onSubmit={handleCreate} className="space-y-2">
            {createError && <ErrorState message={createError} />}
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Username"
              required
              className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-xs font-mono text-neutral-200 placeholder-neutral-500"
            />
            <input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Display name"
              required
              className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-xs font-mono text-neutral-200 placeholder-neutral-500"
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              required
              className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-xs font-mono text-neutral-200 placeholder-neutral-500"
            />
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as typeof role)}
              className="w-full bg-neutral-900 border border-neutral-800 rounded px-3 py-2 text-xs font-mono text-neutral-200"
            >
              <option value="officer">Officer</option>
              <option value="lab_personnel">Lab Personnel</option>
              <option value="admin">Admin</option>
            </select>
            <button
              type="submit"
              disabled={creating}
              className="w-full px-4 py-2 rounded bg-yellow-400 hover:bg-yellow-300 text-neutral-950 font-bold text-xs font-mono flex items-center justify-center gap-2"
            >
              {creating && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>CREATE USER</span>
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

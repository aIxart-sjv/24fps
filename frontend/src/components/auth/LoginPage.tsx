import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { Logo24FPS, LogoCBI } from '../Logos';
import { ShieldCheck, AlertCircle, ArrowLeft, KeyRound, User as UserIcon } from 'lucide-react';

interface LoginPageProps {
  onSuccess?: (role: 'officer' | 'lab_personnel' | 'admin') => void;
  onBackToLanding?: () => void;
  onNavigate?: (path: string) => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onSuccess, onBackToLanding, onNavigate }) => {
  const { login } = useApp();
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const handleBack = () => {
    if (onBackToLanding) onBackToLanding();
    else if (onNavigate) onNavigate('/');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    const result = await login(username.trim(), password);
    setIsSubmitting(false);
    if (result.ok && result.role) {
      onSuccess?.(result.role);
    } else {
      setError(result.error || 'Invalid username or password.');
    }
  };

  return (
    <div className="min-h-screen w-full bg-neutral-950 text-neutral-100 flex flex-col justify-between p-4 sm:p-8 select-none">
      <header className="flex items-center justify-between max-w-4xl mx-auto w-full pt-2">
        <button
          onClick={handleBack}
          className="flex items-center gap-2 text-xs font-mono text-neutral-400 hover:text-yellow-400 transition-colors p-2 rounded hover:bg-neutral-900"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>PORTAL HOME</span>
        </button>

        <div className="flex items-center gap-4">
          <Logo24FPS variant="dark" className="h-7 sm:h-8 w-auto" />
          <span className="h-4 w-px bg-neutral-800" />
          <LogoCBI className="h-7 sm:h-8 w-auto" />
        </div>
      </header>

      <main className="max-w-md w-full mx-auto my-auto px-4">
        <div className="bg-neutral-900 border border-neutral-800 rounded p-6 sm:p-8 shadow-2xl">
          <div className="text-center mb-6">
            <div className="inline-flex p-2.5 rounded bg-neutral-800/80 border border-neutral-700/80 mb-3 text-yellow-400">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-neutral-100 tracking-tight font-sans">
              24FPS EVIDENCE GATEWAY
            </h2>
            <p className="text-xs text-neutral-400 font-mono mt-1">
              AUTHORIZED FORENSIC PERSONNEL ONLY
            </p>
          </div>

          {error && (
            <div className="mb-5 p-3 rounded bg-red-950/40 border border-red-500/40 text-red-300 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-400" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="username-input"
                className="block text-xs font-mono font-medium text-neutral-300 mb-1.5 uppercase tracking-wider"
              >
                Username
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-500">
                  <UserIcon className="w-4 h-4" />
                </div>
                <input
                  id="username-input"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="your account username"
                  required
                  autoFocus
                  className="w-full bg-neutral-950 border border-neutral-700 rounded py-2.5 pl-9 pr-3 text-sm font-mono text-neutral-100 placeholder-neutral-600 focus:outline-none focus:border-yellow-400 focus:ring-1 focus:ring-yellow-400 transition-colors"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="password-input"
                className="block text-xs font-mono font-medium text-neutral-300 mb-1.5 uppercase tracking-wider"
              >
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-500">
                  <KeyRound className="w-4 h-4" />
                </div>
                <input
                  id="password-input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full bg-neutral-950 border border-neutral-700 rounded py-2.5 pl-9 pr-3 text-sm font-mono text-neutral-100 placeholder-neutral-600 focus:outline-none focus:border-yellow-400 focus:ring-1 focus:ring-yellow-400 transition-colors"
                />
              </div>
            </div>

            <div className="pt-2">
              <button
                id="authenticate-btn"
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3 rounded bg-yellow-400 hover:bg-yellow-300 text-neutral-950 font-bold text-sm tracking-wider uppercase font-sans transition-all duration-200 cursor-pointer active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed shadow-md"
              >
                {isSubmitting ? 'VERIFYING CREDENTIALS...' : 'AUTHENTICATE'}
              </button>
            </div>
          </form>

          <p className="mt-6 pt-5 border-t border-neutral-800 text-[11px] font-mono text-neutral-400 leading-relaxed">
            Accounts are provisioned by a system administrator (
            <span className="text-neutral-300">POST /api/v1/users</span>, admin-only) or via the
            backend's <span className="text-neutral-300">AuthManager.create_user</span> bootstrap
            path -- there is no self-service registration.
          </p>
        </div>
      </main>

      <footer className="text-center text-[11px] font-mono text-neutral-400 pb-2">
        <span>24FPS FORENSIC SYSTEM · ISO/IEC 27037 EVIDENCE AUDIT PROTOCOL</span>
      </footer>
    </div>
  );
};

import React from 'react';
import { useApp } from '../../context/AppContext';
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X, Loader2, Inbox, RefreshCw, ShieldOff } from 'lucide-react';

/** Real loading state -- never a silent blank screen while a request is in flight. */
export const LoadingState: React.FC<{ label?: string }> = ({ label = 'Loading…' }) => (
  <div className="flex-1 flex flex-col items-center justify-center gap-3 p-10 text-neutral-400">
    <Loader2 className="w-6 h-6 animate-spin text-yellow-400" />
    <span className="text-xs font-mono">{label}</span>
  </div>
);

/** Real error state -- never masked behind an empty mock array (task Phase 23
 * scope, "No Mock Fallback in Production"). */
export const ErrorState: React.FC<{ message: string; onRetry?: () => void }> = ({
  message,
  onRetry,
}) => (
  <div className="flex-1 flex flex-col items-center justify-center gap-3 p-10 text-center">
    <AlertCircle className="w-6 h-6 text-red-400" />
    <p className="text-xs font-mono text-red-300 max-w-md">{message}</p>
    {onRetry && (
      <button
        onClick={onRetry}
        className="mt-1 px-3 py-1.5 rounded bg-neutral-900 border border-neutral-800 hover:border-red-500/50 text-xs font-mono text-neutral-200 flex items-center gap-1.5 transition-colors"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        <span>RETRY</span>
      </button>
    )}
  </div>
);

/** A real, backend-enforced `403` (Phase 25, "Case-Level Access Control"):
 * this officer is authenticated but not assigned to this case. Distinct
 * from `ErrorState` so it never reads as a generic/transient failure --
 * and never silently redirects or shows fake data (task section 22). */
export const AccessDeniedState: React.FC<{ message?: string }> = ({ message }) => (
  <div className="flex-1 flex flex-col items-center justify-center gap-3 p-10 text-center">
    <ShieldOff className="w-7 h-7 text-amber-400" />
    <p className="text-sm font-mono font-bold text-amber-300">ACCESS DENIED</p>
    <p className="text-xs font-mono text-neutral-400 max-w-md">
      {message ?? "You are not assigned to this case."} Contact an administrator to request access.
    </p>
  </div>
);

/** A real empty state, distinct from an error -- the backend answered
 * successfully, there is simply nothing there yet. */
export const EmptyState: React.FC<{ message: string; icon?: React.ReactNode }> = ({
  message,
  icon,
}) => (
  <div className="flex-1 flex flex-col items-center justify-center gap-3 p-10 text-center text-neutral-400">
    {icon ?? <Inbox className="w-6 h-6" />}
    <p className="text-xs font-mono max-w-md">{message}</p>
  </div>
);

/** A capability the real backend does not (yet) provide -- surfaced
 * honestly rather than removed or faked (task Phase 23 scope, "Missing
 * Feature Policy"). */
export const UnavailableState: React.FC<{ title: string; reason: string }> = ({
  title,
  reason,
}) => (
  <div className="bg-neutral-950 border border-dashed border-neutral-800 rounded p-8 text-center space-y-2">
    <div className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-300">
      {title}
    </div>
    <p className="text-xs font-mono text-neutral-400 max-w-lg mx-auto leading-relaxed">{reason}</p>
    <div className="inline-flex items-center gap-1.5 mt-1 text-[10px] font-mono text-amber-400 bg-amber-950/20 border border-amber-500/20 px-2 py-0.5 rounded">
      NOT YET IMPLEMENTED IN THE BACKEND
    </div>
  </div>
);

export const ToastContainer: React.FC = () => {
  const { toasts, removeToast } = useApp();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      {toasts.map((toast) => {
        let icon = <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />;
        let borderClass = 'border-emerald-500/30';
        let bgClass = 'bg-emerald-950/20';

        if (toast.type === 'error') {
          icon = <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />;
          borderClass = 'border-red-500/30';
          bgClass = 'bg-red-950/20';
        } else if (toast.type === 'warning') {
          icon = <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />;
          borderClass = 'border-amber-400/30';
          bgClass = 'bg-amber-950/20';
        } else if (toast.type === 'info') {
          icon = <Info className="w-4 h-4 text-yellow-400 shrink-0 mt-0.5" />;
          borderClass = 'border-yellow-400/30';
          bgClass = 'bg-yellow-950/20';
        }

        return (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-start gap-3 p-3.5 rounded border ${borderClass} ${bgClass} bg-neutral-900/95 dark:bg-neutral-900/95 text-neutral-100 dark:text-neutral-100 shadow-lg backdrop-blur-sm transition-all duration-200 animate-in fade-in slide-in-from-bottom-2`}
          >
            {icon}
            <div className="flex-1 min-w-0">
              <div className="text-xs font-semibold text-neutral-100">{toast.title}</div>
              {toast.description && (
                <div className="text-[11px] text-neutral-400 mt-0.5 leading-snug">
                  {toast.description}
                </div>
              )}
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="text-neutral-400 hover:text-neutral-200 transition-colors p-0.5 rounded"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
};

export const StatusBadge: React.FC<{
  status: string;
  type?: 'success' | 'warning' | 'error' | 'neutral' | 'info' | 'auto';
  className?: string;
}> = ({ status, type = 'auto', className = '' }) => {
  let style = 'bg-neutral-800 text-neutral-300 border-neutral-700';

  const lower = status.toLowerCase();

  if (
    type === 'success' ||
    lower === 'verified' ||
    lower === 'recovered' ||
    lower === 'online' ||
    lower === 'active' ||
    lower === 'good' ||
    lower === 'approved' ||
    lower === 'completed' ||
    lower === 'measured' ||
    lower === 'validated' ||
    lower === 'controlled'
  ) {
    style =
      'bg-emerald-950/30 text-emerald-400 border-emerald-500/30 dark:bg-emerald-950/30 dark:text-emerald-400 dark:border-emerald-500/30';
  } else if (
    type === 'warning' ||
    lower === 'fragmented' ||
    lower === 'pending' ||
    lower === 'pending acquisition' ||
    lower === 'submitted' ||
    lower === 'review' ||
    lower === 'degraded' ||
    lower === 'required' ||
    lower === 'low confidence' ||
    lower === 'partial' ||
    lower === 'requires_review' ||
    lower === 'requires review' ||
    lower === 'unverified'
  ) {
    style =
      'bg-amber-950/30 text-amber-400 border-amber-500/30 dark:bg-amber-950/30 dark:text-amber-400 dark:border-amber-500/30';
  } else if (
    type === 'error' ||
    lower === 'deleted' ||
    lower === 'mismatch' ||
    lower === 'offline' ||
    lower === 'failed' ||
    lower === 'access denied' ||
    lower === 'critical' ||
    lower === 'blocked'
  ) {
    style =
      'bg-red-950/30 text-red-400 border-red-500/30 dark:bg-red-950/30 dark:text-red-400 dark:border-red-500/30';
  } else if (lower === 'recording' || lower === 'processing') {
    style =
      'bg-yellow-950/30 text-yellow-300 border-yellow-500/30 dark:bg-yellow-950/30 dark:text-yellow-300 dark:border-yellow-500/30';
  }

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono font-medium border uppercase tracking-wider ${style} ${className}`}
    >
      {status}
    </span>
  );
};

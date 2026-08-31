import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '../lib/api';

export interface ApiQueryState<TData> {
  data: TData | null;
  loading: boolean;
  error: string | null;
  /** The failed request's HTTP status, when `error` came from the API
   * (never set for a network-level failure) -- lets a caller render a
   * `403` ("access denied") distinctly from a generic error state
   * (Phase 25 task section 22: "show a proper 403 / Access denied
   * state... do not show fake data"). */
  errorStatus: number | null;
  refetch: () => void;
}

/**
 * Thin, shared data-fetching hook so every view gets real
 * loading/error/empty/success states from the actual backend instead of
 * silently falling back to mock data (task Phase 23 scope, "Loading /
 * Error / Empty States"). `deps` re-runs the fetch when any value
 * changes (e.g. the active case ID) -- pass `null` from `fetcher` calls
 * that should not run yet (e.g. no case selected).
 */
export function useApiQuery<TData>(
  fetcher: () => Promise<TData> | null,
  deps: unknown[]
): ApiQueryState<TData> {
  const [data, setData] = useState<TData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const requestId = useRef(0);

  const load = useCallback(() => {
    const promise = fetcher();
    if (promise === null) {
      setLoading(false);
      return;
    }
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError(null);
    setErrorStatus(null);
    promise
      .then((result) => {
        if (requestId.current !== currentRequest) return;
        setData(result);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (requestId.current !== currentRequest) return;
        setError(err instanceof ApiError ? err.message : 'An unexpected error occurred.');
        setErrorStatus(err instanceof ApiError ? err.status : null);
        setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, error, errorStatus, refetch: load };
}

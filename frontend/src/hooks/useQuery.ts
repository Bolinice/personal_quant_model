import { useState, useEffect, useCallback } from 'react';

export interface QueryState<T> {
  data: T | null;
  loading: boolean;
  error: string;
}

export interface QueryOptions<T = unknown> {
  enabled?: boolean;
  refetchOnMount?: boolean;
  onSuccess?: (data: T) => void;
  onError?: (error: Error) => void;
}

export function useQuery<T>(
  queryFn: () => Promise<T>,
  deps: unknown[] = [],
  options: QueryOptions<T> = {}
) {
  const { enabled = true, refetchOnMount = true, onSuccess, onError } = options;
  const [state, setState] = useState<QueryState<T>>({
    data: null,
    loading: false,
    error: '',
  });

  const execute = useCallback(async () => {
    if (!enabled) return;

    setState((prev) => ({ ...prev, loading: true, error: '' }));
    try {
      const result = await queryFn();
      setState({ data: result, loading: false, error: '' });
      onSuccess?.(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : '请求失败';
      setState({ data: null, loading: false, error: message });
      onError?.(err instanceof Error ? err : new Error(message));
    }
  }, [enabled, queryFn, onSuccess, onError]);

  useEffect(() => {
    if (!refetchOnMount || !enabled) return;
    execute();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, execute, refetchOnMount]);

  const refetch = useCallback(() => {
    execute();
  }, [execute]);

  return { ...state, refetch };
}

export function useQueries<T extends unknown[]>(
  queryFns: Array<() => Promise<unknown>>,
  options: QueryOptions = {}
) {
  const { enabled = true, onSuccess, onError } = options;
  const [state, setState] = useState<QueryState<T>>({
    data: null,
    loading: false,
    error: '',
  });

  const execute = useCallback(async () => {
    if (!enabled) return;

    setState((prev) => ({ ...prev, loading: true, error: '' }));
    try {
      const results = await Promise.all(queryFns.map((fn) => fn()));
      setState({ data: results as T, loading: false, error: '' });
      onSuccess?.(results);
    } catch (err) {
      const message = err instanceof Error ? err.message : '请求失败';
      setState({ data: null, loading: false, error: message });
      onError?.(err instanceof Error ? err : new Error(message));
    }
  }, [enabled, queryFns, onSuccess, onError]);

  useEffect(() => {
    if (!enabled) return;
    execute();
  }, [execute, enabled]);

  const refetch = useCallback(() => {
    execute();
  }, [execute]);

  return { ...state, refetch };
}

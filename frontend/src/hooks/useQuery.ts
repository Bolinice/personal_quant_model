import { useState, useEffect, useCallback, useRef } from 'react';

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

  // Use refs to avoid recreating execute on every callback change
  const queryFnRef = useRef(queryFn);
  const onSuccessRef = useRef(onSuccess);
  const onErrorRef = useRef(onError);

  // Update refs on each render
  queryFnRef.current = queryFn;
  onSuccessRef.current = onSuccess;
  onErrorRef.current = onError;

  const execute = useCallback(async () => {
    if (!enabled) return;

    setState((prev) => ({ ...prev, loading: true, error: '' }));
    try {
      const result = await queryFnRef.current();
      setState({ data: result, loading: false, error: '' });
      onSuccessRef.current?.(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : '请求失败';
      setState({ data: null, loading: false, error: message });
      onErrorRef.current?.(err instanceof Error ? err : new Error(message));
    }
  }, [enabled]);

  useEffect(() => {
    if (!refetchOnMount || !enabled) return;
    execute();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, refetchOnMount, enabled]);

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

  // Use refs to avoid recreating execute on every callback change
  const queryFnsRef = useRef(queryFns);
  const onSuccessRef = useRef(onSuccess);
  const onErrorRef = useRef(onError);

  // Update refs on each render
  queryFnsRef.current = queryFns;
  onSuccessRef.current = onSuccess;
  onErrorRef.current = onError;

  const execute = useCallback(async () => {
    if (!enabled) return;

    setState((prev) => ({ ...prev, loading: true, error: '' }));
    try {
      const results = await Promise.all(queryFnsRef.current.map((fn) => fn()));
      setState({ data: results as T, loading: false, error: '' });
      onSuccessRef.current?.(results);
    } catch (err) {
      const message = err instanceof Error ? err.message : '请求失败';
      setState({ data: null, loading: false, error: message });
      onErrorRef.current?.(err instanceof Error ? err : new Error(message));
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    execute();
  }, [execute, enabled]);

  const refetch = useCallback(() => {
    execute();
  }, [execute]);

  return { ...state, refetch };
}

import { useState, useEffect, useCallback } from 'react';

export interface QueryState<T> {
  data: T | null;
  loading: boolean;
  error: string;
}

export interface QueryOptions {
  enabled?: boolean;
  refetchOnMount?: boolean;
  onSuccess?: (data: any) => void;
  onError?: (error: Error) => void;
}

export function useQuery<T>(
  queryFn: () => Promise<T>,
  deps: any[] = [],
  options: QueryOptions = {}
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
    if (refetchOnMount) {
      execute();
    }
  }, [...deps, execute, refetchOnMount]);

  const refetch = useCallback(() => {
    execute();
  }, [execute]);

  return { ...state, refetch };
}

export function useQueries<T extends any[]>(
  queryFns: (() => Promise<any>)[],
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
    execute();
  }, [execute]);

  const refetch = useCallback(() => {
    execute();
  }, [execute]);

  return { ...state, refetch };
}

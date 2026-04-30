import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useQuery, useQueries } from '../hooks/useQuery';

describe('useQuery', () => {
  it('should fetch data successfully', async () => {
    const mockData = { id: 1, name: 'Test' };
    const queryFn = vi.fn().mockResolvedValue(mockData);

    const { result } = renderHook(() => useQuery(queryFn));

    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBe(null);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual(mockData);
    expect(result.current.error).toBe('');
    expect(queryFn).toHaveBeenCalledTimes(1);
  });

  it('should handle errors', async () => {
    const errorMessage = 'Failed to fetch';
    const queryFn = vi.fn().mockRejectedValue(new Error(errorMessage));

    const { result } = renderHook(() => useQuery(queryFn));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toBe(null);
    expect(result.current.error).toBe(errorMessage);
  });

  it('should not fetch when enabled is false', async () => {
    const queryFn = vi.fn().mockResolvedValue({ data: 'test' });

    const { result } = renderHook(() => useQuery(queryFn, [], { enabled: false }));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(queryFn).not.toHaveBeenCalled();
    expect(result.current.data).toBe(null);
  });

  it('should call onSuccess callback', async () => {
    const mockData = { id: 1, name: 'Test' };
    const queryFn = vi.fn().mockResolvedValue(mockData);
    const onSuccess = vi.fn();

    renderHook(() => useQuery(queryFn, [], { onSuccess }));

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith(mockData);
    });
  });

  it('should call onError callback', async () => {
    const error = new Error('Failed');
    const queryFn = vi.fn().mockRejectedValue(error);
    const onError = vi.fn();

    renderHook(() => useQuery(queryFn, [], { onError }));

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith(error);
    });
  });
});

describe('useQueries', () => {
  it('should fetch multiple queries successfully', async () => {
    const mockData1 = { id: 1, name: 'Test1' };
    const mockData2 = { id: 2, name: 'Test2' };
    const queryFn1 = vi.fn().mockResolvedValue(mockData1);
    const queryFn2 = vi.fn().mockResolvedValue(mockData2);

    const { result } = renderHook(() => useQueries([queryFn1, queryFn2]));

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual([mockData1, mockData2]);
    expect(result.current.error).toBe('');
  });

  it('should handle errors in multiple queries', async () => {
    const queryFn1 = vi.fn().mockResolvedValue({ data: 'test' });
    const queryFn2 = vi.fn().mockRejectedValue(new Error('Failed'));

    const { result } = renderHook(() => useQueries([queryFn1, queryFn2]));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toBe(null);
    expect(result.current.error).toBe('Failed');
  });
});

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useFilters } from '../hooks/useFilters';

interface TestItem {
  id: number;
  name: string;
  category: string;
  status: 'active' | 'inactive';
}

describe('useFilters', () => {
  const mockData: TestItem[] = [
    { id: 1, name: 'Item One', category: 'A', status: 'active' },
    { id: 2, name: 'Item Two', category: 'B', status: 'inactive' },
    { id: 3, name: 'Item Three', category: 'A', status: 'active' },
    { id: 4, name: 'Another Item', category: 'C', status: 'active' },
  ];

  it('should return all data initially', () => {
    const { result } = renderHook(() =>
      useFilters(mockData, {
        search: { fields: ['name'] },
      })
    );

    expect(result.current.filtered).toEqual(mockData);
    expect(result.current.search).toBe('');
    expect(result.current.filters).toEqual({});
  });

  it('should filter by search term', () => {
    const { result } = renderHook(() =>
      useFilters(mockData, {
        search: { fields: ['name'] },
      })
    );

    act(() => {
      result.current.setSearch('Item One');
    });

    expect(result.current.filtered).toEqual([mockData[0]]);
  });

  it('should filter by search term case-insensitively', () => {
    const { result } = renderHook(() =>
      useFilters(mockData, {
        search: { fields: ['name'] },
      })
    );

    act(() => {
      result.current.setSearch('item');
    });

    expect(result.current.filtered.length).toBe(4);
  });

  it('should search across multiple fields', () => {
    const { result } = renderHook(() =>
      useFilters(mockData, {
        search: { fields: ['name', 'category'] },
      })
    );

    act(() => {
      result.current.setSearch('A');
    });

    // Should match "Item One", "Item Three" (category A), and "Another Item"
    expect(result.current.filtered.length).toBe(3);
  });

  it('should apply single filter', () => {
    const { result } = renderHook(() =>
      useFilters(mockData, {
        filters: {
          category: {
            field: 'category',
            match: (itemValue, filterValue) => itemValue === filterValue,
          },
        },
      })
    );

    act(() => {
      result.current.setFilter('category', 'A');
    });

    expect(result.current.filtered).toEqual([mockData[0], mockData[2]]);
  });

  it('should apply multiple filters', () => {
    const { result } = renderHook(() =>
      useFilters(mockData, {
        filters: {
          category: {
            field: 'category',
            match: (itemValue, filterValue) => itemValue === filterValue,
          },
          status: {
            field: 'status',
            match: (itemValue, filterValue) => itemValue === filterValue,
          },
        },
      })
    );

    act(() => {
      result.current.setFilter('category', 'A');
      result.current.setFilter('status', 'active');
    });

    expect(result.current.filtered).toEqual([mockData[0], mockData[2]]);
  });

  it('should combine search and filters', () => {
    const { result } = renderHook(() =>
      useFilters(mockData, {
        search: { fields: ['name'] },
        filters: {
          status: {
            field: 'status',
            match: (itemValue, filterValue) => itemValue === filterValue,
          },
        },
      })
    );

    act(() => {
      result.current.setSearch('Item');
      result.current.setFilter('status', 'active');
    });

    // Should match "Item One", "Item Three", and "Another Item" (all active and contain "Item")
    expect(result.current.filtered).toEqual([mockData[0], mockData[2], mockData[3]]);
  });

  it('should ignore "all" filter value', () => {
    const { result } = renderHook(() =>
      useFilters(mockData, {
        filters: {
          category: {
            field: 'category',
            match: (itemValue, filterValue) => itemValue === filterValue,
          },
        },
      })
    );

    act(() => {
      result.current.setFilter('category', 'all');
    });

    expect(result.current.filtered).toEqual(mockData);
  });

  it('should reset all filters', () => {
    const { result } = renderHook(() =>
      useFilters(mockData, {
        search: { fields: ['name'] },
        filters: {
          category: {
            field: 'category',
            match: (itemValue, filterValue) => itemValue === filterValue,
          },
        },
      })
    );

    act(() => {
      result.current.setSearch('Item');
      result.current.setFilter('category', 'A');
    });

    expect(result.current.filtered.length).toBeLessThan(mockData.length);

    act(() => {
      result.current.resetFilters();
    });

    expect(result.current.search).toBe('');
    expect(result.current.filters).toEqual({});
    expect(result.current.filtered).toEqual(mockData);
  });

  it('should use custom field function', () => {
    const { result } = renderHook(() =>
      useFilters(mockData, {
        filters: {
          idRange: {
            field: (item) => item.id,
            match: (itemValue, filterValue) => (itemValue as number) <= (filterValue as number),
          },
        },
      })
    );

    act(() => {
      result.current.setFilter('idRange', 2);
    });

    expect(result.current.filtered).toEqual([mockData[0], mockData[1]]);
  });

  it('should apply search transform', () => {
    const { result } = renderHook(() =>
      useFilters(mockData, {
        search: {
          fields: ['name'],
          transform: (value) => value.toUpperCase(),
        },
      })
    );

    act(() => {
      result.current.setSearch('item one');
    });

    expect(result.current.filtered).toEqual([mockData[0]]);
  });

  it('should handle empty data', () => {
    const { result } = renderHook(() =>
      useFilters([], {
        search: { fields: ['name'] },
      })
    );

    act(() => {
      result.current.setSearch('test');
    });

    expect(result.current.filtered).toEqual([]);
  });

  it('should handle null/undefined filter values', () => {
    const { result } = renderHook(() =>
      useFilters(mockData, {
        filters: {
          category: {
            field: 'category',
            match: (itemValue, filterValue) => itemValue === filterValue,
          },
        },
      })
    );

    act(() => {
      result.current.setFilter('category', null);
    });

    expect(result.current.filtered).toEqual(mockData);

    act(() => {
      result.current.setFilter('category', undefined);
    });

    expect(result.current.filtered).toEqual(mockData);
  });
});

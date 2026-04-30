import { useState, useMemo, useCallback } from 'react';

export interface FilterConfig<T> {
  search?: {
    fields: (keyof T)[];
    transform?: (value: string) => string;
  };
  filters?: {
    [key: string]: {
      field: keyof T | ((item: T) => any);
      match: (itemValue: any, filterValue: any) => boolean;
    };
  };
}

export function useFilters<T>(data: T[], config: FilterConfig<T>) {
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState<Record<string, any>>({});

  const filtered = useMemo(() => {
    let result = data;

    // Apply search
    if (search && config.search) {
      const searchLower = (config.search.transform?.(search) || search).toLowerCase();
      result = result.filter((item) =>
        config.search!.fields.some((field) => {
          const value = item[field];
          return String(value).toLowerCase().includes(searchLower);
        })
      );
    }

    // Apply filters
    if (config.filters) {
      Object.entries(filters).forEach(([key, filterValue]) => {
        if (filterValue === 'all' || filterValue === '' || filterValue == null) return;

        const filterDef = config.filters![key];
        if (!filterDef) return;

        result = result.filter((item) => {
          const itemValue =
            typeof filterDef.field === 'function'
              ? filterDef.field(item)
              : item[filterDef.field];
          return filterDef.match(itemValue, filterValue);
        });
      });
    }

    return result;
  }, [data, search, filters, config]);

  const setFilter = useCallback((key: string, value: any) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }, []);

  const resetFilters = useCallback(() => {
    setSearch('');
    setFilters({});
  }, []);

  return {
    search,
    setSearch,
    filters,
    setFilter,
    resetFilters,
    filtered,
  };
}

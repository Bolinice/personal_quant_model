import client from '../client';
import type { StockPool } from '../types';

export const stockPoolApi = {
  list: (params?: Record<string, unknown>) => client.get<StockPool[]>('/stock-pools/', { params }),
  get: (poolCode: string) => client.get<StockPool>(`/stock-pools/${poolCode}`),
};

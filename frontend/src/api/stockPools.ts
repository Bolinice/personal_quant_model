import client from './client';

export interface StockPool {
  id: number;
  pool_code: string;
  pool_name: string;
  base_index_code: string;
  filter_config: Record<string, unknown>;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface StockPoolSnapshot {
  id: number;
  pool_id: number;
  trade_date: string;
  securities: string[];
  eligible_count: number;
  created_at: string;
}

export const stockPoolApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    client.get<StockPool[]>('/stock-pools/', { params }),
  get: (poolCode: string) => client.get<StockPool>(`/stock-pools/${poolCode}`),
  create: (data: { pool_code: string; pool_name: string; base_index_code: string; filter_config?: Record<string, unknown>; description?: string }) =>
    client.post<StockPool>('/stock-pools/', data),
  update: (poolId: number, data: Partial<StockPool>) =>
    client.put<StockPool>(`/stock-pools/${poolId}`, data),
  getSnapshots: (poolId: number, tradeDate?: string) =>
    client.get<StockPoolSnapshot[]>(`/stock-pools/${poolId}/snapshots`, { params: { trade_date: tradeDate } }),
  createSnapshot: (poolId: number, data: { trade_date: string; securities: string[]; eligible_count: number }) =>
    client.post<StockPoolSnapshot>(`/stock-pools/${poolId}/snapshots`, data),
};

import client from '../client';
import type { Backtest, BacktestResult, BacktestTrade, BacktestCreate } from '../types';

export const backtestApi = {
  list: (params?: Record<string, unknown>) => client.get<Backtest[]>('/backtests/', { params }),

  get: (id: number) => client.get<Backtest>(`/backtests/${id}`),

  create: (data: BacktestCreate) => client.post<Backtest>('/backtests/', data),

  update: (id: number, data: Partial<BacktestCreate>) => client.put<Backtest>(`/backtests/${id}`, data),

  getResult: (id: number) => client.get<BacktestResult>(`/backtests/${id}/result`),

  createResult: (id: number, data: Omit<BacktestResult, 'id' | 'created_at'>) =>
    client.post<BacktestResult>(`/backtests/${id}/result`, data),

  getTrades: (id: number, page?: number, pageSize?: number) =>
    client.get<BacktestTrade[]>(`/backtests/${id}/trades`, { params: { page, page_size: pageSize } }),

  run: (id: number) => client.post<Backtest>(`/backtests/${id}/run`),

  cancel: (id: number) => client.post<Backtest>(`/backtests/${id}/cancel`),
};
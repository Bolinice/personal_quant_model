import client from './client';

export interface Backtest {
  id: number;
  name: string;
  description: string | null;
  start_date: string;
  end_date: string;
  initial_capital: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface BacktestResult {
  id: number;
  backtest_id: number;
  trade_date: string;
  total_return: number;
  benchmark_return: number;
  excess_return: number;
  sharpe_ratio: number;
  created_at: string;
}

export interface BacktestTrade {
  id: number;
  backtest_id: number;
  security_id: number;
  trade_type: string;
  trade_date: string;
  quantity: number;
  price: number;
  created_at: string;
}

export interface BacktestCreate {
  name: string;
  description?: string;
  start_date: string;
  end_date: string;
  initial_capital?: number;
}

export const backtestApi = {
  list: (params?: { model_id?: number; status?: string; skip?: number; limit?: number }) =>
    client.get<Backtest[]>('/backtests/', { params }),
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

import client from './client';

export interface Portfolio {
  id: number;
  portfolio_code: string;
  portfolio_name: string;
  description: string | null;
  initial_capital: number;
  current_value: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PortfolioPosition {
  id: number;
  portfolio_id: number;
  security_id: number;
  quantity: number;
  weight: number;
  created_at: string;
}

export interface RebalanceRecord {
  id: number;
  model_id: number;
  trade_date: string;
  rebalance_type: string;
  buy_list: unknown[];
  sell_list: unknown[];
  total_turnover: number;
  created_at: string;
}

export interface PortfolioCreate {
  portfolio_code: string;
  portfolio_name: string;
  description?: string;
  initial_capital?: number;
}

export const portfolioApi = {
  list: (modelId: number, tradeDate?: string) =>
    client.get<Portfolio[]>('/portfolios/', { params: { model_id: modelId, trade_date: tradeDate } }),
  create: (data: PortfolioCreate) =>
    client.post<Portfolio>('/portfolios/', data),
  getPositions: (portfolioId: number) =>
    client.get<PortfolioPosition[]>(`/portfolios/${portfolioId}/positions`),
  createPositions: (portfolioId: number, positions: { security_id: number; quantity: number; weight: number }[]) =>
    client.post<PortfolioPosition[]>(`/portfolios/${portfolioId}/positions`, positions),
  getRebalances: (modelId: number, startDate: string, endDate: string) =>
    client.get<RebalanceRecord[]>('/portfolios/rebalances', { params: { model_id: modelId, start_date: startDate, end_date: endDate } }),
  generate: (modelId: number, tradeDate: string) =>
    client.post<Portfolio>('/portfolios/generate', null, { params: { model_id: modelId, trade_date: tradeDate } }),
  rebalance: (modelId: number, tradeDate: string) =>
    client.post<RebalanceRecord>('/portfolios/rebalance', null, { params: { model_id: modelId, trade_date: tradeDate } }),
};

import client from '../client';
import type { Portfolio, PortfolioPosition, RebalanceRecord, PortfolioCreate } from '../types';

export const portfolioApi = {
  list: (modelId: number, tradeDate?: string) =>
    client.get<Portfolio[]>('/portfolios/', {
      params: { model_id: modelId, trade_date: tradeDate || undefined },
    }),

  create: (data: PortfolioCreate) => client.post<Portfolio>('/portfolios/', data),

  getPositions: (portfolioId: number) =>
    client.get<PortfolioPosition[]>(`/portfolios/${portfolioId}/positions`),

  createPositions: (
    portfolioId: number,
    positions: { security_id: number; quantity: number; weight: number }[]
  ) => client.post<PortfolioPosition[]>(`/portfolios/${portfolioId}/positions`, positions),

  getRebalances: (modelId: number, startDate: string, endDate: string) =>
    client.get<RebalanceRecord[]>('/portfolios/rebalances', {
      params: { model_id: modelId, start_date: startDate, end_date: endDate },
    }),

  generate: (modelId: number, tradeDate: string) =>
    client.post<Portfolio>('/portfolios/generate', null, {
      params: { model_id: modelId, trade_date: tradeDate },
    }),

  rebalance: (modelId: number, tradeDate: string) =>
    client.post<RebalanceRecord>('/portfolios/rebalance', null, {
      params: { model_id: modelId, trade_date: tradeDate },
    }),
};

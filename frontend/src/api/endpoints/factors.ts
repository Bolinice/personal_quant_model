import client from '../client';
import type { Factor, FactorValue, FactorAnalysis, FactorCreate, FactorUpdate } from '../types';

export const factorApi = {
  list: (params?: Record<string, unknown>) => client.get<Factor[]>('/factors/', { params }),

  get: (id: number) => client.get<Factor>(`/factors/${id}`),

  create: (data: FactorCreate) => client.post<Factor>('/factors/', data),

  update: (id: number, data: FactorUpdate) => client.put<Factor>(`/factors/${id}`, data),

  getValues: (id: number, tradeDate: string, securityId?: number) =>
    client.get<FactorValue[]>(`/factors/${id}/values`, {
      params: { trade_date: tradeDate, security_id: securityId },
    }),

  calculate: (id: number, tradeDate: string) =>
    client.post(`/factors/${id}/calculate`, null, { params: { trade_date: tradeDate } }),

  preprocess: (id: number, tradeDate: string) =>
    client.post(`/factors/${id}/preprocess`, null, { params: { trade_date: tradeDate } }),

  icAnalysis: (id: number, startDate: string, endDate: string) =>
    client.post(`/factors/${id}/ic-analysis`, null, {
      params: { start_date: startDate, end_date: endDate },
    }),

  groupReturns: (id: number, startDate: string, endDate: string) =>
    client.post(`/factors/${id}/group-returns`, null, {
      params: { start_date: startDate, end_date: endDate },
    }),

  getAnalysis: (id: number, startDate: string, endDate: string) =>
    client.get<FactorAnalysis[]>(`/factors/${id}/analysis`, {
      params: { start_date: startDate, end_date: endDate },
    }),
};

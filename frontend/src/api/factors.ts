import client from './client';

export interface Factor {
  id: number;
  factor_code: string;
  factor_name: string;
  category: string;
  direction: string;
  calc_expression: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FactorValue {
  id: number;
  factor_id: number;
  trade_date: string;
  security_id: number;
  value: number;
  is_valid: boolean;
  created_at: string;
}

export interface FactorAnalysis {
  id: number;
  factor_id: number;
  analysis_date: string;
  analysis_type: string;
  ic: number | null;
  rank_ic: number | null;
  mean: number | null;
  std: number | null;
  coverage: number | null;
  ic_decay: number[] | null;
  group_returns: number[] | null;
  long_short_return: number | null;
  correlation: number | null;
  compare_factor_id: number | null;
  created_at: string;
}

export interface FactorCreate {
  factor_code: string;
  factor_name: string;
  category: string;
  direction?: string;
  calc_expression: string;
  description?: string;
}

export interface FactorUpdate {
  factor_name?: string;
  category?: string;
  direction?: string;
  calc_expression?: string;
  description?: string;
  is_active?: boolean;
}

export const factorApi = {
  list: (params?: { skip?: number; limit?: number; category?: string; status?: string }) =>
    client.get<Factor[]>('/factors/', { params }),
  get: (id: number) => client.get<Factor>(`/factors/${id}`),
  create: (data: FactorCreate) => client.post<Factor>('/factors/', data),
  update: (id: number, data: FactorUpdate) => client.put<Factor>(`/factors/${id}`, data),
  getValues: (factorId: number, tradeDate: string, securityId?: number) =>
    client.get<FactorValue[]>(`/factors/${factorId}/values`, { params: { trade_date: tradeDate, security_id: securityId } }),
  calculate: (factorId: number, tradeDate: string) =>
    client.post<FactorValue[]>(`/factors/${factorId}/calculate`, null, { params: { trade_date: tradeDate } }),
  preprocess: (factorId: number, tradeDate: string) =>
    client.post<FactorValue[]>(`/factors/${factorId}/preprocess`, null, { params: { trade_date: tradeDate } }),
  getAnalysis: (factorId: number, startDate: string, endDate: string) =>
    client.get<FactorAnalysis[]>(`/factors/${factorId}/analysis`, { params: { start_date: startDate, end_date: endDate } }),
  icAnalysis: (factorId: number, startDate: string, endDate: string) =>
    client.post<FactorAnalysis>(`/factors/${factorId}/ic-analysis`, null, { params: { start_date: startDate, end_date: endDate } }),
  groupReturns: (factorId: number, startDate: string, endDate: string) =>
    client.post<FactorAnalysis>(`/factors/${factorId}/group-returns`, null, { params: { start_date: startDate, end_date: endDate } }),
};

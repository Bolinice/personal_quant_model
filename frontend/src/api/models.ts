import client from './client';

export interface Model {
  id: number;
  name: string;
  description: string | null;
  model_type: string;
  version: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ModelFactorWeight {
  id: number;
  model_id: number;
  factor_id: number;
  weight: number;
  created_at: string;
}

export interface ModelScore {
  id: number;
  model_id: number;
  security_id: number;
  total_score: number;
  trade_date: string;
  created_at: string;
}

export interface ModelCreate {
  name: string;
  description?: string;
  model_type: string;
  version?: string;
}

export interface ModelUpdate {
  name?: string;
  description?: string;
  model_type?: string;
  version?: string;
  is_active?: boolean;
}

export const modelApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    client.get<Model[]>('/models/', { params }),
  get: (id: number) => client.get<Model>(`/models/${id}`),
  create: (data: ModelCreate) => client.post<Model>('/models/', data),
  update: (id: number, data: ModelUpdate) => client.put<Model>(`/models/${id}`, data),
  getFactorWeights: (modelId: number) =>
    client.get<ModelFactorWeight[]>(`/models/${modelId}/factor-weights`),
  createFactorWeights: (modelId: number, weights: { factor_id: number; weight: number }[]) =>
    client.post<ModelFactorWeight[]>(`/models/${modelId}/factor-weights`, weights),
  updateFactorWeights: (modelId: number, weights: { factor_id: number; weight: number }[]) =>
    client.put<ModelFactorWeight[]>(`/models/${modelId}/factor-weights`, weights),
  getScores: (modelId: number, tradeDate: string, selectedOnly?: boolean) =>
    client.get<ModelScore[]>(`/models/${modelId}/scores`, { params: { trade_date: tradeDate, selected_only: selectedOnly } }),
  calculateScores: (modelId: number, tradeDate: string) =>
    client.post<ModelScore[]>(`/models/${modelId}/score`, null, { params: { trade_date: tradeDate } }),
};

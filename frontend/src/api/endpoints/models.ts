import client from '../client';
import type { Model, ModelFactorWeight, ModelScore, ModelPerformance, ModelCreate, ModelUpdate } from '../types';

export const modelApi = {
  list: (params?: Record<string, unknown>) => client.get<Model[]>('/models/', { params }),

  get: (id: number) => client.get<Model>(`/models/${id}`),

  getByCode: (code: string) => client.get<Model[]>(`/models/`, { params: { model_code: code } }),

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

  getPerformance: (modelId: number, params?: Record<string, unknown>) =>
    client.get<ModelPerformance[]>(`/models/${modelId}/performance`, { params }),
};
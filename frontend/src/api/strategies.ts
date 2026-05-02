import apiClient from './client';
import type { Strategy, StrategyCreate, StrategyUpdate, StrategyListItem } from './types/strategies';

export const strategyApi = {
  list: async (params?: { page?: number; page_size?: number; status?: string }) => {
    const response = await apiClient.get<{
      items: StrategyListItem[];
      page: number;
      page_size: number;
      total: number;
    }>('/strategies/', { params });
    return response.data;
  },

  get: async (id: number) => {
    const response = await apiClient.get<Strategy>(`/strategies/${id}/`);
    return response.data;
  },

  create: async (data: StrategyCreate) => {
    const response = await apiClient.post<{ id: number; model_code: string }>('/strategies/', data);
    return response.data;
  },

  update: async (id: number, data: StrategyUpdate) => {
    const response = await apiClient.put(`/strategies/${id}/`, data);
    return response.data;
  },

  publish: async (id: number) => {
    const response = await apiClient.post(`/strategies/${id}/publish/`);
    return response.data;
  },

  archive: async (id: number) => {
    const response = await apiClient.post(`/strategies/${id}/archive/`);
    return response.data;
  },
};

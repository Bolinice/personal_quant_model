import client from '../client';
import type { Report } from '../types';

export const reportApi = {
  list: (params?: Record<string, unknown>) => client.get<Report[]>('/reports/', { params }),
  get: (id: number) => client.get<Report>(`/reports/${id}`),
  getByModel: (modelId: number, params?: Record<string, unknown>) =>
    client.get<Report[]>('/reports/', { params: { model_id: modelId, ...params } }),
};

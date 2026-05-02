import apiClient from './client';
import type { Factor } from './types/factors';

interface FactorListParams {
  page?: number;
  page_size?: number;
  category?: string;
  status?: string;
}

interface FactorListResponse {
  items: Factor[];
  total: number;
  page: number;
  page_size: number;
}

export const factorApi = {
  getFactors: async (params?: FactorListParams): Promise<FactorListResponse> => {
    const skip = params?.page ? (params.page - 1) * (params.page_size || 20) : 0;
    const limit = params?.page_size || 100;

    const response = await apiClient.get('/factors/', {
      params: {
        skip,
        limit,
        category: params?.category,
        status: params?.status,
      }
    });

    // 后端返回的是 { items: [...] } 格式
    return {
      items: response.data.items || response.data || [],
      total: response.data.total || (response.data.items || response.data || []).length,
      page: params?.page || 1,
      page_size: params?.page_size || 100,
    };
  },

  getFactor: async (id: number): Promise<Factor> => {
    const response = await apiClient.get(`/factors/${id}`);
    return response.data;
  },
};

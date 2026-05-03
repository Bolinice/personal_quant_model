import apiClient from './client';
import type { TemplateStrategy } from './types/templates';

export const templateApi = {
  list: async () => {
    const response = await apiClient.get<TemplateStrategy[]>('/models/templates');
    return response.data;
  },
};

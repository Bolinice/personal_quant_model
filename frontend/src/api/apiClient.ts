import type { AxiosResponse } from 'axios';
import client from './client';
import type { ApiResponse, PaginatedResponse } from './types/common';

/**
 * 类型安全的 API 请求包装器
 */

export class ApiClient {
  /**
   * GET 请求
   */
  static async get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
    const response: AxiosResponse<T> = await client.get(url, { params });
    return response.data;
  }

  /**
   * POST 请求
   */
  static async post<T, D = unknown>(url: string, data?: D): Promise<T> {
    const response: AxiosResponse<T> = await client.post(url, data);
    return response.data;
  }

  /**
   * PUT 请求
   */
  static async put<T, D = unknown>(url: string, data?: D): Promise<T> {
    const response: AxiosResponse<T> = await client.put(url, data);
    return response.data;
  }

  /**
   * PATCH 请求
   */
  static async patch<T, D = unknown>(url: string, data?: D): Promise<T> {
    const response: AxiosResponse<T> = await client.patch(url, data);
    return response.data;
  }

  /**
   * DELETE 请求
   */
  static async delete<T>(url: string): Promise<T> {
    const response: AxiosResponse<T> = await client.delete(url);
    return response.data;
  }

  /**
   * 分页查询
   */
  static async getPaginated<T>(
    url: string,
    params?: Record<string, unknown>
  ): Promise<PaginatedResponse<T>> {
    const response: AxiosResponse<PaginatedResponse<T>> = await client.get(url, { params });
    return response.data;
  }
}

/**
 * 创建类型安全的 API 端点
 */
export function createApiEndpoint<T, CreateT = Partial<T>, UpdateT = Partial<T>>(baseUrl: string) {
  return {
    list: (params?: Record<string, unknown>) => ApiClient.get<T[]>(baseUrl, params),

    getPaginated: (params?: Record<string, unknown>) => ApiClient.getPaginated<T>(baseUrl, params),

    get: (id: number | string) => ApiClient.get<T>(`${baseUrl}/${id}`),

    create: (data: CreateT) => ApiClient.post<T>(baseUrl, data),

    update: (id: number | string, data: UpdateT) => ApiClient.put<T>(`${baseUrl}/${id}`, data),

    patch: (id: number | string, data: Partial<UpdateT>) =>
      ApiClient.patch<T>(`${baseUrl}/${id}`, data),

    delete: (id: number | string) => ApiClient.delete<void>(`${baseUrl}/${id}`),
  };
}

export default ApiClient;

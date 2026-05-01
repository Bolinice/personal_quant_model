/**
 * API 错误处理工具
 */

import type { AxiosError } from 'axios';
import type { ApiError } from './types/common';

export class ApiErrorHandler {
  /**
   * 解析 API 错误
   */
  static parseError(error: unknown): string {
    if (error instanceof Error) {
      return error.message;
    }

    const axiosError = error as AxiosError<ApiError>;
    if (axiosError.response?.data) {
      const data = axiosError.response.data;
      if (typeof data === 'object' && 'detail' in data) {
        return data.detail;
      }
      if (typeof data === 'string') {
        return data;
      }
    }

    return '请求失败，请稍后重试';
  }

  /**
   * 判断是否为认证错误
   */
  static isAuthError(error: unknown): boolean {
    const axiosError = error as AxiosError;
    return axiosError.response?.status === 401;
  }

  /**
   * 判断是否为权限错误
   */
  static isPermissionError(error: unknown): boolean {
    const axiosError = error as AxiosError;
    return axiosError.response?.status === 403;
  }

  /**
   * 判断是否为网络错误
   */
  static isNetworkError(error: unknown): boolean {
    const axiosError = error as AxiosError;
    return !axiosError.response && axiosError.code === 'ERR_NETWORK';
  }

  /**
   * 判断是否为超时错误
   */
  static isTimeoutError(error: unknown): boolean {
    const axiosError = error as AxiosError;
    return axiosError.code === 'ECONNABORTED';
  }
}

export default ApiErrorHandler;

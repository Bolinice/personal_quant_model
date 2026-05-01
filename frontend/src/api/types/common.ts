/**
 * 统一 API 响应类型
 */

// 后端统一响应格式
export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

// 分页响应
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// 列表查询参数
export interface ListParams {
  page?: number;
  page_size?: number;
  limit?: number;
  offset?: number;
  sort_by?: string;
  order?: 'asc' | 'desc';
}

// 日期范围查询参数
export interface DateRangeParams {
  start_date?: string;
  end_date?: string;
}

// 通用 ID 参数
export interface IdParam {
  id: number | string;
}

// 错误响应
export interface ApiError {
  detail: string;
  code?: string;
  field?: string;
}

// 操作结果
export interface OperationResult {
  success: boolean;
  message?: string;
}

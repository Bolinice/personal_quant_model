/**
 * 支付API客户端
 */
import apiClient from './client';
import type {
  PaymentOrder,
  PaymentOrderCreate,
  PaymentOrderResponse,
  RefundRequest,
  RefundResponse,
  PaymentConfig,
} from './types/payments';

export const paymentsApi = {
  /**
   * 创建支付订单
   */
  createOrder: async (data: PaymentOrderCreate): Promise<PaymentOrderResponse> => {
    const response = await apiClient.post('/payments/orders', data);
    return response.data;
  },

  /**
   * 查询订单详情
   */
  getOrder: async (orderNo: string): Promise<PaymentOrder> => {
    const response = await apiClient.get(`/payments/orders/${orderNo}`);
    return response.data;
  },

  /**
   * 获取用户订单列表
   */
  getUserOrders: async (userId: number): Promise<PaymentOrder[]> => {
    const response = await apiClient.get(`/payments/orders/user/${userId}`);
    return response.data;
  },

  /**
   * 取消订单
   */
  cancelOrder: async (orderNo: string): Promise<PaymentOrder> => {
    const response = await apiClient.post(`/payments/orders/${orderNo}/cancel`);
    return response.data;
  },

  /**
   * 申请退款
   */
  refundOrder: async (data: RefundRequest): Promise<RefundResponse> => {
    const response = await apiClient.post('/payments/refund', data);
    return response.data;
  },

  /**
   * 获取支付配置列表
   */
  getConfigs: async (): Promise<PaymentConfig[]> => {
    const response = await apiClient.get('/payments/configs');
    return response.data;
  },

  /**
   * 查询订单支付状态
   */
  checkOrderStatus: async (orderNo: string): Promise<{ status: string; paid_at?: string }> => {
    const response = await apiClient.get(`/payments/orders/${orderNo}/status`);
    return response.data;
  },
};

/**
 * 支付相关类型定义
 */

export interface PaymentOrder {
  id: number;
  order_no: string;
  user_id: number;
  subscription_id?: number;
  plan_id?: number;
  subject: string;
  body?: string;
  amount: number;
  currency: string;
  payment_method: string;
  payment_type?: string;
  status: string;
  trade_no?: string;
  prepay_id?: string;
  code_url?: string;
  h5_url?: string;
  paid_at?: string;
  expired_at?: string;
  notify_data?: any;
  notify_time?: string;
  refund_amount?: number;
  refund_reason?: string;
  refunded_at?: string;
  client_ip?: string;
  extra_data?: any;
  created_at: string;
  updated_at: string;
}

export interface PaymentOrderCreate {
  user_id: number;
  plan_id: number;
  payment_method: 'alipay' | 'wechat';
  payment_type: 'web' | 'h5' | 'native' | 'jsapi' | 'yearly' | 'monthly';
  client_ip?: string;
  return_url?: string;
}

export interface PaymentOrderResponse {
  order_no: string;
  amount: number;
  subject: string;
  payment_method: string;
  payment_type: string;
  status: string;
  code_url?: string;
  h5_url?: string;
  form_data?: string;
  prepay_id?: string;
  expired_at?: string;
  created_at: string;
}

export interface RefundRequest {
  order_no: string;
  refund_amount?: number;
  refund_reason: string;
}

export interface RefundResponse {
  order_no: string;
  refund_amount: number;
  status: string;
  refunded_at?: string;
}

export interface PaymentConfig {
  id: number;
  payment_method: string;
  is_enabled: boolean;
  notify_url?: string;
  return_url?: string;
  created_at: string;
  updated_at: string;
}

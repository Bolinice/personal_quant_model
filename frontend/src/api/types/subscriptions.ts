export interface Subscription {
  id: number;
  user_id: number;
  plan_id: number;
  status: string;
  start_date: string;
  end_date: string;
  auto_renew: boolean;
  payment_method: string | null;
  transaction_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubscriptionPlan {
  id: number;
  name: string;
  description: string | null;
  price: number;
  billing_cycle: string;
  features: string[] | null;
  is_active: boolean;
  created_at: string;
}

export interface Product {
  id: number;
  product_code: string;
  product_name: string;
  product_type: string;
  description: string | null;
  price: number;
  is_active: boolean;
  created_at: string;
}
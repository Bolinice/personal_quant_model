export interface SubscriptionPlan {
  id: number;
  name: string;
  display_name: string;
  price: number;
  duration_days: number;
  features: string;
  max_stocks: number;
  max_strategies: number;
  api_rate_limit: number;
  is_active: boolean;
}

export interface CurrentSubscription {
  user_id: number;
  subscription_plan: string;
  subscription_status: string;
  plan_detail: SubscriptionPlan | null;
  started_at: string | null;
  expires_at: string | null;
}

export interface SubscribeResult {
  plan_name: string;
  started_at: string;
  expires_at: string;
}

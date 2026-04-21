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
  plan_name: string;
  plan_type: string | null;
  plan_tier: number;
  price_monthly: number | null;
  price_yearly: number | null;
  price_unit: string | null;
  custom_price: string | null;
  stock_pools: string[] | null;
  frequencies: string[] | null;
  features: string[] | null;
  description: string | null;
  highlight: boolean;
  buttons: string[] | null;
  is_active: boolean;
}

export interface PricingMatrix {
  billing_cycle: string;
  pools: string[];
  frequencies: string[];
  prices: number[][];
  note: string | null;
}

export interface UpgradePackage {
  id: number;
  name: string;
  description: string | null;
  price_monthly: number | null;
  price_yearly: number | null;
  price_standard: string | null;
  price_advanced: string | null;
  price_unit: string | null;
}

export interface PricingOverview {
  plans: SubscriptionPlan[];
  pricing_matrix: PricingMatrix[];
  upgrade_packages: UpgradePackage[];
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

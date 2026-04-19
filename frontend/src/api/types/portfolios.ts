export interface Portfolio {
  id: number;
  portfolio_code: string;
  portfolio_name: string;
  description: string | null;
  initial_capital: number;
  current_value: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PortfolioPosition {
  id: number;
  portfolio_id: number;
  security_id: number;
  quantity: number;
  weight: number;
  created_at: string;
}

export interface RebalanceRecord {
  id: number;
  model_id: number;
  trade_date: string;
  rebalance_type: string;
  buy_list: unknown[];
  sell_list: unknown[];
  total_turnover: number;
  created_at: string;
}

export interface PortfolioCreate {
  portfolio_code: string;
  portfolio_name: string;
  description?: string;
  initial_capital?: number;
}

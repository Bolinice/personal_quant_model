export interface Model {
  id: number;
  model_code: string;
  model_name: string;
  model_type: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  version?: string;
  status?: string;
  ic_mean?: number;
  ic_ir?: number;
  factor_weights?: Record<string, number>;
}

export interface ModelFactorWeight {
  id: number;
  model_id: number;
  factor_id: number;
  weight: number;
  created_at: string;
  updated_at: string;
}

export interface ModelScore {
  id: number;
  model_id: number;
  trade_date: string;
  security_id: number;
  score: number;
  rank: number | null;
  is_selected: boolean;
  created_at: string;
  quantile?: number;
}

export interface ModelPerformance {
  id: number;
  model_id: number;
  trade_date: string;
  nav: number;
  daily_return: number | null;
  cumulative_return: number | null;
  volatility: number | null;
  sharpe_ratio: number | null;
  max_drawdown: number | null;
  created_at: string;
  turnover?: number;
  ic?: number;
  rank_ic?: number;
  num_selected?: number;
}

export interface ModelCreate {
  model_code: string;
  model_name: string;
  model_type: string;
  description?: string;
}

export interface ModelUpdate {
  model_name?: string;
  model_type?: string;
  description?: string;
  is_active?: boolean;
}

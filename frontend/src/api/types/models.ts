export interface Model {
  id: number;
  model_code: string;
  model_name: string;
  description: string | null;
  model_type: string;
  version: string;
  status: string;
  factor_ids: number[] | null;
  factor_weights: Record<string, number> | null;
  ic_mean: number | null;
  ic_ir: number | null;
  created_at: string;
  updated_at: string;
}

export interface ModelFactorWeight {
  id: number;
  model_id: number;
  factor_id: number;
  weight: number;
  created_at: string;
}

export interface ModelScore {
  id: number;
  model_id: number;
  security_id: string;
  trade_date: string;
  score: number;
  rank: number | null;
  quantile: number | null;
  is_selected: boolean;
  factor_contributions: Record<string, number> | null;
  created_at: string;
}

export interface ModelPerformance {
  id: number;
  model_id: number;
  trade_date: string;
  daily_return: number | null;
  cumulative_return: number | null;
  max_drawdown: number | null;
  sharpe_ratio: number | null;
  ic: number | null;
  rank_ic: number | null;
  turnover: number | null;
  num_selected: number | null;
  created_at: string;
}

export interface ModelCreate {
  model_code: string;
  model_name: string;
  description?: string;
  model_type?: string;
  version?: string;
}

export interface ModelUpdate {
  model_name?: string;
  description?: string;
  model_type?: string;
  version?: string;
  status?: string;
}
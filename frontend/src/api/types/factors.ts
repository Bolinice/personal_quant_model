export interface Factor {
  id: number;
  factor_code: string;
  factor_name: string;
  category: string;
  direction: string;
  calc_expression: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FactorValue {
  id: number;
  factor_id: number;
  trade_date: string;
  security_id: number;
  value: number;
  is_valid: boolean;
  created_at: string;
}

export interface FactorAnalysis {
  id: number;
  factor_id: number;
  analysis_date: string;
  analysis_type: string;
  ic: number | null;
  rank_ic: number | null;
  mean: number | null;
  std: number | null;
  coverage: number | null;
  ic_decay: number[] | null;
  group_returns: number[] | null;
  long_short_return: number | null;
  correlation: number | null;
  compare_factor_id: number | null;
  created_at: string;
}

export interface FactorCreate {
  factor_code: string;
  factor_name: string;
  category: string;
  direction?: string;
  calc_expression: string;
  description?: string;
}

export interface FactorUpdate {
  factor_name?: string;
  category?: string;
  direction?: string;
  calc_expression?: string;
  description?: string;
  is_active?: boolean;
}

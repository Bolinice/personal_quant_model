export interface Strategy {
  id: number;
  model_code: string;
  model_name: string;
  model_type: string;
  description?: string | null;
  version?: string;
  status?: string;
  factor_ids?: number[];
  factor_weights?: Record<string, number>;
  model_config?: Record<string, any>;
  ic_mean?: number;
  ic_std?: number;
  ic_ir?: number;
  factors?: Array<{ id: number; factor_name: string }>;
  created_at: string;
  updated_at?: string;
}

export interface StrategyCreate {
  model_name: string;
  model_type: string;
  description?: string;
  factor_ids: number[];
  factor_weights: Record<string, number>;
  config: Record<string, any>;
}

export interface StrategyUpdate {
  model_name?: string;
  description?: string;
  factor_ids?: number[];
  factor_weights?: Record<string, number>;
  config?: Record<string, any>;
  status?: string;
}

export interface StrategyListItem {
  id: number;
  model_code: string;
  model_name: string;
  model_type: string;
  status?: string;
  version?: string;
  created_at: string;
}

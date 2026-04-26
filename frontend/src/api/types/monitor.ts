export interface MonitorFactorHealth {
  trade_date: string;
  factor_name: string;
  factor_code?: string;
  category?: string;
  coverage_rate: number | null;
  missing_rate: number | null;
  ic_rolling: number | null;
  ic_mean: number | null;
  ir: number | null;
  psi: number | null;
  health_status: string;
}

export interface MonitorModelHealth {
  trade_date: string;
  model_id: string;
  prediction_drift: number | null;
  feature_importance_drift: number | null;
  oos_score: number | null;
  health_status: string;
}

export interface MonitorAlert {
  alert_id: number;
  alert_time: string | null;
  alert_type: string | null;
  severity: string | null;
  object_type: string | null;
  object_name: string | null;
  message: string | null;
  resolved_flag: boolean;
}

export interface Regime {
  trade_date: string | null;
  regime: string;
  confidence: number | null;
  regime_detail: Record<string, unknown> | null;
  module_weight_adjustment: Record<string, number> | null;
}

export interface PortfolioMonitor {
  trade_date: string | null;
  model_id: number | null;
  industry_exposure: Record<string, number> | null;
  style_exposure: Record<string, number> | null;
  turnover_rate: number | null;
  crowding_score: number | null;
}

export interface LiveTracking {
  model_id: number | null;
  execution_deviation: number | null;
  cost_deviation: number | null;
  drawdown: number | null;
  fill_rate: number | null;
}

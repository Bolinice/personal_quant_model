export interface Event {
  id: number;
  stock_id: number;
  event_type: string;
  event_subtype: string | null;
  event_date: string;
  effective_date: string | null;
  expire_date: string | null;
  severity: string | null;
  score: number | null;
  title: string | null;
  content: string | null;
  source: string | null;
}

export interface RiskFlag {
  trade_date: string;
  stock_id: number;
  blacklist_flag: boolean;
  audit_issue_flag: boolean;
  violation_flag: boolean;
  pledge_high_flag: boolean;
  goodwill_high_flag: boolean;
  earnings_warning_flag: boolean;
  reduction_flag: boolean;
  cashflow_risk_flag: boolean;
  risk_penalty_score: number;
}

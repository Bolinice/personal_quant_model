export interface PerformanceAnalysis {
  total_return: number;
  annual_return: number;
  benchmark_return: number;
  excess_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  calmar_ratio: number;
  information_ratio: number | null;
  sortino_ratio: number | null;
  volatility: number | null;
  win_rate: number | null;
  profit_loss_ratio: number | null;
  turnover_rate: number | null;
}

export interface PerformanceReport {
  analysis: PerformanceAnalysis;
  industry_exposure: Record<string, number> | null;
  style_exposure: Record<string, number> | null;
  monthly_returns: { month: string; return: number }[] | null;
  top_holdings: { name: string; weight: number }[] | null;
  generated_at: string;
}

import client from './client';

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

export const performanceApi = {
  getBacktestAnalysis: (backtestId: number, startDate?: string, endDate?: string) =>
    client.get<PerformanceAnalysis>(`/performance/backtests/${backtestId}/analysis`, { params: { start_date: startDate, end_date: endDate } }),
  getIndustryExposure: (backtestId: number, date: string) =>
    client.get<Record<string, number>>(`/performance/backtests/${backtestId}/industry-exposure`, { params: { date } }),
  getStyleExposure: (backtestId: number, date: string) =>
    client.get<Record<string, number>>(`/performance/backtests/${backtestId}/style-exposure`, { params: { date } }),
  generateReport: (backtestId: number) =>
    client.post<PerformanceReport>(`/performance/backtests/${backtestId}/generate-report`),
};

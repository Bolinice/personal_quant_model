export interface BacktestResult {
  backtest_id: number;
  start_date: string;
  end_date: string;
  total_return: number;
  annual_return: number;
  sharpe: number;
  max_drawdown: number;
  calmar: number;
  information_ratio: number;
  win_rate: number;
}

export interface TemplateStrategy {
  id: number;
  model_name: string;
  model_code: string;
  description: string;
  status: string;
  backtest_result: BacktestResult | null;
}

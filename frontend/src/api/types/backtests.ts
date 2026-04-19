export interface Backtest {
  id: number;
  name: string;
  description: string | null;
  start_date: string;
  end_date: string;
  initial_capital: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface BacktestResult {
  id: number;
  backtest_id: number;
  trade_date: string;
  total_return: number;
  benchmark_return: number;
  excess_return: number;
  sharpe_ratio: number;
  created_at: string;
}

export interface BacktestTrade {
  id: number;
  backtest_id: number;
  security_id: number;
  trade_type: string;
  trade_date: string;
  quantity: number;
  price: number;
  created_at: string;
}

export interface BacktestCreate {
  name: string;
  description?: string;
  start_date: string;
  end_date: string;
  initial_capital?: number;
}

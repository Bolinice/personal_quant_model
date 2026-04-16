import client from './client';

export interface StockDaily {
  id: number;
  ts_code: string;
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  pre_close: number;
  change: number;
  pct_chg: number;
  vol: number;
  amount: number;
  created_at: string;
  updated_at: string;
}

export interface IndexDaily {
  id: number;
  index_code: string;
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  pre_close: number;
  change: number;
  pct_chg: number;
  vol: number;
  amount: number;
  created_at: string;
  updated_at: string;
}

export const marketApi = {
  getStockDaily: (tsCode: string, startDate: string, endDate: string) =>
    client.get<StockDaily[]>('/market/stock-daily', { params: { ts_code: tsCode, start_date: startDate, end_date: endDate } }),
  getIndexDaily: (indexCode: string, startDate: string, endDate: string) =>
    client.get<IndexDaily[]>('/market/index-daily', { params: { index_code: indexCode, start_date: startDate, end_date: endDate } }),
};

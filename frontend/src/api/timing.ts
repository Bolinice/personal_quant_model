import client from './client';

export interface TimingSignal {
  id: number;
  model_id: number;
  trade_date: string;
  signal_type: string;
  exposure: number;
  created_at: string;
}

export interface TimingConfig {
  id: number;
  model_id: number;
  config_type: string;
  config_value: string;
  created_at: string;
}

export interface TimingConfigCreate {
  model_id: number;
  config_type: string;
  config_value: string;
}

export interface TimingConfigUpdate {
  config_type?: string;
  config_value?: string;
}

export const timingApi = {
  getSignals: (modelId: number, startDate: string, endDate: string) =>
    client.get<TimingSignal[]>('/timing/signals', { params: { model_id: modelId, start_date: startDate, end_date: endDate } }),
  createSignal: (data: { model_id: number; trade_date: string; signal_type: string; exposure: number }) =>
    client.post<TimingSignal>('/timing/signals', data),
  getConfig: (modelId: number) =>
    client.get<TimingConfig>('/timing/config', { params: { model_id: modelId } }),
  createConfig: (data: TimingConfigCreate) =>
    client.post<TimingConfig>('/timing/config', data),
  updateConfig: (modelId: number, data: TimingConfigUpdate) =>
    client.put<TimingConfig>('/timing/config', { params: { model_id: modelId }, data }),
  calculateMa: (modelId: number, tradeDate: string) =>
    client.post<TimingSignal>('/timing/ma-signal', null, { params: { model_id: modelId, trade_date: tradeDate } }),
  calculateBreadth: (modelId: number, tradeDate: string) =>
    client.post<TimingSignal>('/timing/breadth-signal', null, { params: { model_id: modelId, trade_date: tradeDate } }),
  calculateVolatility: (modelId: number, tradeDate: string) =>
    client.post<TimingSignal>('/timing/volatility-signal', null, { params: { model_id: modelId, trade_date: tradeDate } }),
};

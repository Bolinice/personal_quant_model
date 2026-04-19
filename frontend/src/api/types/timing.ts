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

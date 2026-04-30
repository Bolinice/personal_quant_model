import client from '../client';
import type {
  MonitorFactorHealth,
  MonitorModelHealth,
  MonitorAlert,
  Regime,
  PortfolioMonitor,
  LiveTracking,
} from '../types';

export const monitorApi = {
  getFactorHealth: (params?: { trade_date?: string; factor_group?: string }) =>
    client.get<MonitorFactorHealth[]>('/monitor/factor-health', { params }),

  getModelHealth: (params?: { model_id?: string; trade_date?: string }) =>
    client.get<MonitorModelHealth[]>('/monitor/model-health', { params }),

  getAlerts: (params?: {
    severity?: string;
    type?: string;
    resolved?: boolean;
    page?: number;
    page_size?: number;
  }) => client.get<MonitorAlert[]>('/monitor/alerts', { params }),

  resolveAlert: (alertId: number) =>
    client.put<{ alert_id: number; resolved: boolean }>(`/monitor/alerts/${alertId}/resolve`),

  getRegime: (params?: { trade_date?: string }) =>
    client.get<Regime>('/monitor/regime', { params }),

  getPortfolioMonitor: (params?: { model_id?: number; trade_date?: string }) =>
    client.get<PortfolioMonitor[]>('/monitor/portfolio', { params }),

  getLiveTracking: (params?: { model_id?: number }) =>
    client.get<LiveTracking[]>('/monitor/live-tracking', { params }),
};

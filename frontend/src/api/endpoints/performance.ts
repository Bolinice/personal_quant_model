import client from '../client';
import type { PerformanceAnalysis, PerformanceReport } from '../types';

export const performanceApi = {
  getBacktestAnalysis: (backtestId: number, startDate?: string, endDate?: string) =>
    client.get<PerformanceAnalysis>(`/performance/backtests/${backtestId}/analysis`, {
      params: { start_date: startDate, end_date: endDate },
    }),

  getIndustryExposure: (backtestId: number, date: string) =>
    client.get<Record<string, number>>(`/performance/backtests/${backtestId}/industry-exposure`, {
      params: { date },
    }),

  getStyleExposure: (backtestId: number, date: string) =>
    client.get<Record<string, number>>(`/performance/backtests/${backtestId}/style-exposure`, {
      params: { date },
    }),

  generateReport: (backtestId: number) =>
    client.post<PerformanceReport>(`/performance/backtests/${backtestId}/generate-report`),
};

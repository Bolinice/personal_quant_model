import client from '../client';
import type { Event, RiskFlag } from '../types';

export const eventsApi = {
  getEvents: (params?: { stock_id?: number; event_type?: string; severity?: string; start_date?: string; end_date?: string; page?: number; page_size?: number }) =>
    client.get<Event[]>('/events', { params }),

  getEvent: (eventId: number) =>
    client.get<Event>(`/events/${eventId}`),

  getRiskFlags: (tradeDate: string, stockId?: number) =>
    client.get<RiskFlag[]>('/events/risk-flags', { params: { trade_date: tradeDate, stock_id: stockId } }),

  getBlacklist: () =>
    client.get<{ stock_id: number }[]>('/events/risk-flags/blacklist'),
};

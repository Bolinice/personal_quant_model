import { apiClient } from '../client';
import type { SubscriptionPlan, CurrentSubscription, SubscribeResult } from '../types/subscription';

export const subscriptionApi = {
  getPlans: () =>
    apiClient.get<{ code: number; data: SubscriptionPlan[] }>('/subscriptions/plans'),

  getCurrent: (userId: number = 1) =>
    apiClient.get<{ code: number; data: CurrentSubscription }>(`/subscriptions/current?user_id=${userId}`),

  subscribe: (userId: number, planId: number) =>
    apiClient.post<{ code: number; data: SubscribeResult }>(`/subscriptions/subscribe?user_id=${userId}&plan_id=${planId}`),
};

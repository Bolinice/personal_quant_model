import client from '../client';
import type { SubscriptionPlan, CurrentSubscription, SubscribeResult } from '../types/subscription';

export const subscriptionApi = {
  getPlans: () =>
    client.get<{ code: number; data: SubscriptionPlan[] }>('/subscriptions/plans'),

  getCurrent: (userId: number = 1) =>
    client.get<{ code: number; data: CurrentSubscription }>(`/subscriptions/current?user_id=${userId}`),

  subscribe: (userId: number, planId: number) =>
    client.post<{ code: number; data: SubscribeResult }>(`/subscriptions/subscribe?user_id=${userId}&plan_id=${planId}`),
};

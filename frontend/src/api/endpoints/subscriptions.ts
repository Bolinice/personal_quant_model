import client from '../client';

export const subscriptionApi = {
  listPlans: () => client.get('/subscriptions/plans'),

  subscribe: (userId: number, planId: number) =>
    client.post('/subscriptions/subscribe', { user_id: userId, plan_id: planId }),

  checkAccess: (userId: number, resourceCode: string) =>
    client.post<{ has_access: boolean; resource_code: string }>('/subscriptions/check-access', {
      user_id: userId,
      resource_code: resourceCode,
    }),

  getMySubscriptions: (userId: number) =>
    client.get(`/subscriptions/my/subscriptions`, { params: { user_id: userId } }),
};
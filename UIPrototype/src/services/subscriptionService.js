import { dailyDigest, historyBasedRecommendations } from '../data/subscriptionData';
import { createEndpoint, request } from './apiClient';

export const getSubscriptionFeed = createEndpoint({
  mock: () => ({ dailyDigest, historyBasedRecommendations }),
  http: () => request('/subscriptions'),
});

export const saveSubscriptionPreferences = createEndpoint({
  mock: (preferences) => preferences,
  http: (preferences) => request('/subscriptions/preferences', {
    body: preferences,
    method: 'PUT',
  }),
});

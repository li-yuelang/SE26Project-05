import { createEndpoint, request } from './apiClient';

export const saveProfile = createEndpoint({
  mock: (profile) => profile,
  http: (profile) => request('/auth/me', { body: profile, method: 'PATCH' }),
});

export const getNotificationPreferences = createEndpoint({
  mock: () => ({ email_digest: true, push_new_paper: true, push_recommendation: false }),
  http: () => request('/settings/notifications'),
});

export const saveNotificationPreferences = createEndpoint({
  mock: (preferences) => preferences,
  http: (preferences) => request('/settings/notifications', {
    body: {
      email_digest: preferences.dailyDigest,
      push_new_paper: preferences.paperAlert,
      push_recommendation: preferences.subscriptionAlert,
    },
    method: 'PUT',
  }),
});

export const getSystemPreferences = createEndpoint({
  mock: () => ({
    theme: window.localStorage.getItem('papermate:theme') || 'dark',
    default_page_size: 20,
  }),
  http: () => request('/settings/system'),
});

export const saveSystemPreferences = createEndpoint({
  mock: (preferences) => preferences,
  http: (preferences) => request('/settings/system', {
    body: {
      theme: preferences.theme,
    },
    method: 'PUT',
  }),
});

export const changePassword = createEndpoint({
  mock: () => ({ changed: true }),
  http: (passwords) => request('/settings/password', {
    body: passwords,
    method: 'PUT',
  }),
});

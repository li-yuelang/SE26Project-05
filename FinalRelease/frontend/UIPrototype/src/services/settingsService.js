import { createEndpoint, request } from './apiClient';

export const saveProfile = createEndpoint({
  mock: (profile) => profile,
  http: (profile) => request('/settings/profile', { body: profile, method: 'PUT' }),
});

export const saveNotificationPreferences = createEndpoint({
  mock: (preferences) => preferences,
  http: (preferences) => request('/settings/notifications', {
    body: preferences,
    method: 'PUT',
  }),
});

export const saveSystemPreferences = createEndpoint({
  mock: (preferences) => preferences,
  http: (preferences) => request('/settings/system', {
    body: preferences,
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

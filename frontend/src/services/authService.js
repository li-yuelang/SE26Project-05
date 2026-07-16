import { request } from './apiClient';

export function login(credentials) {
  return request('/auth/login', {
    body: credentials,
    method: 'POST',
  });
}

export function register(profile) {
  return request('/auth/register', {
    body: profile,
    method: 'POST',
  });
}

export function getCurrentUser() {
  return request('/auth/me');
}

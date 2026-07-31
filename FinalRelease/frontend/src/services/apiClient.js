const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';
export const AUTH_UNAUTHORIZED_EVENT = 'papermate:unauthorized';
const MOCK_USER_SCOPE_KEY = 'papermate:mock-user-scope';

export const apiMode = import.meta.env.VITE_API_MODE === 'mock' ? 'mock' : 'http';

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'UNKNOWN_ERROR', details = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function getAccessToken() {
  return window.localStorage.getItem('access_token') || '';
}

export function setAccessToken(token) {
  window.localStorage.setItem('access_token', token);
}

export function clearAccessToken() {
  window.localStorage.removeItem('access_token');
}

export function getMockUserScope() {
  return window.localStorage.getItem(MOCK_USER_SCOPE_KEY) || 'anonymous';
}

export function setMockUserScope(userId) {
  if (userId) window.localStorage.setItem(MOCK_USER_SCOPE_KEY, String(userId));
}

export function clearMockUserScope() {
  window.localStorage.removeItem(MOCK_USER_SCOPE_KEY);
}

export function buildWebSocketUrl(path) {
  const httpUrl = buildUrl(path);
  httpUrl.protocol = httpUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  return httpUrl;
}

function buildUrl(path, query) {
  const normalizedBase = API_BASE_URL.replace(/\/$/, '');
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const url = new URL(`${normalizedBase}${normalizedPath}`, window.location.origin);

  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value));
    }
  });

  return url;
}

export async function request(path, options = {}) {
  const {
    body,
    headers,
    method = 'GET',
    query,
    signal,
  } = options;
  const response = await fetch(buildUrl(path, query), {
    method,
    signal,
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      ...(getAccessToken() ? { Authorization: `Bearer ${getAccessToken()}` } : {}),
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const contentType = response.headers.get('content-type') || '';
  const payload = response.status === 204
    ? null
    : contentType.includes('application/json')
      ? await response.json()
      : await response.text();

  if (!response.ok) {
    if (response.status === 401 && getAccessToken()) {
      clearAccessToken();
      window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT));
    }
    throw new ApiError(
      payload?.message || payload?.detail || `请求失败（${response.status}）`,
      {
        status: response.status,
        code: payload?.code || 'HTTP_ERROR',
        details: payload,
      },
    );
  }

  return payload?.data ?? payload;
}

export function cloneMockData(value) {
  return value === undefined ? undefined : structuredClone(value);
}

export async function mockResponse(value, { delay = 120 } = {}) {
  await new Promise((resolve) => window.setTimeout(resolve, delay));
  const result = typeof value === 'function' ? value() : value;
  return cloneMockData(result);
}

export function createEndpoint({ mock, http }) {
  return (...args) => (
    apiMode === 'mock'
      ? mockResponse(() => mock(...args))
      : http(...args)
  );
}

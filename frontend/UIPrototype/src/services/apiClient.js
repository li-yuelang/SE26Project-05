const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export const apiMode = import.meta.env.VITE_API_MODE === 'http' ? 'http' : 'mock';

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'UNKNOWN_ERROR', details = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
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
    throw new ApiError(
      payload?.message || `请求失败（${response.status}）`,
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

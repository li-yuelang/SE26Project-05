import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import {
  AUTH_UNAUTHORIZED_EVENT,
  ApiError,
  apiMode,
  buildWebSocketUrl,
  clearAccessToken,
  clearMockUserScope,
  cloneMockData,
  createEndpoint,
  getAccessToken,
  getMockUserScope,
  mockResponse,
  request,
  setAccessToken,
  setMockUserScope,
} from './apiClient';

function jsonResponse(payload, init = {}) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    ...init,
    headers: {
      'content-type': 'application/json',
      ...init.headers,
    },
  });
}

describe('API client storage and URL helpers', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('stores and clears access tokens', () => {
    expect(getAccessToken()).toBe('');

    setAccessToken('token-123');
    expect(getAccessToken()).toBe('token-123');

    clearAccessToken();
    expect(getAccessToken()).toBe('');
  });

  it('stores a mock user scope only for non-empty values', () => {
    expect(getMockUserScope()).toBe('anonymous');

    setMockUserScope('');
    expect(getMockUserScope()).toBe('anonymous');

    setMockUserScope(42);
    expect(getMockUserScope()).toBe('42');

    clearMockUserScope();
    expect(getMockUserScope()).toBe('anonymous');
  });

  it('builds a WebSocket URL from the configured API origin', () => {
    const url = buildWebSocketUrl('chat/stream');

    expect(url.protocol).toBe('ws:');
    expect(url.pathname).toBe('/api/chat/stream');
  });

  it('constructs an ApiError with useful defaults and metadata', () => {
    const defaultError = new ApiError('failed');
    const detailedError = new ApiError('forbidden', {
      status: 403,
      code: 'FORBIDDEN',
      details: { reason: 'owner' },
    });

    expect(defaultError).toMatchObject({
      name: 'ApiError',
      message: 'failed',
      status: 0,
      code: 'UNKNOWN_ERROR',
      details: null,
    });
    expect(detailedError).toMatchObject({
      status: 403,
      code: 'FORBIDDEN',
      details: { reason: 'owner' },
    });
  });
});

describe('request', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sends authentication, JSON body, custom headers, and filtered query parameters', async () => {
    setAccessToken('access-token');
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      code: 'OK',
      data: { id: 'paper-1' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await request('papers', {
      method: 'POST',
      body: { title: 'Paper' },
      headers: { 'X-Trace': 'trace-1' },
      query: {
        page: 2,
        empty: '',
        missing: undefined,
        nil: null,
      },
    });

    expect(result).toEqual({ id: 'paper-1' });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url.toString()).toBe('http://localhost:3000/api/papers?page=2');
    expect(options).toMatchObject({
      method: 'POST',
      credentials: 'include',
      body: JSON.stringify({ title: 'Paper' }),
    });
    expect(options.headers).toMatchObject({
      Accept: 'application/json',
      Authorization: 'Bearer access-token',
      'Content-Type': 'application/json',
      'X-Trace': 'trace-1',
    });
  });

  it('returns raw JSON, text, and empty responses', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ items: [1, 2] }))
      .mockResolvedValueOnce(new Response('plain text', {
        status: 200,
        headers: { 'content-type': 'text/plain' },
      }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(request('/raw')).resolves.toEqual({ items: [1, 2] });
    await expect(request('/text')).resolves.toBe('plain text');
    await expect(request('/empty')).resolves.toBeNull();

    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty('Authorization');
    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty('Content-Type');
  });

  it('clears an existing token and dispatches an event after a 401 response', async () => {
    setAccessToken('expired-token');
    const unauthorizedListener = vi.fn();
    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, unauthorizedListener);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      code: 'TOKEN_EXPIRED',
      message: '登录已过期',
    }, { status: 401 })));

    await expect(request('/private')).rejects.toMatchObject({
      name: 'ApiError',
      message: '登录已过期',
      status: 401,
      code: 'TOKEN_EXPIRED',
      details: {
        code: 'TOKEN_EXPIRED',
        message: '登录已过期',
      },
    });
    expect(getAccessToken()).toBe('');
    expect(unauthorizedListener).toHaveBeenCalledOnce();

    window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, unauthorizedListener);
  });

  it('uses detail and fallback messages for other HTTP errors', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ detail: 'not found' }, { status: 404 }))
      .mockResolvedValueOnce(new Response('', {
        status: 503,
        headers: { 'content-type': 'text/plain' },
      }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(request('/missing')).rejects.toMatchObject({
      message: 'not found',
      status: 404,
      code: 'HTTP_ERROR',
    });
    await expect(request('/offline')).rejects.toMatchObject({
      message: '请求失败（503）',
      status: 503,
      code: 'HTTP_ERROR',
    });
  });
});

describe('mock helpers and endpoint selection', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('deep-clones mock data without sharing nested state', () => {
    const source = { nested: { value: 1 } };
    const cloned = cloneMockData(source);
    cloned.nested.value = 2;

    expect(source.nested.value).toBe(1);
    expect(cloneMockData(undefined)).toBeUndefined();
  });

  it('resolves static and computed mock responses after the requested delay', async () => {
    vi.useFakeTimers();
    const staticPromise = mockResponse({ ok: true }, { delay: 25 });
    const computedPromise = mockResponse(() => ({ value: 2 }), { delay: 25 });

    await vi.advanceTimersByTimeAsync(25);

    await expect(staticPromise).resolves.toEqual({ ok: true });
    await expect(computedPromise).resolves.toEqual({ value: 2 });
  });

  it('uses the HTTP implementation in the configured test environment', async () => {
    const mock = vi.fn(() => 'mock');
    const http = vi.fn(() => 'http');
    const endpoint = createEndpoint({ mock, http });

    expect(apiMode).toBe('http');
    expect(endpoint('argument')).toBe('http');
    expect(http).toHaveBeenCalledWith('argument');
    expect(mock).not.toHaveBeenCalled();
  });
});

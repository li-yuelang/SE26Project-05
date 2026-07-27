/**
 * apiClient 单元测试 —— 验证 mock/http 双模式基础设施的核心行为
 *
 * 测试目标：
 *   1. ApiError —— 自定义错误类
 *   2. cloneMockData —— 深拷贝
 *   3. mockResponse —— 模拟响应（延迟 + 结构化克隆）
 *   4. createEndpoint —— mock/http 双模式分发
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

let apiClientModule;
beforeEach(async () => {
  vi.resetModules();
  window.localStorage.clear();
  vi.stubEnv('VITE_API_MODE', 'mock');
  apiClientModule = await import('../services/apiClient.js');
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ================================================================
// 1. ApiError
// ================================================================
describe('ApiError', () => {
  it('应该使用默认值创建 ApiError', () => {
    const err = new apiClientModule.ApiError('出错了');
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(apiClientModule.ApiError);
    expect(err.name).toBe('ApiError');
    expect(err.message).toBe('出错了');
    expect(err.status).toBe(0);
    expect(err.code).toBe('UNKNOWN_ERROR');
    expect(err.details).toBeNull();
  });

  it('应该携带 status / code / details', () => {
    const details = { hint: 'retry' };
    const err = new apiClientModule.ApiError('未找到', {
      status: 404,
      code: 'NOT_FOUND',
      details,
    });
    expect(err.status).toBe(404);
    expect(err.code).toBe('NOT_FOUND');
    expect(err.details).toBe(details);
  });
});

// ================================================================
// 2. cloneMockData
// ================================================================
describe('cloneMockData', () => {
  it('undefined 返回 undefined', () => {
    expect(apiClientModule.cloneMockData(undefined)).toBeUndefined();
  });

  it('应该深拷贝对象（修改克隆不影响原对象）', () => {
    const original = { a: 1, b: { c: 2 } };
    const cloned = apiClientModule.cloneMockData(original);
    expect(cloned).toEqual(original);
    expect(cloned).not.toBe(original);
    cloned.b.c = 999;
    expect(original.b.c).toBe(2);
  });

  it('应该深拷贝数组', () => {
    const original = [{ x: 1 }, { x: 2 }];
    const cloned = apiClientModule.cloneMockData(original);
    cloned[0].x = 999;
    expect(original[0].x).toBe(1);
  });
});

// ================================================================
// 3. mockResponse
// ================================================================
describe('mockResponse', () => {
  it('应该延迟后返回深拷贝的值', async () => {
    vi.useFakeTimers();
    const data = { hello: 'world' };
    const promise = apiClientModule.mockResponse(data, { delay: 120 });
    vi.advanceTimersByTime(120);
    const result = await promise;
    expect(result).toEqual(data);
    expect(result).not.toBe(data);
    vi.useRealTimers();
  });

  it('如果 value 是函数，应该调用它', async () => {
    vi.useFakeTimers();
    const fn = vi.fn(() => ({ fromFn: true }));
    const promise = apiClientModule.mockResponse(fn, { delay: 0 });
    vi.advanceTimersByTime(0);
    const result = await promise;
    expect(fn).toHaveBeenCalledTimes(1);
    expect(result).toEqual({ fromFn: true });
    vi.useRealTimers();
  });

  it('默认 delay = 120ms', async () => {
    vi.useFakeTimers();
    const promise = apiClientModule.mockResponse('ok');
    let resolved = false;
    promise.then(() => { resolved = true; });
    await Promise.resolve();
    expect(resolved).toBe(false);
    vi.advanceTimersByTime(120);
    await promise;
    expect(resolved).toBe(true);
    vi.useRealTimers();
  });
});

// ================================================================
// 4. createEndpoint（mock 模式）
// ================================================================
describe('createEndpoint (mock mode)', () => {
  it('mock 模式下应调用 mock 函数并返回深拷贝结果', async () => {
    vi.useFakeTimers();
    const endpoint = apiClientModule.createEndpoint({
      mock: (id) => ({ id, name: 'test' }),
      http: vi.fn(),
    });
    const promise = endpoint('abc');
    vi.advanceTimersByTime(120);
    const result = await promise;
    expect(result).toEqual({ id: 'abc', name: 'test' });
    vi.useRealTimers();
  });

  it('Mock 函数接收调用参数', async () => {
    vi.useFakeTimers();
    const mockFn = vi.fn((a, b) => ({ sum: a + b }));
    const endpoint = apiClientModule.createEndpoint({
      mock: mockFn,
      http: vi.fn(),
    });
    const promise = endpoint(1, 2);
    vi.advanceTimersByTime(120);
    await promise;
    expect(mockFn).toHaveBeenCalledWith(1, 2);
    vi.useRealTimers();
  });

  it('返回的是 mock 数据的深拷贝（外部修改不污染内部）', async () => {
    vi.useFakeTimers();
    let internal = { items: [1, 2, 3] };
    const endpoint = apiClientModule.createEndpoint({
      mock: () => internal,
      http: vi.fn(),
    });
    const promise1 = endpoint();
    vi.advanceTimersByTime(120);
    const result1 = await promise1;
    result1.items.push(999);
    expect(internal.items).toEqual([1, 2, 3]);
    vi.useRealTimers();
  });
});

// ================================================================
// 5. localStorage 工具函数
// ================================================================
describe('localStorage 工具函数', () => {
  it('getAccessToken / setAccessToken / clearAccessToken', () => {
    expect(apiClientModule.getAccessToken()).toBe('');
    apiClientModule.setAccessToken('my-token');
    expect(apiClientModule.getAccessToken()).toBe('my-token');
    apiClientModule.clearAccessToken();
    expect(apiClientModule.getAccessToken()).toBe('');
  });

  it('getMockUserScope / setMockUserScope / clearMockUserScope', () => {
    expect(apiClientModule.getMockUserScope()).toBe('anonymous');
    apiClientModule.setMockUserScope('user-123');
    expect(apiClientModule.getMockUserScope()).toBe('user-123');
    apiClientModule.clearMockUserScope();
    expect(apiClientModule.getMockUserScope()).toBe('anonymous');
  });
});

// ================================================================
// 6. apiMode 常量
// ================================================================
describe('apiMode', () => {
  it('VITE_API_MODE=mock 时 apiMode 应为 "mock"', () => {
    expect(apiClientModule.apiMode).toBe('mock');
  });
});

// ================================================================
// 7. AUTH_UNAUTHORIZED_EVENT 常量
// ================================================================
describe('常量', () => {
  it('AUTH_UNAUTHORIZED_EVENT', () => {
    expect(apiClientModule.AUTH_UNAUTHORIZED_EVENT).toBe('papermate:unauthorized');
  });
});

// ================================================================
// 8. buildWebSocketUrl
// ================================================================
describe('buildWebSocketUrl', () => {
  it('http 协议应转为 ws', () => {
    const url = apiClientModule.buildWebSocketUrl('/chat/stream');
    expect(url.protocol).toMatch(/^ws/);
  });
});

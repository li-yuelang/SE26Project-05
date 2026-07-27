/**
 * authService Mock 单元测试
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

let authService;
beforeEach(async () => {
  vi.resetModules();
  window.localStorage.clear();
  vi.stubEnv('VITE_API_MODE', 'mock');
  authService = await import('../services/authService.js');
});

describe('authService 导出', () => {
  it('login 应该是函数', () => {
    expect(typeof authService.login).toBe('function');
  });

  it('register 应该是函数', () => {
    expect(typeof authService.register).toBe('function');
  });

  it('getCurrentUser 应该是函数', () => {
    expect(typeof authService.getCurrentUser).toBe('function');
  });
});

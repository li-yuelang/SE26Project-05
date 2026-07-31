import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./apiClient', () => ({
  request: vi.fn(),
}));

import { request } from './apiClient';
import { getCurrentUser, login, register } from './authService';

describe('authentication service', () => {
  beforeEach(() => {
    request.mockResolvedValue({ id: 'user-1' });
  });

  it('posts login credentials to the login endpoint', async () => {
    const credentials = { email: 'reader@example.com', password: 'secret' };

    await expect(login(credentials)).resolves.toEqual({ id: 'user-1' });
    expect(request).toHaveBeenCalledWith('/auth/login', {
      body: credentials,
      method: 'POST',
    });
  });

  it('posts a profile to the registration endpoint', async () => {
    const profile = { email: 'reader@example.com', password: 'secret', username: 'reader' };

    await register(profile);

    expect(request).toHaveBeenCalledWith('/auth/register', {
      body: profile,
      method: 'POST',
    });
  });

  it('loads the currently authenticated user', async () => {
    await getCurrentUser();

    expect(request).toHaveBeenCalledWith('/auth/me');
  });
});

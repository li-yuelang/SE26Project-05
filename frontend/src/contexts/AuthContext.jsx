import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  AUTH_UNAUTHORIZED_EVENT,
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from '../services/apiClient';
import {
  getCurrentUser,
  login as loginRequest,
  register as registerRequest,
} from '../services/authService';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(getAccessToken()));

  const applySession = useCallback((session) => {
    setAccessToken(session.access_token);
    setUser(session.user);
    return session.user;
  }, []);

  const login = useCallback(
    async (credentials) => applySession(await loginRequest(credentials)),
    [applySession],
  );

  const register = useCallback(
    async (profile) => applySession(await registerRequest(profile)),
    [applySession],
  );

  const logout = useCallback(() => {
    clearAccessToken();
    setUser(null);
    setLoading(false);
  }, []);

  const updateUser = useCallback((nextUser) => {
    setUser(nextUser);
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => {
      setUser(null);
      setLoading(false);
    };
    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
  }, []);

  useEffect(() => {
    if (!getAccessToken()) {
      setLoading(false);
      return;
    }

    let active = true;
    getCurrentUser()
      .then((currentUser) => {
        if (active) setUser(currentUser);
      })
      .catch(() => {
        if (active) setUser(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const value = useMemo(
    () => ({ loading, login, logout, register, updateUser, user }),
    [loading, login, logout, register, updateUser, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}

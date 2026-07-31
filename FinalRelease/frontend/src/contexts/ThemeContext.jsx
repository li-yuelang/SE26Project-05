import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
} from 'react';
import { ConfigProvider } from 'antd';
import { useAuth } from './AuthContext';
import { getSystemPreferences } from '../services/settingsService';
import {
  getThemeDefinition,
  isThemeName,
  THEME_STORAGE_KEY,
} from '../theme/themes';

const DEFAULT_THEME = 'dark';
const ThemeContext = createContext(null);

function getInitialTheme() {
  const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  return isThemeName(storedTheme) ? storedTheme : DEFAULT_THEME;
}

export function ThemeProvider({ children }) {
  const { user } = useAuth();
  const userId = user?.id;
  const [themeName, setThemeName] = useState(getInitialTheme);
  const definition = useMemo(() => getThemeDefinition(themeName), [themeName]);

  const applyTheme = useCallback((nextTheme) => {
    if (!isThemeName(nextTheme)) return;
    window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    setThemeName(nextTheme);
  }, []);

  useLayoutEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = themeName;
    root.style.colorScheme = definition.palette.mode;
    Object.entries(definition.cssVariables).forEach(([property, value]) => {
      root.style.setProperty(property, value);
    });
  }, [definition, themeName]);

  useEffect(() => {
    if (!userId) return undefined;
    let active = true;

    getSystemPreferences()
      .then((preferences) => {
        if (active && isThemeName(preferences.theme)) applyTheme(preferences.theme);
      })
      .catch(() => {});

    return () => {
      active = false;
    };
  }, [applyTheme, userId]);

  const value = useMemo(
    () => ({ applyTheme, themeName }),
    [applyTheme, themeName],
  );

  return (
    <ThemeContext.Provider value={value}>
      <ConfigProvider theme={definition.antdTheme}>{children}</ConfigProvider>
    </ThemeContext.Provider>
  );
}

export function useThemePreference() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useThemePreference must be used within ThemeProvider');
  return context;
}

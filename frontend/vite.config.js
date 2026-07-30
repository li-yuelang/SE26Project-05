import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  const backendTarget = env.VITE_BACKEND_TARGET || 'http://127.0.0.1:8080';

  return {
    plugins: [react()],
    server: {
      port: 3000,
      open: true,
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true,
          ws: true,
        },
        '/health': {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.js'],
      clearMocks: true,
      restoreMocks: true,
      reporters: ['default', 'junit'],
      outputFile: {
        junit: 'test-reports/junit.xml',
      },
      coverage: {
        provider: 'v8',
        reportsDirectory: 'test-reports/coverage',
        reporter: ['text', 'html', 'json-summary', 'cobertura'],
        include: [
          'src/services/apiClient.js',
          'src/services/authService.js',
          'src/utils/date.js',
        ],
        thresholds: {
          statements: 91,
          lines: 91,
          functions: 91,
          branches: 85,
        },
      },
    },
  };
});

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // Важный момент про WebSocket:
      // Vite матчится по префиксам, и порядок правил в proxy не гарантирован.
      // Поэтому /api/order/ws иногда “улетал” в /api/order (обычный proxy) и апгрейд ломался.
      // Регэксп с ^...$ заставляет правило сработать именно для WS-ручки.
      '^/api/order/ws$': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
        rewrite: () => '/ws',
        rewriteWsOrigin: true,
      },
      '^/api/courier/ws$': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        ws: true,
        rewrite: () => '/ws',
        rewriteWsOrigin: true,
      },
      '/api/order': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/api\/order/, '') || '/',
      },
      '/api/courier': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/api\/courier/, '') || '/',
      },
      '/api/log': {
        target: 'http://localhost:8004',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/log/, '') || '/',
      },
    },
  },
});

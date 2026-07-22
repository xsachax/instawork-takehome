import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server proxies API and media requests to Django so the SPA runs
// same-origin (keeps session + CSRF cookies simple during development).
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  // Under Vitest the base transform is esbuild; use React's automatic JSX
  // runtime so components don't need an explicit React import. The production
  // build uses oxc + plugin-react, so this is only applied in test mode to
  // avoid a "duplicate jsx options" warning during `vite build`.
  ...(mode === 'test' ? { esbuild: { jsx: 'automatic' } } : {}),
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/media': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
  },
}))

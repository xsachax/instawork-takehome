import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server proxies API and media requests to Django so the SPA runs
// same-origin (keeps session + CSRF cookies simple during development).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/media': 'http://localhost:8000',
    },
  },
})

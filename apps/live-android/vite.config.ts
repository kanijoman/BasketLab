import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// base './' so the build also works from the Capacitor WebView (https://localhost/).
export default defineConfig({
  base: './',
  plugins: [react()],
  worker: { format: 'es' },
  build: { target: 'es2022', chunkSizeWarningLimit: 2000 },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    testTimeout: 30_000,
  },
})

import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { existsSync, renameSync } from 'node:fs'
import { join } from 'node:path'

/** BasketLab Talent (#877) is built from this project with `vite build --mode market`: its page is `market.html`, renamed to `index.html` in `dist` so the host's default
 *  document and the rewrite of vercel.json (`/(.*)` -> `/index.html`) serve it exactly like Analytics. Only in that mode: the Analytics build does not change.
 *  It renames the written file (`writeBundle`): Vite emits the page of an HTML entry after the `generateBundle` hooks of the plugins, so a rename in the bundle finds nothing. */
const talentIndex = (): Plugin => ({
  name: 'talent-index',
  writeBundle(options) {
    const dir = options.dir
    if (dir && existsSync(join(dir, 'market.html'))) renameSync(join(dir, 'market.html'), join(dir, 'index.html'))
  },
})

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react(), ...(mode === 'market' ? [talentIndex()] : [])],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      // design/ is shared with the live app: tokens, Tailwind preset and theme store (issue #188)
      '@design': path.resolve(__dirname, '../design'),
      // the unlocking of scoped files (decryption, invitations, rights) is the live app's: one implementation until the shared interface (#330)
      '@live-package': path.resolve(__dirname, '../apps/live-android/src/package'),
    },
  },
  server: {
    port: 5173,
    fs: { allow: ['..'] },
    // Proxy /api requests to the FastAPI backend during development
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  // `vite preview` (smoke e2e, issue #111) proxies /api to the e2e API server instead of a real backend
  preview: {
    proxy: {
      '/api': {
        target: process.env.E2E_API_URL ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    ...(mode === 'market' ? { rollupOptions: { input: path.resolve(__dirname, 'market.html') } } : {}),
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
}))

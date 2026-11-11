import path from 'path'
import { defineConfig } from 'vitest/config'

// The studies (`src/**/*.study.ts`, issue #851): long evaluations over real competitions, run by hand with `npm run study:forecast` and never by the CI (the config of the tests only includes
// `*.test.ts`). They run in node (no DOM) and have no time limit worth the name.
export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@design': path.resolve(__dirname, '../design'),
      '@live-package': path.resolve(__dirname, '../apps/live-android/src/package'),
    },
  },
  test: { globals: true, environment: 'node', include: ['src/**/*.study.ts'], testTimeout: 3_600_000 },
})

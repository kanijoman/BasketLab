import { defineConfig, devices } from '@playwright/test'

// e2e of BasketLab Talent (#1006, epic #1011): real browser against the production build of Talent (`vite build --mode market`, into `dist-talent` so it never overwrites the build of Analytics)
// and the REAL publication of the exporter (`tests/local_vectors/talent_data`), served by the tests themselves in place of `raw.githubusercontent.com`. No API, no credentials, no network.
// Locally Chrome is reused (no download); CI installs Chromium.
const WEB_PORT = 4175

export default defineConfig({
  testDir: './e2e-talent',
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  outputDir: 'test-results-talent',
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    ...devices['Desktop Chrome'],
    viewport: { width: 1280, height: 800 },
    channel: process.env.CI ? undefined : 'chrome',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: `npx vite preview --outDir dist-talent --port ${WEB_PORT} --strictPort`,
    url: `http://localhost:${WEB_PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
})

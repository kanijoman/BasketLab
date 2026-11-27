import { defineConfig, devices } from '@playwright/test'

// Smoke e2e of the web app (issue #111): real browser against the production build (`vite preview`), with the REAL publication of the fixtures league served in place of the `web-data`
// branch (e2e/publication.ts). No server, no credentials, no network. Locally Chrome is reused (no download); CI installs Chromium.
const WEB_PORT = 4174

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    ...devices['Desktop Chrome'],
    viewport: { width: 1280, height: 800 },
    channel: process.env.CI ? undefined : 'chrome',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: `npx vite preview --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
})

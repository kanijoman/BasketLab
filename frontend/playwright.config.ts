import { defineConfig, devices } from '@playwright/test'

// Smoke e2e of the web app (issue #111): real browser against the production build (`vite preview`) and
// the real FastAPI app on an in-memory MongoDB (tests/e2e_web/serve_api.py). No credentials, no network.
// Python: E2E_PYTHON (default `python`). Locally Chrome is reused (no download); CI installs Chromium.
const API_PORT = 8010
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
      command: `"${process.env.E2E_PYTHON ?? 'python'}" ../tests/e2e_web/serve_api.py ${API_PORT}`,
      url: `http://localhost:${API_PORT}/api/v1/health`,
      reuseExistingServer: false, // never reuse: a dev API on this port could be pointing at the real database
      timeout: 120_000,
    },
    {
      command: `npx vite preview --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: { E2E_API_URL: `http://localhost:${API_PORT}` },
    },
  ],
})

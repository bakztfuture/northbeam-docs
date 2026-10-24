import { defineConfig, devices } from '@playwright/test'

// Minimal frontend E2E checks. Playwright starts its own Vite dev server on a separate port;
// every /api request is answered by the test's FakeApi, so no backend or database is needed.
const port = 5180

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  reporter: 'list',
  use: {
    baseURL: `http://localhost:${port}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npm run dev -- --port ${port} --strictPort`,
    url: `http://localhost:${port}`,
    reuseExistingServer: false,
  },
})

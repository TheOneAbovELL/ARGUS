import { defineConfig, devices } from '@playwright/test';

// Browser tests run the real UI against a real backend on fixture data.
// Locally you can reuse an installed Chrome: E2E_BROWSER_CHANNEL=chrome.
// In CI: `npx playwright install --with-deps chromium`.
const port = process.env.E2E_PORT ?? '8020';
const channel = process.env.E2E_BROWSER_CHANNEL || undefined;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1, // one shared backend with per-run state
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
    channel,
  },
  webServer: {
    command: 'node e2e/start-backend.mjs',
    url: `http://127.0.0.1:${port}/health/ready`,
    timeout: 120_000,
    reuseExistingServer: false,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});

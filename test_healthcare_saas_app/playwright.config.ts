/// <reference types="node" />

import { defineConfig, devices } from '@playwright/test';

const frontendBaseUrl = process.env.FRONTEND_BASE_URL ?? 'http://localhost:5173';
const apiBaseUrl = process.env.API_BASE_URL ?? 'http://localhost:8000';

export default defineConfig({
  timeout: 30 * 1000,
  expect: {
    timeout: 5000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report' }],
  ],
  use: {
    baseURL: frontendBaseUrl,
    actionTimeout: 10000,
    navigationTimeout: 30000,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    ignoreHTTPSErrors: true,
  },
  outputDir: 'test-results',
  testIgnore: ['**/node_modules/**', '**/test-results/**', '**/playwright-report/**'],
  projects: [
    {
      name: 'integration',
      testDir: './tests/integration',
      use: {
        ...devices['Desktop Chrome'],
        extraHTTPHeaders: {
          'x-test-suite': 'integration',
        },
      },
      metadata: {
        apiBaseUrl,
      },
    },
    {
      name: 'e2e',
      testDir: './tests/e2e',
      use: {
        ...devices['Desktop Chrome'],
      },
      metadata: {
        apiBaseUrl,
      },
    },
  ],
});

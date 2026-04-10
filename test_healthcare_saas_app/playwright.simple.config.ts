import { defineConfig, devices } from '@playwright/test';

/**
 * Simple Playwright configuration for testing without global setup
 */
export default defineConfig({
  testDir: './tests',
  timeout: 30 * 1000,
  expect: {
    timeout: 5000
  },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list']
  ],
  use: {
    baseURL: 'http://localhost:5174',
    actionTimeout: 10000,
    navigationTimeout: 30000,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,
    testIdAttribute: 'data-testid'
  },
  projects: [
    {
      name: 'chromium',
      use: { 
        ...devices['Desktop Chrome']
      },
      testMatch: '**/ui-registration-appointment-final.spec.ts'
    }
  ],
  testIgnore: [
    '**/node_modules/**',
    '**/test-results/**',
    '**/playwright-report/**',
    '**/playwright/.cache/**'
  ],
  outputDir: 'test-results',
});

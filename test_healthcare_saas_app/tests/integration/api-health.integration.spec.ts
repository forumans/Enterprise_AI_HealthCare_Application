import { test, expect } from '@playwright/test';

test.describe('API health integration', () => {
  test('backend health endpoint responds with success', async ({ request }, testInfo) => {
    const apiBaseUrl = String(testInfo.project.metadata.apiBaseUrl ?? 'http://localhost:8000');

    const response = await request.get(`${apiBaseUrl}/api/health`);

    expect(response.ok()).toBeTruthy();
  });
});

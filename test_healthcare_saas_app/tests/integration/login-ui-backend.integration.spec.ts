import { test, expect } from '@playwright/test';

test.describe('Login UI to backend integration', () => {
  test('admin login submits to backend auth endpoint and returns 401 for invalid credentials', async ({ page }) => {
    await page.goto('/admin/login');

    await page.fill('input[type="email"]', 'invalid-admin@example.com');
    await page.fill('input[type="password"]', 'wrong-password');

    const loginResponsePromise = page.waitForResponse(
      (response) => response.url().includes('/auth/login') && response.request().method() === 'POST',
    );

    await page.click('button[type="submit"]');

    const loginResponse = await loginResponsePromise;
    expect(loginResponse.status()).toBe(401);
    await expect(page).toHaveURL(/\/admin\/login/);
  });
});

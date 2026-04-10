import { test, expect } from '@playwright/test';

test.describe('Admin dashboard E2E', () => {
  test('shows tenant name and appointment metrics after successful admin login', async ({ page }) => {
    const adminEmail = process.env.ADMIN_E2E_EMAIL;
    const adminPassword = process.env.ADMIN_E2E_PASSWORD;

    test.skip(!adminEmail || !adminPassword, 'Set ADMIN_E2E_EMAIL and ADMIN_E2E_PASSWORD to run admin E2E flow.');

    await page.goto('/admin/login');
    await page.fill('input[type="email"]', adminEmail!);
    await page.fill('input[type="password"]', adminPassword!);
    await page.click('button[type="submit"]');

    await page.waitForURL('/');
    await page.goto('/admin/system-dashboard');

    const metricsResponse = await page.waitForResponse(
      (response) => response.url().includes('/admin/appointment-metrics') && response.request().method() === 'GET',
    );

    expect(metricsResponse.ok()).toBeTruthy();
    await expect(page.locator('h3', { hasText: 'Administrator' })).toBeVisible();
    await expect(page.locator('label', { hasText: 'Tenant Name' })).toBeVisible();
    await expect(page.locator('text=Appointments (To Date)')).toBeVisible();
    await expect(page.locator('text=Appointments YTD')).toBeVisible();
    await expect(page.locator('text=Appointments This Month')).toBeVisible();
    await expect(page.locator('text=Appointments This Week')).toBeVisible();
    await expect(page.locator('text=Appointments Today')).toBeVisible();
  });
});

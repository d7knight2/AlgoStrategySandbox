import { test, expect } from '@playwright/test';

test.describe('Visual snapshots', () => {
  test('home page matches snapshot', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'AlgoStrategySandbox' })).toBeVisible();
    const homeShell = page.locator('header').locator('xpath=ancestor::div[1]');
    await expect(homeShell).toHaveScreenshot('home-page.png');
  });

  test('report page matches snapshot', async ({ page }) => {
    await page.goto('/report');
    await expect(
      page.getByRole('heading', { name: 'Lumibot + Alpaca Integration Report' }),
    ).toBeVisible();
    await expect(page.locator('main')).toHaveScreenshot('report-page.png');
  });
});
